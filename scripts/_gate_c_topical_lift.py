"""Isolate FACET's net-new: does operation/object GENERATION surface gold memories that
vector/lexical recall misses? (menhir R2 Phase-4 go/no-go, pre-gate-c.)

Gate (b) showed the reranker's win is scope/belief discipline — which the ScopeWarden
already provides. The open question: beyond scope, does facet candidate generation by
TOPICAL (operation/object) overlap recover relevant memories BM25/embedding rank outside
top-k? If yes, that recovery is FACET's genuine net-new over the warden chain; if not,
active wiring isn't justified.

Method (gold mode, to isolate facet families cleanly):
  1. Baselines (BM25, embedding) rank the corpus per query -> the gold-support memories
     ranked OUTSIDE top-k by BOTH are the "vector-missed" set.
  2. Run F (facet index generation + meet-point rerank) under three facet restrictions:
       scope_only  = repo/project/namespace/belief/time      (warden-equivalent)
       scope+topic = scope_only + operation/object            (adds topical generation)
       full        = all facets                               (+ structural)
  3. Report recall@k per restriction, the marginal lift of adding topical, and how many
     vector-missed gold each restriction RECOVERS into top-k. The scope+topic - scope_only
     delta on the vector-missed set is the number that decides go/no-go.
"""
from __future__ import annotations

import argparse
import copy
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from archolith_bench.facet.models import ALL_FACETS, FacetFixture  # noqa: E402
from archolith_bench.facet.runner import FacetBenchmarkRunner  # noqa: E402

K = 5
SCOPE_ONLY = {"repo", "project", "namespace", "belief_bucket", "valid_time", "learned_time"}
SCOPE_TOPIC = SCOPE_ONLY | {"operation", "object"}
FULL = set(ALL_FACETS)
RESTRICTIONS = [("scope_only", SCOPE_ONLY), ("scope+topic", SCOPE_TOPIC), ("full", FULL)]


def _restrict(fixture: FacetFixture, allowed: set[str]) -> FacetFixture:
    """Copy with every facet NOT in `allowed` zeroed, on memories AND queries."""
    fx = copy.deepcopy(fixture)
    for holder in list(fx.memories) + list(fx.queries):
        for facet in ALL_FACETS:
            if facet in allowed:
                continue
            cur = getattr(holder.facets, facet)
            setattr(holder.facets, facet, set() if isinstance(cur, set) else None)
    return fx


def _ranks_by_query(fixture: FacetFixture, condition: str, embedder) -> dict[str, list[str]]:
    runner = FacetBenchmarkRunner(fixture, embedder=embedder)
    result = runner.run_condition(condition, "gold")
    return {pq.query_id: pq.ranked for pq in result.per_query}


