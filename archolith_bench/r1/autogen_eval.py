"""Auto-generated known-item retrieval eval (plan v6 §2).

Instead of a hand-curated gold corpus (curator bias: \"the queries are mine\"), sample real
memories from the frozen clone and, for each, generate a PARAPHRASED query whose answer is
that memory. The metric is known-item: does the source memory (or any duplicate-cluster
member) come back, and at what rank?

Why this shape:
  - reproducible NUMBER for the win gate, not a spot-check's vibes;
  - bigger N for pennies; samples the true corpus distribution, not my cherry-picks;
  - no prod-UUID rot -- the answer key is regenerated each run (no R7 repair machinery);
  - the generator naturally produces paraphrase queries, which ARE the hypothesis.

All I/O (Neo4j, the generator LLM) is behind the ``CorpusReader`` / ``QueryGenerator``
protocols so the sampling, clustering, prompt, and orchestration logic is unit-tested with
stubs -- no live clone or model required. The live adapters live in ``autogen_eval_live.py``
(P0 wiring, exercised only against the clone).
"""
from __future__ import annotations

import hashlib
import random
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Protocol, Sequence


# --------------------------------------------------------------------------- data


@dataclass(frozen=True)
class CorpusNode:
    """A sampled memory candidate from the clone."""

    uuid: str
    name: str
    text: str  # the recall-text: summary -> content -> name (plan v6 §9.1)
    namespace: str = "default"


@dataclass(frozen=True)
class AutogenQuery:
    """One generated known-item eval case."""

    query_text: str
    gold_cluster_ids: tuple[str, ...]  # source uuid + any near-duplicate siblings
    source_uuid: str
    source_text_sha256: str
    namespace: str
    stratum: str = ""


# --------------------------------------------------------------------------- seams


class CorpusReader(Protocol):
    """Live seam over the clone. Implemented for real in autogen_eval_live.py."""

    def sample_candidates(self) -> Sequence[CorpusNode]:
        """Return every eligible node (has non-empty text). Caller does the sampling,
        so the sample is deterministic and reproducible from the manifest seed."""
        ...

    def duplicate_cluster(self, node: CorpusNode, threshold: float) -> Sequence[str]:
        """UUIDs of GENUINE near-duplicates of ``node`` -- \"the same fact stored twice.\"

        The clone is a duplicate of prod, and prod holds near-duplicate memories, so
        retrieving any sibling is a correct answer, not a miss (plan v6 §2.2).

        ANTI-SKEW CONTRACT (plan Appendix H.2 -- load-bearing): the cluster MUST be
        computed by a LANE-NEUTRAL signal -- lexical near-identity (normalized-text hash
        or high token Jaccard on the recall-text). It MUST NOT be computed from
        ``content_embedding`` cosine, ``name_embedding`` cosine, or BM25 score. Clustering
        by a lane's own ranking function makes \"what counts as a hit\" the very metric that
        lane optimizes, rigging cluster-crediting toward that arm. ``threshold`` is the
        lexical-similarity threshold (e.g. Jaccard >= 0.9), NOT an embedding cosine.
        """
        ...


class QueryGenerator(Protocol):
    """Live seam over the generator LLM."""

    def generate(self, prompt: str) -> str:
        ...


# --------------------------------------------------------------------------- prompt


PARAPHRASE_SYSTEM_INSTRUCTION = (
    "You write a single search query that a user would type to FIND the note below, "
    "WITHOUT reusing its distinctive words. Ask about the FACT it records using different "
    "phrasing, synonyms, or an abbreviation's expansion (or vice versa). Do not quote the "
    "note. Do not add explanation. Output only the query, one line."
)


def build_paraphrase_prompt(node: CorpusNode) -> str:
    """The exact text handed to the generator. Pure, so it is testable and versionable."""
    return f"{PARAPHRASE_SYSTEM_INSTRUCTION}\n\n---\nNOTE:\n{node.text.strip()}\n---\nQUERY:"


def looks_like_leak(query: str, node: CorpusNode) -> bool:
    """Heuristic: did the generator cheat by quoting the note's distinctive IDENTIFIERS?

    A query that echoes the memory's identifier-shaped tokens (``PUBLIC_GA_ID``,
    ``lifecycle_decay_interval_s``) tests BM25's strength, not the content lane's, and is
    unrealistic -- a user would not type them. Such a case is flagged (not silently kept).

    Crucially this does NOT flag shared ordinary words. \"decay\", \"interval\", \"server\"
    are topic words a real user would type; sharing them is expected overlap, not leakage.
    The signal is specifically an IDENTIFIER: a raw token with an underscore, an embedded
    digit, or internal capitalization (camelCase). See tests for the boundary cases.
    """
    q_ids = {t.lower() for t in _raw_tokens(query) if _is_identifier_shaped(t)}
    if not q_ids:
        return False
    # The generator sees the full recall text, not only the entity name. Comparing
    # against name alone lets an identifier copied from summary/content slip through
    # and turns the case into an artificial BM25 win.
    source_text = f"{node.name} {node.text}"
    n_ids = {t.lower() for t in _raw_tokens(source_text) if _is_identifier_shaped(t)}
    return bool(q_ids & n_ids)


