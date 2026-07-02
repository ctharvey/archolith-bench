"""Deterministic retrieval-quality harness (no answer-model spend).

For each LongMemEval question it measures, per retrieval arm:
  - gold_rank : smallest k such that the gold answer's tokens are all present in the
                ACCUMULATED text of the top-k candidates (i.e. "answer becomes present
                in context at rank k"). None if never present within the cap.
  - present@k : gold_rank <= k.

Arms:
  - menhir   : HTTP /api/recall against a running menhir server (whatever config it serves).
  - graphiti : graphiti-core native search() over the same graph (edge facts) — the
               Graphiti/Zep-shaped baseline.

This isolates RETRIEVAL from generation/judge noise: if the gold is not in top-k, it's a
candidate-generation problem; if it is and the answer is still wrong, it's packing/generation.
"""
import os, re, json, asyncio, statistics, sys

import glob
import httpx
from graphiti_core import Graphiti
from graphiti_core.driver.neo4j_driver import Neo4jDriver
from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig

MENHIR_URL = os.environ["MENHIR_URL"].rstrip("/")
KEY = os.environ["OPENAI_API_KEY"]
BOLT = os.getenv("LME_BOLT", "bolt://localhost:7689")
PW = os.getenv("LME_NEO4J_PW", "lmedata123")
N = int(os.getenv("LME_N", "30"))
CAP = int(os.getenv("LME_TOPK", "20"))
KS = (5, 10, 20)

_PUNCT = str.maketrans({c: " " for c in r"""!"#$%&'()*+,-./:;<=>?@[\]^_`{|}~"""})
_STOP = set("a an the of to and or in on at for with is was are were be been "
            "i you he she it we they my your his her its our their me him them "
            "do did does what when where which who how why that this these those".split())


def _norm(t: str) -> str:
    return re.sub(r"\s+", " ", t.lower().translate(_PUNCT)).strip()


def _content_tokens(t: str) -> set:
    return {w for w in _norm(t).split() if w not in _STOP}


def _gold_tokens(t: str) -> set:
    # Distinctive gold tokens: drop stopwords so common words don't fake "presence".
    return {w for w in _norm(t).split() if w not in _STOP and len(w) > 1}


def gold_rank(gold: str, ranked_texts: list[str]) -> int | None:
    """Smallest 1-based k s.t. all distinctive gold tokens appear in top-k accumulated text."""
    gt = _gold_tokens(gold)
    if not gt:
        return None
    acc: set = set()
    for i, txt in enumerate(ranked_texts, 1):
        acc |= _content_tokens(txt)
        if gt <= acc:
            return i
    return None


def evidence_tokens(item: dict) -> set:
    """Distinctive tokens of the SUPPORT: the has_answer evidence turns. Unlike the gold
    answer (often a computed value stored nowhere), the support IS in memory — so this
    separates retrieval failure from reasoning failure."""
    toks: set = set()
    for sess in (item.get("haystack_sessions") or []):
        for turn in (sess if isinstance(sess, list) else []):
            if isinstance(turn, dict) and turn.get("has_answer"):
                toks |= _content_tokens(turn.get("content", ""))
    return toks


def support_rank(support: set, ranked_texts: list[str], thresh: float = 0.5) -> int | None:
    """Smallest 1-based k s.t. the top-k accumulated text COVERS >= thresh of the support
    tokens (coverage, not all-or-nothing, because enrichment rewords raw turns)."""
    if not support:
        return None
    acc: set = set()
    need = max(1, int(len(support) * thresh))
    for i, txt in enumerate(ranked_texts, 1):
        acc |= _content_tokens(txt)
        if len(acc & support) >= need:
            return i
    return None


def menhir_recall(q: str, ns: str) -> list[str]:
    r = httpx.post(f"{MENHIR_URL}/api/recall",
                   json={"query": q, "limit": CAP, "namespace": ns, "include_session": True},
                   timeout=90)
    r.raise_for_status()
    out = []
    for it in (r.json().get("results") or []):
        if isinstance(it, dict):
            out.append(f"{it.get('name') or ''} {it.get('content') or ''}".strip())
    return out