def _f_traces(fixture: FacetFixture, embedder) -> dict[str, dict[str, dict]]:
    """query_id -> {memory_id -> meet-point explanation dict} for full-facet F (gold)."""
    runner = FacetBenchmarkRunner(fixture, embedder=embedder)
    result = runner.run_condition("F_facet_meet", "gold")
    return {pq.query_id: {t["memory_id"]: t for t in pq.trace} for pq in result.per_query}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixture", nargs="?", default=str(REPO_ROOT / "fixtures" / "facet_r2_draft.json"))
    parser.add_argument("--embedder", choices=["stub", "openai"], default="stub")
    args = parser.parse_args(argv)

    embedder = None
    if args.embedder == "openai":
        from run_facet_bench import OpenAIEmbeddingScorer

        embedder = OpenAIEmbeddingScorer()

    fixture = FacetFixture.from_file(Path(args.fixture))
    queries = [q for q in fixture.queries if q.support_ids]  # skip abstention/vague-no-gold

    # Baseline ranks (facet-independent) -> vector-missed gold per query.
    bm25 = _ranks_by_query(fixture, "A_bm25", embedder)
    embd = _ranks_by_query(fixture, "B_embedding", embedder)

    vector_missed: dict[str, set[str]] = {}   # query_id -> gold ids missed by BOTH baselines @k
    total_gold = 0
    for q in queries:
        top_bm = set(bm25[q.id][:K])
        top_em = set(embd[q.id][:K])
        missed = {g for g in q.support_ids if g not in top_bm and g not in top_em}
        vector_missed[q.id] = missed
        total_gold += len(q.support_ids)
    n_missed = sum(len(v) for v in vector_missed.values())

    # F ranks under each facet restriction.
    f_ranks: dict[str, dict[str, list[str]]] = {
        name: _ranks_by_query(_restrict(fixture, allowed), "F_facet_meet", embedder)
        for name, allowed in RESTRICTIONS
    }

    def recall_at_k(ranks: dict[str, list[str]]) -> float:
        hit = sum(
            len(set(ranks[q.id][:K]) & set(q.support_ids)) for q in queries
        )
        return hit / total_gold if total_gold else 0.0

    def recovered(ranks: dict[str, list[str]]) -> int:
        """vector-missed gold that this F restriction ranks INSIDE top-k."""
        return sum(
            len(set(ranks[qid][:K]) & missed) for qid, missed in vector_missed.items()
        )

    by_qid = {q.id: q for q in queries}
    traces = _f_traces(fixture, embedder)

    print(f"fixture={Path(args.fixture).name} k={K} embedder={args.embedder}")
    print(f"queries with gold: {len(queries)}  total gold: {total_gold}  "
          f"vector-missed gold (both baselines miss @k): {n_missed}\n")

    header = f"{'F facet restriction':16s} {'recall@5':>9s} {'vec-missed rec':>15s}"
    print(header)
    print("-" * len(header))
    for name, _allowed in RESTRICTIONS:
        r = recall_at_k(f_ranks[name])
        rec = recovered(f_ranks[name])
        print(f"{name:16s} {r:>9.3f} {rec:>11d}/{n_missed}")
    print("  NOTE: scope_only generation floods the same-scope corpus; its 'recovery' is a "
          "meet-point tie-break by memory-id, not real signal. The per-case table below is "
          "decisive.\n")

    # DECISIVE: for each vector-missed gold, does FULL-facet F rank it top-k, and driven by
    # what? topical overlap present iff gold shares operation/object with the query.
    print("per-case: vector-missed gold under FULL-facet F")
    print(f"{'query':6s} {'gold':5s} {'shares op/obj':>13s} {'F-rank':>7s} {'score':>6s}  matched (required+convergence)")
    print("-" * 92)
    topical_driven = 0
    for qid, missed in vector_missed.items():
        if not missed:
            continue
        q = by_qid[qid]
        q_topic = q.facets.values("operation") | q.facets.values("object")
        for g in sorted(missed):
            mem = fixture.memories_by_id[g]
            shares = bool(q_topic & (mem.facets.values("operation") | mem.facets.values("object")))
            frank = f_ranks["full"][qid].index(g) + 1 if g in f_ranks["full"][qid] else None
            tr = traces.get(qid, {}).get(g, {})
            matched = list(tr.get("matched_required", [])) + [
                f"conv:{k}" for k in (tr.get("convergence") or {})
            ]
            non_scope = [m for m in matched if m.split(":")[-1] in ("operation", "object", "file", "symbol", "test")]
            in_topk = frank is not None and frank <= K
            if in_topk and shares and non_scope:
                topical_driven += 1
            print(f"{qid:6s} {g:5s} {str(shares):>13s} {str(frank):>7s} "
                  f"{tr.get('score', 0):>6.1f}  {matched}")

    print(f"\nDECISION SIGNAL: of {n_missed} vector-missed gold, {topical_driven} are recovered "
          f"into top-{K} by FULL-facet F via a NON-scope (op/obj/structural) match.")
    print("If ~0, FACET generation adds nothing the ScopeWarden's scope discipline doesn't "
          "already give -> Phase-4 active wiring NOT justified. If >0, that count is the net-new.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
