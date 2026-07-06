"""Condition ladder runner for the facet benchmark (menhir R2).

Runs the honest-baseline ladder over a `FacetFixture`, in both facet modes:

    A  BM25
    B  embedding top-k            (pluggable; offline stand-in by default)
    C  BM25 + embedding (RRF)
    D  existing graph/file-context (stand-in: file/symbol overlap)
    E  facet index + embedding rerank
    F  facet index + meet-point rerank

Three facet modes are kept strictly separate (R2 Risk #2):
- gold       — memories use their hand-authored facets.
- extracted  — memories use `FacetExtractor` output instead (regex/vocab over prose).
- hybrid     — deterministic facets (file/symbol/test/scope/time/bucket) read from
               structure/Git (gold stand-in); only interpretive facets extracted from
               text. The realistic case (facet-extraction-plan.md, Priority 6).

In both modes the *query* facets stay gold, and all correctness (stale /
wrong-scope / support) is judged against the **gold** corpus — the extractor only
changes what the retriever sees, never the ground truth.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field

from . import metrics as M
from .baselines import (
    BM25,
    EmbeddingScorer,
    LexicalEmbeddingStub,
    file_context_rank,
    rank_from_scores,
    rrf_fuse,
)
from .extractor import ExtractorConfig, FacetExtractor
from .index import MemoryFacetIndex
from .models import FacetFixture, Memory, Query
from .reranker import MeetPointReranker, MeetPointWeights

CONDITIONS: tuple[str, ...] = ("A_bm25", "B_embedding", "C_hybrid", "D_file_context", "E_facet_embed", "F_facet_meet")
BASELINE_CONDITIONS: tuple[str, ...] = ("A_bm25", "B_embedding", "C_hybrid")
FACET_MODES: tuple[str, ...] = ("gold", "extracted", "hybrid")
DEFAULT_K = 5


@dataclass
class QueryConditionResult:
    query_id: str
    ranked: list[str]
    latency_ms: float
    trace: list[dict] = field(default_factory=list)


@dataclass
class ConditionResult:
    condition: str
    facet_mode: str
    metrics: dict[str, float]
    per_query: list[QueryConditionResult] = field(default_factory=list)


class FacetBenchmarkRunner:
    """Execute the facet ladder over a fixture and assemble a run artifact."""

    def __init__(
        self,
        fixture: FacetFixture,
        embedder: EmbeddingScorer | None = None,
        weights: MeetPointWeights | None = None,
        extractor: FacetExtractor | None = None,
        k: int = DEFAULT_K,
        corpus_transform: Callable[[list[Memory]], list[Memory]] | None = None,
    ) -> None:
        self.fixture = fixture
        self.embedder = embedder or LexicalEmbeddingStub()
        self.reranker = MeetPointReranker(weights)
        self.extractor = extractor or FacetExtractor(_infer_extractor_config(fixture))
        self.k = k
        # Optional post-mode corpus transform (e.g. anchor-noise / hygiene, gate b). None ==
        # today's behavior. Correctness is still judged against the untouched gold corpus.
        self.corpus_transform = corpus_transform
        self.gold_by_id = fixture.memories_by_id

    # -- corpus views -------------------------------------------------------
    def _corpus_for_mode(self, mode: str) -> list[Memory]:
        if mode == "gold":
            corpus = self.fixture.memories
        elif mode == "extracted":
            corpus = [self.extractor.extract_memory(m) for m in self.fixture.memories]
        elif mode == "hybrid":
            corpus = [self.extractor.extract_memory_hybrid(m) for m in self.fixture.memories]
        else:
            raise ValueError(f"unknown facet mode: {mode}")
        return self.corpus_transform(corpus) if self.corpus_transform else corpus

    # -- per-condition rankers ---------------------------------------------
    def _rank(
        self,
        condition: str,
        query: Query,
        corpus: list[Memory],
        index: MemoryFacetIndex,
        corpus_by_id: dict[str, Memory],
    ) -> tuple[list[str], list[dict]]:
        if condition == "A_bm25":
            return rank_from_scores(BM25(corpus).score(query.text)), []
        if condition == "B_embedding":
            return rank_from_scores(self.embedder.score(query.text, corpus)), []
        if condition == "C_hybrid":
            bm25_rank = rank_from_scores(BM25(corpus).score(query.text))
            embed_rank = rank_from_scores(self.embedder.score(query.text, corpus))
            return rrf_fuse([bm25_rank, embed_rank]), []
        if condition == "D_file_context":
            return file_context_rank(query, corpus), []
        if condition == "E_facet_embed":
            candidate_ids = set(index.candidate_ids(query.facets))
            candidates = [m for m in corpus if m.id in candidate_ids]
            scores = self.embedder.score(query.text, candidates)
            return rank_from_scores(scores), []
        if condition == "F_facet_meet":
            candidate_ids = index.candidate_ids(query.facets)
            explanations = self.reranker.rerank(query, candidate_ids, corpus_by_id)
            return [e.memory_id for e in explanations], [e.to_dict() for e in explanations]
        raise ValueError(f"unknown condition: {condition}")

    def run_condition(self, condition: str, mode: str) -> ConditionResult:
        corpus = self._corpus_for_mode(mode)
        corpus_by_id = {m.id: m for m in corpus}
        index = MemoryFacetIndex().build(corpus)

        per_query: list[QueryConditionResult] = []
        top_k_by_query: dict[str, list[str]] = {}
        for query in self.fixture.queries:
            start = time.perf_counter()
            ranked, trace = self._rank(condition, query, corpus, index, corpus_by_id)
            latency_ms = (time.perf_counter() - start) * 1000.0
            per_query.append(
                QueryConditionResult(query_id=query.id, ranked=ranked, latency_ms=latency_ms, trace=trace)
            )
            top_k_by_query[query.id] = ranked

        agg = self._aggregate(per_query, top_k_by_query)
        return ConditionResult(condition=condition, facet_mode=mode, metrics=agg, per_query=per_query)

    def _aggregate(
        self, per_query: list[QueryConditionResult], top_k_by_query: dict[str, list[str]]
    ) -> dict[str, float]:
        k = self.k
        queries_by_id = {q.id: q for q in self.fixture.queries}
        sums: dict[str, float] = {
            "recall_at_5": 0.0,
            "precision_at_5": 0.0,
            "mrr": 0.0,
            "ndcg_at_5": 0.0,
            "stale_hit_rate": 0.0,
            "wrong_scope_injection_rate": 0.0,
            "support_sufficiency": 0.0,
            "false_neighbor_rate": 0.0,
            "latency_ms": 0.0,
        }
        n = len(per_query) or 1
        for result in per_query:
            query = queries_by_id[result.query_id]
            ranked = result.ranked
            support = query.support_ids
            sums["recall_at_5"] += M.recall_at_k(ranked, support, k)
            sums["precision_at_5"] += M.precision_at_k(ranked, support, k)
            sums["mrr"] += M.mrr(ranked, support)
            sums["ndcg_at_5"] += M.ndcg_at_k(ranked, support, k)
            sums["stale_hit_rate"] += M.stale_hit_rate(ranked, self.gold_by_id, query, k)
            sums["wrong_scope_injection_rate"] += M.wrong_scope_injection_rate(ranked, self.gold_by_id, query, k)
            sums["support_sufficiency"] += M.support_sufficiency(ranked, support, k)
            sums["false_neighbor_rate"] += M.false_neighbor_rate(ranked, self.gold_by_id, query, k)
            sums["latency_ms"] += result.latency_ms
        agg = {name: round(total / n, 4) for name, total in sums.items()}
        agg["paraphrase_stability"] = round(
            M.paraphrase_stability(top_k_by_query, self.fixture.queries, k), 4
        )
        return agg

    def run(self, include_traces: bool = True) -> dict:
        """Run every condition in every mode and return a JSON-able artifact."""
        results: dict[str, dict[str, ConditionResult]] = {}
        for mode in FACET_MODES:
            results[mode] = {cond: self.run_condition(cond, mode) for cond in CONDITIONS}

        artifact: dict = {
            "fixture": self.fixture.name,
            "description": self.fixture.description,
            "config": {
                "k": self.k,
                "embedder": getattr(self.embedder, "name", type(self.embedder).__name__),
                "meet_point_weights": asdict(self.reranker.weights),
                "n_memories": len(self.fixture.memories),
                "n_queries": len(self.fixture.queries),
            },
            "modes": {},
            "promotion_gate": {},
        }
        for mode, cond_results in results.items():
            artifact["modes"][mode] = {
                cond: _condition_to_dict(res, include_traces) for cond, res in cond_results.items()
            }
            artifact["promotion_gate"][mode] = evaluate_promotion_gate(cond_results)
        return artifact


def evaluate_promotion_gate(
    cond_results: dict[str, ConditionResult], recall_tolerance: float = 0.10
) -> dict:
    """Decide whether F (facet + meet-point) graduates against the baselines.

    Gate (from the R2 plan): F improves `stale_hit_rate`, `wrong_scope_injection_rate`,
    **or** `support_sufficiency` versus the best of BM25 / embedding / hybrid,
    **without** an unacceptable recall loss (recall@5 within `recall_tolerance` of
    the best baseline).
    """
    f = cond_results["F_facet_meet"].metrics
    baselines = [cond_results[c].metrics for c in BASELINE_CONDITIONS]

    best_stale = min(b["stale_hit_rate"] for b in baselines)
    best_wrong = min(b["wrong_scope_injection_rate"] for b in baselines)
    best_support = max(b["support_sufficiency"] for b in baselines)
    best_recall = max(b["recall_at_5"] for b in baselines)

    improvements = {
        "stale_hit_rate": round(best_stale - f["stale_hit_rate"], 4),
        "wrong_scope_injection_rate": round(best_wrong - f["wrong_scope_injection_rate"], 4),
        "support_sufficiency": round(f["support_sufficiency"] - best_support, 4),
    }
    improved = {name: delta > 0 for name, delta in improvements.items()}
    recall_loss = round(best_recall - f["recall_at_5"], 4)
    recall_acceptable = recall_loss <= recall_tolerance

    graduates = any(improved.values()) and recall_acceptable
    return {
        "graduates": graduates,
        "improved_any": any(improved.values()),
        "recall_loss": recall_loss,
        "recall_acceptable": recall_acceptable,
        "recall_tolerance": recall_tolerance,
        "improvements_vs_best_baseline": improvements,
        "improved": improved,
        "baseline_reference": {
            "best_stale_hit_rate": best_stale,
            "best_wrong_scope_injection_rate": best_wrong,
            "best_support_sufficiency": best_support,
            "best_recall_at_5": best_recall,
        },
    }


def _condition_to_dict(result: ConditionResult, include_traces: bool) -> dict:
    per_query = []
    for q in result.per_query:
        entry = {"query_id": q.query_id, "ranked": q.ranked, "latency_ms": round(q.latency_ms, 4)}
        if include_traces and q.trace:
            entry["trace"] = q.trace
        per_query.append(entry)
    return {"condition": result.condition, "facet_mode": result.facet_mode, "metrics": result.metrics, "per_query": per_query}


def _infer_extractor_config(fixture: FacetFixture) -> ExtractorConfig:
    """Seed extractor vocab from the gold scope facets present in the fixture.

    Repos / projects / namespaces can't be guessed from free text, so the
    extractor is given the closed set that actually appears in the corpus — a
    deterministic, fixture-local vocabulary, not an external knowledge base.
    """
    repos: set[str] = set()
    projects: set[str] = set()
    namespaces: set[str] = set()
    for memory in fixture.memories:
        if memory.facets.repo:
            repos.add(memory.facets.repo)
        if memory.facets.project:
            projects.add(memory.facets.project)
        if memory.facets.namespace:
            namespaces.add(memory.facets.namespace)
    return ExtractorConfig(
        repos=tuple(sorted(repos)),
        projects=tuple(sorted(projects)),
        namespaces=tuple(sorted(namespaces)),
    )
