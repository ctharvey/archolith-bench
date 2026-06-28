"""Condition ladder runner for the oracle benchmark (menhir R4-R7).

The killer-baseline question, made falsifiable:

    A_semantic   single-signal baseline (semantic oracle only)
    E_weighted   one-pass weighted sum of all cheap oracles            (ladder E)
    F_logspace   one-pass role-specific log-space oracle combiner       (ladder F, R7)

Does combining oracles (E) beat a single semantic signal (A)? And does the
log-space role-logit combiner (F) beat the naive weighted sum (E) on the metrics
the oracle layer exists to move — stale-hit, wrong-scope, current-truth
suppression — without unacceptable recall loss?

Bench-first: nothing here touches menhir production. The semantic oracle is a
deterministic lexical stand-in; swap a real embedder before quoting A/E/F as an
embedding comparison.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from . import metrics as M
from .combiner import LogSpaceOracleCombiner, WeightedOracleCombiner
from .executor import OracleExecutor
from .models import OracleFixture, OracleQuery
from .oracles import RetrievalOracle, SemanticOracle, default_oracles

CONDITIONS: tuple[str, ...] = ("A_semantic", "E_weighted", "F_logspace")
BASELINE_CONDITIONS: tuple[str, ...] = ("A_semantic", "E_weighted")
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
    metrics: dict[str, float]
    per_query: list[QueryConditionResult] = field(default_factory=list)


class OracleBenchmarkRunner:
    """Execute the oracle ladder over a fixture and assemble a run artifact."""

    def __init__(
        self,
        fixture: OracleFixture,
        oracles: list[RetrievalOracle] | None = None,
        k: int = DEFAULT_K,
    ) -> None:
        self.fixture = fixture
        self.oracles = oracles or default_oracles()
        self.executor = OracleExecutor(self.oracles)
        self.weighted = WeightedOracleCombiner()
        self.logspace = LogSpaceOracleCombiner()
        self.k = k
        self.by_id = fixture.memories_by_id
        self.candidates = [m.to_candidate() for m in fixture.memories]

    def _rank(self, condition: str, query: OracleQuery) -> tuple[list[str], list[dict]]:
        ctx = query.to_context()
        if condition == "A_semantic":
            sem = SemanticOracle()
            scored = [(c.id, sem.evaluate(ctx, c).probability) for c in self.candidates]
            ranked = [cid for cid, _ in sorted(scored, key=lambda kv: (-kv[1], kv[0]))]
            return ranked, []
        grouped = self.executor.evaluate(ctx, self.candidates)
        combiner = self.weighted if condition == "E_weighted" else self.logspace
        ranked, packets = combiner.rank(ctx, grouped)
        trace = [packets[cid].to_dict() for cid in ranked[: self.k]]
        return ranked, trace

    def run_condition(self, condition: str) -> ConditionResult:
        per_query: list[QueryConditionResult] = []
        for query in self.fixture.queries:
            start = time.perf_counter()
            ranked, trace = self._rank(condition, query)
            latency_ms = (time.perf_counter() - start) * 1000.0
            per_query.append(QueryConditionResult(query.id, ranked, latency_ms, trace))
        return ConditionResult(condition, self._aggregate(condition, per_query), per_query)

    def _aggregate(self, condition: str, per_query: list[QueryConditionResult]) -> dict[str, float]:
        k = self.k
        queries_by_id = {q.id: q for q in self.fixture.queries}
        sums = {
            "recall_at_5": 0.0, "precision_at_5": 0.0, "mrr": 0.0, "ndcg_at_5": 0.0,
            "stale_hit_rate": 0.0, "wrong_scope_injection_rate": 0.0,
            "current_truth_suppression_accuracy": 0.0, "historical_context_preservation": 0.0,
            "latency_ms": 0.0,
        }
        n = len(per_query) or 1
        for result in per_query:
            query = queries_by_id[result.query_id]
            ranked, support = result.ranked, query.support_ids
            sums["recall_at_5"] += M.recall_at_k(ranked, support, k)
            sums["precision_at_5"] += M.precision_at_k(ranked, support, k)
            sums["mrr"] += M.mrr(ranked, support)
            sums["ndcg_at_5"] += M.ndcg_at_k(ranked, support, k)
            sums["stale_hit_rate"] += M.stale_hit_rate(ranked, self.by_id, query, k)
            sums["wrong_scope_injection_rate"] += M.wrong_scope_injection_rate(ranked, self.by_id, query, k)
            sums["current_truth_suppression_accuracy"] += M.current_truth_suppression_accuracy(ranked, self.by_id, query, k)
            sums["historical_context_preservation"] += M.historical_context_preservation(ranked, support, query, k)
            sums["latency_ms"] += result.latency_ms
        agg = {name: round(total / n, 4) for name, total in sums.items()}
        agg["ranking_determinism"] = self._determinism(condition)
        return agg

    def _determinism(self, condition: str) -> float:
        """1.0 iff a re-run produces identical rankings (parallel-safety guard)."""
        for query in self.fixture.queries:
            first, _ = self._rank(condition, query)
            second, _ = self._rank(condition, query)
            if first != second:
                return 0.0
        return 1.0

    def run(self, include_traces: bool = True) -> dict:
        results = {cond: self.run_condition(cond) for cond in CONDITIONS}
        artifact = {
            "fixture": self.fixture.name,
            "description": self.fixture.description,
            "config": {
                "k": self.k,
                "oracles": [o.name for o in self.oracles],
                "n_memories": len(self.fixture.memories),
                "n_queries": len(self.fixture.queries),
            },
            "conditions": {
                cond: _condition_to_dict(res, include_traces) for cond, res in results.items()
            },
            "promotion_gate": evaluate_promotion_gate(results),
        }
        return artifact


def evaluate_promotion_gate(results: dict[str, ConditionResult], recall_tolerance: float = 0.10) -> dict:
    """Decide whether F (log-space role logits) graduates against the baselines.

    Gate: F improves `stale_hit_rate`, `wrong_scope_injection_rate`, **or**
    `current_truth_suppression_accuracy` versus the best of {A_semantic, E_weighted},
    **without** recall@5 falling more than `recall_tolerance` below the best baseline.
    """
    f = results["F_logspace"].metrics
    baselines = [results[c].metrics for c in BASELINE_CONDITIONS]

    best_stale = min(b["stale_hit_rate"] for b in baselines)
    best_wrong = min(b["wrong_scope_injection_rate"] for b in baselines)
    best_suppress = max(b["current_truth_suppression_accuracy"] for b in baselines)
    best_recall = max(b["recall_at_5"] for b in baselines)

    improvements = {
        "stale_hit_rate": round(best_stale - f["stale_hit_rate"], 4),
        "wrong_scope_injection_rate": round(best_wrong - f["wrong_scope_injection_rate"], 4),
        "current_truth_suppression_accuracy": round(f["current_truth_suppression_accuracy"] - best_suppress, 4),
    }
    improved = {name: delta > 0 for name, delta in improvements.items()}
    recall_loss = round(best_recall - f["recall_at_5"], 4)
    recall_acceptable = recall_loss <= recall_tolerance
    return {
        "graduates": any(improved.values()) and recall_acceptable,
        "improved_any": any(improved.values()),
        "recall_loss": recall_loss,
        "recall_acceptable": recall_acceptable,
        "recall_tolerance": recall_tolerance,
        "improvements_vs_best_baseline": improvements,
        "improved": improved,
        "baseline_reference": {
            "best_stale_hit_rate": best_stale,
            "best_wrong_scope_injection_rate": best_wrong,
            "best_current_truth_suppression_accuracy": best_suppress,
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
    return {"condition": result.condition, "metrics": result.metrics, "per_query": per_query}