async def main():
    cached = glob.glob(os.path.expanduser(
        "~/.cache/huggingface/hub/datasets--xiaowu0162--longmemeval/snapshots/*/longmemeval_oracle"))
    if not cached:
        raise SystemExit("longmemeval_oracle not found in HF cache; run a bench arm first to populate it.")
    all_items = json.load(open(cached[0], encoding="utf-8"))
    # STRATIFIED sample: first PER_TYPE of each question_type (the file is grouped by type, so
    # plain --limit N only ever saw temporal-reasoning). This gives a fair cross-type picture.
    per_type = int(os.getenv("LME_PER_TYPE", "15"))
    by_type: dict[str, list] = {}
    for it in all_items:
        by_type.setdefault(it.get("question_type"), []).append(it)
    items = []
    for t, lst in by_type.items():
        items.extend(lst[:per_type])

    driver = Neo4jDriver(uri=BOLT, user="neo4j", password=PW, database="neo4j")
    embedder = OpenAIEmbedder(config=OpenAIEmbedderConfig(api_key=KEY, embedding_model="text-embedding-3-small", embedding_dim=1536))
    g = Graphiti(uri=BOLT, user="neo4j", password=PW, graph_driver=driver, embedder=embedder, llm_client=None, cross_encoder=None)

    rows = []
    try:
        for it in items:
            qid = str(it.get("question_id") or it.get("id"))
            ns = f"lme-{qid}"
            q = it.get("question", "")
            gold = str(it.get("answer", ""))
            qtype = it.get("question_type")
            if qtype == "abstention" or _norm(gold) in {"", "no answer", "unknown"}:
                continue
            m_texts = menhir_recall(q, ns)
            try:
                edges = await g.search(q, group_ids=[ns], num_results=CAP)
                g_texts = [(getattr(e, "fact", None) or "") for e in edges]
            except Exception as e:
                g_texts = []
            supp = evidence_tokens(it)
            rows.append({
                "qid": qid, "qtype": qtype, "gold": gold[:60],
                "m_rank": gold_rank(gold, m_texts), "m_n": len(m_texts),
                "g_rank": gold_rank(gold, g_texts), "g_n": len(g_texts),
                # SUPPORT presence (evidence-turn coverage) — the retrieval-vs-reasoning splitter
                "m_supp": support_rank(supp, m_texts), "g_supp": support_rank(supp, g_texts),
                "supp_n": len(supp),
            })
    finally:
        await g.close()

    def summarize(subset, key):
        ranks = [r[key] for r in subset]
        found = [x for x in ranks if x is not None]
        line = {f"present@{k}": sum(1 for x in found if x <= k) for k in KS}
        line["found"] = len(found); line["total"] = len(ranks)
        line["median_rank"] = statistics.median(found) if found else None
        return line

    print(f"\n===== RETRIEVAL QUALITY (N={len(rows)}, cap top-{CAP}) =====")
    print(f"{'':10s} present@5  present@10  present@20  found/total  median_rank")
    for label, key in (("menhir", "m_rank"), ("graphiti", "g_rank")):
        s = summarize(rows, key)
        print(f"{label:10s} {s['present@5']:9d}  {s['present@10']:10d}  {s['present@20']:10d}  "
              f"{s['found']:5d}/{s['total']:<5d}  {s['median_rank']}")

    print("\n===== GOLD vs SUPPORT presence (menhir, present@k) =====")
    print(f"{'':10s} present@3  present@5  present@10  found/total  median_rank")
    for label, key in (("gold", "m_rank"), ("support", "m_supp")):
        s = summarize(rows, key)
        p3 = sum(1 for r in rows if r[key] is not None and r[key] <= 3)
        print(f"{label:10s} {p3:9d}  {s['present@5']:9d}  {s['present@10']:10d}  "
              f"{s['found']:5d}/{s['total']:<5d}  {s['median_rank']}")

    print("\n===== BY QUESTION TYPE (present@10) =====")
    types = sorted({r["qtype"] for r in rows})
    print(f"{'type':26s} n   gold(m)  supp(m)  gold(graphiti)")
    for t in types:
        sub = [r for r in rows if r["qtype"] == t]
        m = summarize(sub, "m_rank"); ms = summarize(sub, "m_supp"); gg = summarize(sub, "g_rank")
        print(f"{str(t)[:26]:26s} {len(sub):<3d} {m['present@10']:>4d}/{len(sub):<3d} "
              f"{ms['present@10']:>4d}/{len(sub):<3d} {gg['present@10']:>4d}/{len(sub):<3d}")
    print("\n--- per-question (rank = where gold becomes present in accumulated context) ---")
    print(f"{'qid':22s} {'type':16s} menhir  graphiti  gold")
    for r in rows:
        print(f"{r['qid']:22s} {str(r['qtype'])[:16]:16s} {str(r['m_rank']):>6s}  {str(r['g_rank']):>8s}  {r['gold']!r}")


asyncio.run(main())
