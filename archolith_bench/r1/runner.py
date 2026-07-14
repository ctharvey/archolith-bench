"""R1 condition ladder + win gate.

Ladder (deferred-verification.md):
    A_current            today's fused recall (the baseline to beat)
    E_hybrid_a{alpha}    attributed hybrid (vector+BM25, source-aware floor),
                         swept over hybrid_alpha. alpha=1.0 is vector-only (B),
                         alpha=0.0 is BM25-only (D) — the sweep endpoints.

The runner is retriever-agnostic: hand it ``{condition: Retriever}``. Build the
stub conditions with ``build_stub_conditions`` (CI), or wire ``MenhirLiveRetriever``
instances for the live run. Metrics are computed identically for every condition.

Win gate (R1 headline, recalibrated 2026-07-05): an E config GRADUATES if it
strictly beats A_current on every UNSATURATED improvement metric (``exact_string_recall``
/ ``symbol_recall`` whose baseline is below the saturation ceiling, so there is headroom
to beat) WITHOUT regressing a saturated improvement metric, ``stale_hit_rate``, or
``wrong_scope_injection_rate`` (within tolerance). A metric already saturated at the
baseline (e.g. ``exact_string_recall`` = 1.0 on the real corpus, where graphiti's internal
RRF already fuses BM25 + cosine) is EXEMPT from the must-beat test -- requiring a win on a
metric with no headroom was a gate-calibration artifact that could never fire. The graduating
alpha that maximizes exact+symbol recall is the recommended ``hybrid_alpha``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import metrics as M
from .models import R1Fixture
from .retriever import Retriever, StubRetriever

ALPHA_SWEEP: tuple[float, ...] = (0.0, 0.25, 0.5, 0.75, 1.0)
BASELINE_CONDITION = "A_current"
DEFAULT_K = 5

# Higher-is-better recall metrics eligible to earn graduation. A metric already at
# or above SATURATION_CEILING at the baseline has no headroom to beat, so it is exempt
# from the "must beat" test (but still may not regress). Recalibrated 2026-07-05: the
# real dummy-gold corpus saturates exact_string_recall at 1.0 (graphiti's internal RRF
# already fuses BM25 + cosine), which the old "beat exact AND symbol" gate could never
# clear -- see archolith-bench/.agent/benchmark-notes/r1-dummy-gold-run.md.
IMPROVEMENT_METRICS: tuple[str, ...] = ("exact_string_recall", "symbol_recall")
SATURATION_CEILING: float = 1.0


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


# Guards that must not WORSEN. Direction matters: a guard can be lower-is-better
# (an error rate) or higher-is-better (a recall metric the challenger must not trade away).
DEFAULT_GUARDS_LOWER_IS_BETTER: tuple[str, ...] = (
    "stale_hit_rate",
    "wrong_scope_injection_rate",
)
DEFAULT_GUARDS_HIGHER_IS_BETTER: tuple[str, ...] = ()


def evaluate_win_gate(
    results: dict[str, ConditionResult],
    regress_tolerance: float = 0.0,
    saturation_ceiling: float = SATURATION_CEILING,
    *,
    baseline_condition: str = BASELINE_CONDITION,
    challenger_prefix: str = "E_",
    primary_improvement_metrics: tuple[str, ...] = IMPROVEMENT_METRICS,
    improvement_mode: str = "all",
    guards_lower_is_better: tuple[str, ...] = DEFAULT_GUARDS_LOWER_IS_BETTER,
    guards_higher_is_better: tuple[str, ...] = DEFAULT_GUARDS_HIGHER_IS_BETTER,
) -> dict:
    """Decide whether any challenger condition beats the baseline.

    Graduation: the challenger improves the UNSATURATED primary metrics (those in
    ``primary_improvement_metrics`` whose baseline is below ``saturation_ceiling``)
    per ``improvement_mode``, does not regress any primary metric (eligible or
    saturated), and does not worsen any guard -- all within ``regress_tolerance``.
    A metric already saturated at the baseline is exempt from the must-beat test (no
    headroom), so the gate never demands the impossible ``exact > 1.0``.

    ``improvement_mode`` selects the quantifier over the eligible primary metrics:

    - ``"all"`` (default, preserves historical R1 behavior): the challenger must
      strictly beat EVERY eligible metric. Appropriate when the primaries are
      INDEPENDENT (e.g. ``exact_string_recall`` vs ``symbol_recall``), where
      demanding both is a defensible strict gate.

    - ``"any"``: the challenger must beat AT LEAST ONE eligible metric and regress
      NONE. Required when the primaries are NESTED or otherwise correlated, where
      "all" is unsatisfiable even by a genuine win. Concretely: ``recall@5`` and
      ``recall@10`` are nested, so a gold moving from rank 6 to rank 2 improves
      ``recall@5`` and MRR but leaves ``recall@10`` UNCHANGED -- under ``"all"`` the
      conjunction fails and a real improvement is rejected, and the caller then
      wrongly concludes the change was redundant. Use ``"any"`` for nested metric
      families.

    Defaults reproduce the previous behavior exactly for existing callers.
    """
    if baseline_condition not in results:
        return {"graduates": False, "reason": f"missing {baseline_condition} baseline"}
    if improvement_mode not in ("all", "any"):
        raise ValueError(f'improvement_mode must be "all" or "any", got {improvement_mode!r}')
    base = results[baseline_condition].metrics
    e_names = [n for n in results if n.startswith(challenger_prefix)]

    # Fail loudly on a metric the gate is configured to consult but that the run did not
    # produce. This must NOT be softened to a .get(0.0) default: a guard that silently
    # evaluates to 0.0 is a guard that silently guards NOTHING, which is precisely the
    # failure a guard exists to prevent.
    configured = (
        *primary_improvement_metrics,
        *guards_lower_is_better,
        *guards_higher_is_better,
    )
    missing = [k for k in configured if k not in base]
    if missing:
        raise ValueError(
            f"win gate configured with metric(s) {missing} that the run did not produce "
            f"(baseline {baseline_condition!r} has {sorted(base)}). Fix the metric set or the "
            f"gate configuration -- a missing guard would otherwise pass vacuously."
        )

    # Split the primary metrics into those with headroom (eligible to earn a win)
    # and those already maxed at the baseline (exempt from must-beat, must not regress).
    eligible = [k for k in primary_improvement_metrics if base[k] < saturation_ceiling]
    saturated = [k for k in primary_improvement_metrics if base[k] >= saturation_ceiling]

    quantifier = all if improvement_mode == "all" else any

    evaluated: list[dict] = []
    winners: list[dict] = []
    for name in e_names:
        m = results[name].metrics
        # Per-metric flags kept for artifact readability / backward compatibility.
        beats_exact = m.get("exact_string_recall", 0.0) > base.get("exact_string_recall", 0.0)
        beats_symbol = m.get("symbol_recall", 0.0) > base.get("symbol_recall", 0.0)
        # Improvement over the metrics that have headroom. If none has headroom
        # (all saturated) there is nothing to demonstrate a win on -> cannot graduate.
        beats_eligible = bool(eligible) and quantifier(m[k] > base[k] for k in eligible)
        # Under "any", beating one eligible metric must not come at the cost of another,
        # so eligible metrics also carry a non-regression duty. Under "all" this is
        # implied (every eligible strictly improves) and the check is a no-op.
        no_eligible_regression = all(
            m[k] >= base[k] - regress_tolerance for k in eligible
        )
        # A saturated metric may not slip (e.g. don't drop exact from 1.0 to win symbol).
        no_saturated_regression = all(
            m[k] >= base[k] - regress_tolerance for k in saturated
        )
        guards_ok = all(
            m[k] <= base[k] + regress_tolerance for k in guards_lower_is_better
        ) and all(
            m[k] >= base[k] - regress_tolerance for k in guards_higher_is_better
        )
        # Retained for artifact readability; subsumed by guards_ok.
        stale_ok = m.get("stale_hit_rate", 0.0) <= base.get("stale_hit_rate", 0.0) + regress_tolerance
        scope_ok = (
            m.get("wrong_scope_injection_rate", 0.0)
            <= base.get("wrong_scope_injection_rate", 0.0) + regress_tolerance
        )
        wins = (
            beats_eligible
            and no_eligible_regression
            and no_saturated_regression
            and guards_ok
        )
        entry = {
            "condition": name,
            "beats_exact": beats_exact,
            "beats_symbol": beats_symbol,
            "beats_eligible": beats_eligible,
            "no_eligible_regression": no_eligible_regression,
            "no_saturated_regression": no_saturated_regression,
            "no_stale_regression": stale_ok,
            "no_scope_regression": scope_ok,
            "guards_ok": guards_ok,
            "wins": wins,
        }
        # Report every metric the gate actually consulted, whatever it was configured with.
        # (The four legacy keys below are retained verbatim for artifact/back-compat; they
        # are absent-safe so a caller with a different metric set does not KeyError.)
        for key in (
            *primary_improvement_metrics,
            *guards_lower_is_better,
            *guards_higher_is_better,
            "exact_string_recall",
            "symbol_recall",
            "stale_hit_rate",
            "wrong_scope_injection_rate",
        ):
            if key in m:
                entry[key] = m[key]
        evaluated.append(entry)
        if wins:
            winners.append(entry)

    def _primary_sum(e: dict) -> float:
        return sum(e.get(k, 0.0) for k in primary_improvement_metrics)

    def _guard_penalty(e: dict) -> float:
        # Lower-is-better guards count against; higher-is-better guards count for.
        return sum(e.get(k, 0.0) for k in guards_lower_is_better) - sum(
            e.get(k, 0.0) for k in guards_higher_is_better
        )

    recommended = None
    if winners:
        # Best primary total, then least guard damage, then name (stable).
        winners.sort(key=lambda e: (-_primary_sum(e), _guard_penalty(e), e["condition"]))
        recommended = winners[0]["condition"]

    gate = {
        "graduates": bool(winners),
        "recommended_condition": recommended,
        "recommended_hybrid_alpha": _alpha_of(recommended),
        "eligible_metrics": eligible,
        "saturated_metrics": saturated,
        "improvement_mode": improvement_mode,
        "primary_improvement_metrics": list(primary_improvement_metrics),
        "guards_lower_is_better": list(guards_lower_is_better),
        "guards_higher_is_better": list(guards_higher_is_better),
        "baseline": {
            key: base[key]
            for key in (
                *primary_improvement_metrics,
                *guards_lower_is_better,
                *guards_higher_is_better,
                "exact_string_recall",
                "symbol_recall",
                "stale_hit_rate",
                "wrong_scope_injection_rate",
            )
            if key in base
        },
        "evaluated": evaluated,
        "regress_tolerance": regress_tolerance,
        "saturation_ceiling": saturation_ceiling,
    }
    if not eligible:
        gate["reason"] = (
            f"no unsaturated improvement metric: every metric in "
            f"{list(primary_improvement_metrics)} is >= {saturation_ceiling} at baseline, "
            f"so there is no headroom to earn a win"
        )
    return gate


def _alpha_of(condition: str | None) -> float | None:
    if not condition or "_a" not in condition:
        return None
    try:
        return float(condition.rsplit("_a", 1)[1])
    except ValueError:
        return None


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0