def _raw_tokens(s: str) -> list[str]:
    """Whitespace/punctuation split, but KEEP underscores and original case (both are
    identifier signals: ``_`` and camelCase). Returns a list so case is preserved."""
    return [t for t in "".join(c if (c.isalnum() or c == "_") else " " for c in s).split() if t]


def _is_identifier_shaped(token: str) -> bool:
    """True for tokens that read as code identifiers, not ordinary prose words:
    an underscore, an embedded digit, or an internal capital (camelCase/PascalCase)."""
    if "_" in token or any(c.isdigit() for c in token):
        return True
    return any(c.isupper() for c in token[1:])  # internal capital after the first char


# --------------------------------------------------------------------------- sampling


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def stratified_sample(
    candidates: Sequence[CorpusNode],
    n: int,
    *,
    seed: int,
    stratum_of=lambda node: node.namespace,
) -> list[CorpusNode]:
    """Deterministically pick ``n`` nodes, allocated across strata in proportion to size.

    Mirrors the corpus rather than its head: a namespace holding 5% of the eligible nodes
    receives ~5% of the sample. Fully determined by ``seed`` (recorded in the manifest),
    so the run is reproducible despite being generated.
    """
    if n <= 0 or not candidates:
        return []
    if n >= len(candidates):
        return list(candidates)

    buckets: dict[str, list[CorpusNode]] = defaultdict(list)
    for node in candidates:
        buckets[stratum_of(node)].append(node)

    # Stable stratum order so allocation is deterministic regardless of dict/order noise.
    strata = sorted(buckets)
    total = len(candidates)

    # Largest-remainder apportionment: floor quotas, then hand out the leftover seats to
    # the strata with the biggest fractional remainder (ties broken by stratum name).
    raw = {s: n * len(buckets[s]) / total for s in strata}
    quota = {s: int(raw[s]) for s in strata}
    leftover = n - sum(quota.values())
    for s in sorted(strata, key=lambda s: (-(raw[s] - int(raw[s])), s))[:leftover]:
        quota[s] += 1

    rng = random.Random(seed)
    picked: list[CorpusNode] = []
    for s in strata:
        pool = sorted(buckets[s], key=lambda node: node.uuid)  # stable base order
        k = min(quota[s], len(pool))
        picked.extend(rng.sample(pool, k))
    # Deterministic final order.
    picked.sort(key=lambda node: node.uuid)
    return picked


# --------------------------------------------------------------------------- build


@dataclass
class EvalSetResult:
    queries: list[AutogenQuery] = field(default_factory=list)
    leaked: list[AutogenQuery] = field(default_factory=list)  # flagged, not scored-as-clean
    skipped_empty: int = 0
    cluster_sizes: list[int] = field(default_factory=list)


def build_eval_set(
    corpus: CorpusReader,
    generator: QueryGenerator,
    *,
    n: int,
    seed: int,
    duplicate_threshold: float = 0.97,
    stratum_of=lambda node: node.namespace,
) -> EvalSetResult:
    """Sample -> generate paraphrase query -> compute duplicate cluster -> assemble.

    Pure orchestration over the two injected seams; no direct I/O here.
    """
    candidates = [c for c in corpus.sample_candidates() if c.text and c.text.strip()]
    sample = stratified_sample(candidates, n, seed=seed, stratum_of=stratum_of)

    result = EvalSetResult()
    for node in sample:
        query_text = generator.generate(build_paraphrase_prompt(node)).strip()
        if not query_text:
            result.skipped_empty += 1
            continue
        cluster = tuple(dict.fromkeys([node.uuid, *corpus.duplicate_cluster(node, duplicate_threshold)]))
        aq = AutogenQuery(
            query_text=query_text,
            gold_cluster_ids=cluster,
            source_uuid=node.uuid,
            source_text_sha256=_sha256(node.text),
            namespace=node.namespace,
            stratum=stratum_of(node),
        )
        result.cluster_sizes.append(len(cluster))
        if looks_like_leak(query_text, node):
            result.leaked.append(aq)
        else:
            result.queries.append(aq)
    return result
