"""R1 condition ladder + win gate.

Ladder (deferred-verification.md):
    A_current            today's fused recall (the baseline to beat)
    E_hybrid_a{alpha}    attributed hybrid (vector+BM25, source-aware floor),
                         swept over hybrid_alpha. alpha=1.0 is vector-only (B),
                         alpha=0.0 is BM25-only (D) — the sweep endpoints.

The runner is retriever-agnostic: hand it ``{condition: Retriever}``. Build the
stub conditions with ``build_stub_conditions`` (CI), or wire ``MenhirLiveRetriever``
instances for the live run. Metrics are computed identically for every condition.

Win gate (R1 headline): an E config GRADUATES if it beats A_current on BOTH
``exact_string_recall`` and ``symbol_recall`` WITHOUT regressing ``stale_hit_rate``
or ``wrong_scope_injection_rate`` (within tolerance). The graduating alpha that
maximizes exact+symbol recall is the recommended ``hybrid_alpha``.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from . import metrics as M
from .models import R1Fixture, R1Query
from .retriever import Retriever, StubRetriever

ALPHA_SWEEP: tuple[float, ...] = (0.0, 0.25, 0.5, 0.75, 1.0)
BASELINE_CONDITION = "A_current"
DEFAULT_K = 5


def build_stub_conditions(
    fixture: R1Fixture, alpha_sweep: tuple[float, ...] = ALPHA_SWEEP
) -> dict[str, Retriever]:
    """Stub ladder: A_current (fused, no source-aware floor) + the E alpha sweep."""
    conditions: dict[str, Retriever] = {
        BASELINE_CONDITION: StubRetriever(
            fixture, alpha=0.5, source_aware=False, name=BASELINE_CONDITION
        )
    }
    for alpha in alpha_sweep:
        name = f"E_hybrid_a{alpha:g}"
        conditions[name] = StubRetriever(fixture, alpha=alpha, source_aware=True, name=name)
    return conditions


@dataclass
class ConditionResult:
    condition: str
    metrics: dict[str, float]
    per_query: dict[str, list[str]] = field(default_factory=dict)


class R1BenchmarkRunner:
    """Run the R1 ladder over a fixture and assemble a JSON-able artifact."""

    def __init__(self, fixture: R1Fixture, conditions: dict[str, Retriever], k: int = DEFAULT_K) -> None:
        self.fixture = fixture
        self.conditions = conditions
        self.k = k
        self.memories_by_id = fixture.memories_by_id

    def run_condition(self, name: str, retriever: Retriever) -> ConditionResult:
        ranked_by_query: dict[str, list[str]] = {}
        latencies: list[float] = []
        for query in self.fixture.queries:
            result = retriever.rank(query, self.k)
            ranked_by_query[query.id] = result.ranked_ids
            latencies.append(result.latency_ms)
        agg = self._aggregate(ranked_by_query, latencies)
        return ConditionResult(condition=name, metrics=agg, per_query=ranked_by_query)

    def _aggregate(
        self, ranked_by_query: dict[str, list[str]], latencies: list[float]
    ) -> dict[str, float]:
        return aggregate_metrics(self.fixture, ranked_by_query, latencies, self.k)

    def run(self) -> dict:
        results = {name: self.run_condition(name, r) for name, r in self.conditions.items()}
        gate = evaluate_win_gate(results)
        return {
            "fixture": self.fixture.name,
            "description": self.fixture.description,
            "config": {
                "k": self.k,
                "n_memories": len(self.fixture.memories),
                "n_queries": len(self.fixture.queries),
                "conditions": list(self.conditions),
            },
            "conditions": {
                name: {"metrics": res.metrics, "per_query": res.per_query}
                for name, res in results.items()
            },
            "win_gate": gate,
        }


def aggregate_metrics(
    fixture: R1Fixture,
    ranked_by_query: dict[str, list[str]],
    latencies: list[float],
    k: int = DEFAULT_K,
) -> dict[str, float]:
    """Compute the six headline R1 metrics (+ per-family recall) for one condition.

    Shared by the stub runner and the live driver so both score identically.
    exact_string_recall / symbol_recall average only over the queries that target
    an exact string / symbol.
    """
    queries_by_id = {q.id: q for q in fixture.queries}
    memories_by_id = fixture.memories_by_id
    n = len(fixture.queries) or 1

    recall = stale = wrong = 0.0
    exact_hits: list[float] = []
    symbol_hits: list[float] = []
    family_recall: dict[str, list[float]] = {}

    for qid, ranked in ranked_by_query.items():
        q = queries_by_id[qid]
        recall += M.recall_at_k(ranked, q.support_ids, k)
        stale += M.stale_hit_rate(ranked, memories_by_id, q, k)
        wrong += M.wrong_scope_injection_rate(ranked, memories_by_id, q, k)

        es = M.exact_string_hit(ranked, memories_by_id, q, k)
        if es is not None:
            exact_hits.append(es)
        sy = M.symbol_hit(ranked, memories_by_id, q, k)
        if sy is not None:
            symbol_hits.append(sy)

        family_recall.setdefault(q.family, []).append(M.recall_at_k(ranked, q.support_ids, k))

    agg = {
        "recall_at_5": round(recall / n, 4),
        "exact_string_recall": round(_mean(exact_hits), 4),
        "symbol_recall": round(_mean(symbol_hits), 4),
        "stale_hit_rate": round(stale / n, 4),
        "wrong_scope_injection_rate": round(wrong / n, 4),
        "latency_ms": round(_mean(latencies), 4),
    }
    for family, vals in family_recall.items():
        agg[f"recall_at_5__{family}"] = round(_mean(vals), 4)
    return agg


def evaluate_win_gate(
    results: dict[str, ConditionResult], regress_tolerance: float = 0.0
) -> dict:
    """Decide whether any E (hybrid) config beats the A_current baseline.

    Graduation: E beats A on BOTH exact_string_recall and symbol_recall AND does
    not regress stale_hit_rate / wrong_scope_injection_rate by more than
    ``regress_tolerance``. The graduating alpha maximizing exact+symbol recall is
    recommended.
    """
    if BASELINE_CONDITION not in results:
        return {"graduates": False, "reason": f"missing {BASELINE_CONDITION} baseline"}
    base = results[BASELINE_CONDITION].metrics
    e_names = [n for n in results if n.startswith("E_")]

    evaluated: list[dict] = []
    winners: list[dict] = []
    for name in e_names:
        m = results[name].metrics
        beats_exact = m["exact_string_recall"] > base["exact_string_recall"]
        beats_symbol = m["symbol_recall"] > base["symbol_recall"]
        stale_ok = m["stale_hit_rate"] <= base["stale_hit_rate"] + regress_tolerance
        scope_ok = (
            m["wrong_scope_injection_rate"]
            <= base["wrong_scope_injection_rate"] + regress_tolerance
        )
        wins = beats_exact and beats_symbol and stale_ok and scope_ok
        entry = {
            "condition": name,
            "beats_exact": beats_exact,
            "beats_symbol": beats_symbol,
            "no_stale_regression": stale_ok,
            "no_scope_regression": scope_ok,
            "wins": wins,
            "exact_string_recall": m["exact_string_recall"],
            "symbol_recall": m["symbol_recall"],
            "stale_hit_rate": m["stale_hit_rate"],
            "wrong_scope_injection_rate": m["wrong_scope_injection_rate"],
        }
        evaluated.append(entry)
        if wins:
            winners.append(entry)

    recommended = None
    if winners:
        winners.sort(
            key=lambda e: (
                -(e["exact_string_recall"] + e["symbol_recall"]),
                e["stale_hit_rate"] + e["wrong_scope_injection_rate"],
                e["condition"],
            )
        )
        recommended = winners[0]["condition"]

    return {
        "graduates": bool(winners),
        "recommended_condition": recommended,
        "recommended_hybrid_alpha": _alpha_of(recommended),
        "baseline": {
            "exact_string_recall": base["exact_string_recall"],
            "symbol_recall": base["symbol_recall"],
            "stale_hit_rate": base["stale_hit_rate"],
            "wrong_scope_injection_rate": base["wrong_scope_injection_rate"],
        },
        "evaluated": evaluated,
        "regress_tolerance": regress_tolerance,
    }


def _alpha_of(condition: str | None) -> float | None:
    if not condition or "_a" not in condition:
        return None
    try:
        return float(condition.rsplit("_a", 1)[1])
    except ValueError:
        return None


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0
