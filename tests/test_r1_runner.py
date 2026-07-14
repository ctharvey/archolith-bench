"""Tests for the R1 ladder runner and win gate."""

from __future__ import annotations

from pathlib import Path

from archolith_bench.r1.models import R1Fixture, R1Memory, R1Query
from archolith_bench.r1.runner import (
    ConditionResult,
    R1BenchmarkRunner,
    build_stub_conditions,
    evaluate_win_gate,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
DEMO = REPO_ROOT / "fixtures" / "r1_demo.json"


def _cr(name: str, *, exact: float, symbol: float, stale: float, scope: float) -> ConditionResult:
    return ConditionResult(
        condition=name,
        metrics={
            "recall_at_5": 1.0,
            "exact_string_recall": exact,
            "symbol_recall": symbol,
            "stale_hit_rate": stale,
            "wrong_scope_injection_rate": scope,
            "latency_ms": 0.0,
        },
    )


# --- win gate --------------------------------------------------------------


def test_gate_graduates_when_e_beats_both_without_regression() -> None:
    results = {
        "A_current": _cr("A_current", exact=0.5, symbol=0.5, stale=0.2, scope=0.2),
        "E_hybrid_a0.25": _cr("E_hybrid_a0.25", exact=0.8, symbol=0.7, stale=0.2, scope=0.1),
    }
    gate = evaluate_win_gate(results)
    assert gate["graduates"] is True
    assert gate["recommended_condition"] == "E_hybrid_a0.25"
    assert gate["recommended_hybrid_alpha"] == 0.25


def test_gate_picks_best_exact_plus_symbol_among_winners() -> None:
    results = {
        "A_current": _cr("A_current", exact=0.5, symbol=0.5, stale=0.2, scope=0.2),
        "E_hybrid_a0.25": _cr("E_hybrid_a0.25", exact=0.6, symbol=0.6, stale=0.2, scope=0.2),
        "E_hybrid_a0.5": _cr("E_hybrid_a0.5", exact=0.9, symbol=0.8, stale=0.2, scope=0.2),
    }
    gate = evaluate_win_gate(results)
    assert gate["graduates"] is True
    assert gate["recommended_condition"] == "E_hybrid_a0.5"
    assert gate["recommended_hybrid_alpha"] == 0.5


def test_gate_does_not_graduate_when_only_one_metric_beats() -> None:
    results = {
        "A_current": _cr("A_current", exact=0.5, symbol=0.5, stale=0.2, scope=0.2),
        # beats exact but not symbol
        "E_hybrid_a0.5": _cr("E_hybrid_a0.5", exact=0.9, symbol=0.5, stale=0.1, scope=0.1),
    }
    gate = evaluate_win_gate(results)
    assert gate["graduates"] is False
    assert gate["recommended_condition"] is None


def test_gate_blocks_on_stale_or_scope_regression() -> None:
    results = {
        "A_current": _cr("A_current", exact=0.5, symbol=0.5, stale=0.2, scope=0.2),
        # beats both recall metrics but regresses stale_hit_rate
        "E_hybrid_a0": _cr("E_hybrid_a0", exact=0.9, symbol=0.9, stale=0.4, scope=0.2),
    }
    gate = evaluate_win_gate(results)
    assert gate["graduates"] is False
    entry = next(e for e in gate["evaluated"] if e["condition"] == "E_hybrid_a0")
    assert entry["beats_exact"] and entry["beats_symbol"]
    assert entry["no_stale_regression"] is False


def test_gate_reports_missing_baseline() -> None:
    gate = evaluate_win_gate({"E_hybrid_a0.5": _cr("E_hybrid_a0.5", exact=1.0, symbol=1.0, stale=0.0, scope=0.0)})
    assert gate["graduates"] is False
    assert "missing" in gate["reason"]


def test_gate_ignores_saturated_metric_and_graduates_on_headroom() -> None:
    # Real dummy-gold shape: exact_string_recall saturates at 1.0 (graphiti's internal
    # RRF already fuses BM25 + cosine), so only symbol_recall has headroom. The
    # recalibrated gate graduates on the metric with headroom instead of demanding the
    # impossible exact > 1.0. See benchmark-notes/r1-dummy-gold-run.md.
    results = {
        "A_current": _cr("A_current", exact=1.0, symbol=0.30, stale=0.0, scope=0.0),
        "E_hybrid_a0": _cr("E_hybrid_a0", exact=1.0, symbol=0.325, stale=0.0, scope=0.0),
    }
    gate = evaluate_win_gate(results)
    assert gate["graduates"] is True
    assert gate["recommended_condition"] == "E_hybrid_a0"
    assert gate["recommended_hybrid_alpha"] == 0.0
    assert gate["eligible_metrics"] == ["symbol_recall"]
    assert gate["saturated_metrics"] == ["exact_string_recall"]
    entry = next(e for e in gate["evaluated"] if e["condition"] == "E_hybrid_a0")
    assert entry["beats_eligible"] is True
    assert entry["no_saturated_regression"] is True


def test_gate_does_not_graduate_when_all_improvement_metrics_saturated() -> None:
    # No headroom on either improvement metric -> refuse to graduate and explain why,
    # instead of silently passing/failing on an impossible comparison.
    results = {
        "A_current": _cr("A_current", exact=1.0, symbol=1.0, stale=0.0, scope=0.0),
        "E_hybrid_a0": _cr("E_hybrid_a0", exact=1.0, symbol=1.0, stale=0.0, scope=0.0),
    }
    gate = evaluate_win_gate(results)
    assert gate["graduates"] is False
    assert gate["recommended_condition"] is None
    assert gate["eligible_metrics"] == []
    assert "no unsaturated improvement metric" in gate["reason"]


def test_gate_blocks_when_saturated_metric_regresses() -> None:
    # symbol improves, but the saturated exact metric slips below 1.0 -> blocked
    # (a win must not be bought by regressing an already-maxed metric).
    results = {
        "A_current": _cr("A_current", exact=1.0, symbol=0.30, stale=0.0, scope=0.0),
        "E_hybrid_a0.5": _cr("E_hybrid_a0.5", exact=0.9, symbol=0.5, stale=0.0, scope=0.0),
    }
    gate = evaluate_win_gate(results)
    assert gate["graduates"] is False
    entry = next(e for e in gate["evaluated"] if e["condition"] == "E_hybrid_a0.5")
    assert entry["beats_eligible"] is True
    assert entry["no_saturated_regression"] is False
    assert entry["wins"] is False


# --- parameterized gate: nested metric families ----------------------------
#
# recall@k metrics are NESTED: a gold inside the top-5 is necessarily inside the
# top-10. So a gold moving from rank 6 to rank 2 improves recall@5 and MRR but leaves
# recall@10 UNCHANGED. Under improvement_mode="all" the conjunction fails and a REAL
# win is rejected -- and a caller that reads "no graduation" as "the change was
# redundant" then draws a false conclusion. improvement_mode="any" is required for
# nested families: beat at least one eligible metric, regress none.


def _recall_cr(name: str, *, r5: float, r10: float, mrr: float, fp: float = 0.0) -> ConditionResult:
    return ConditionResult(
        condition=name,
        metrics={
            "recall_at_5": r5,
            "recall_at_10": r10,
            "mrr": mrr,
            "negative_query_false_positive_rate": fp,
            "latency_ms": 0.0,
        },
    )


RECALL_PRIMARIES = ("recall_at_5", "recall_at_10", "mrr")


def test_gate_all_mode_rejects_genuine_win_on_nested_metrics() -> None:
    """Documents the bug: 'all' cannot be satisfied by a real improvement.

    Gold moves rank 6 -> 2. recall@5 rises (6 was outside the top 5, 2 is inside),
    MRR rises (1/6 -> 1/2), recall@10 is UNCHANGED (6 and 2 are both within 10).
    """
    results = {
        "A_current": _recall_cr("A_current", r5=0.5, r10=0.9, mrr=0.40),
        "B_content": _recall_cr("B_content", r5=0.7, r10=0.9, mrr=0.55),
    }
    gate = evaluate_win_gate(
        results,
        challenger_prefix="B_",
        primary_improvement_metrics=RECALL_PRIMARIES,
        improvement_mode="all",
        guards_lower_is_better=("negative_query_false_positive_rate",),
    )
    # A genuine improvement is rejected purely because a nested metric could not move.
    assert gate["graduates"] is False


def test_gate_any_mode_graduates_genuine_win_on_nested_metrics() -> None:
    """The fix: 'any' accepts the same real win that 'all' wrongly rejected."""
    results = {
        "A_current": _recall_cr("A_current", r5=0.5, r10=0.9, mrr=0.40),
        "B_content": _recall_cr("B_content", r5=0.7, r10=0.9, mrr=0.55),
    }
    gate = evaluate_win_gate(
        results,
        challenger_prefix="B_",
        primary_improvement_metrics=RECALL_PRIMARIES,
        improvement_mode="any",
        guards_lower_is_better=("negative_query_false_positive_rate",),
    )
    assert gate["graduates"] is True
    assert gate["recommended_condition"] == "B_content"
    assert gate["improvement_mode"] == "any"


def test_gate_any_mode_blocks_when_an_eligible_metric_regresses() -> None:
    """'any' must not let a win on one metric be bought by regressing another."""
    results = {
        "A_current": _recall_cr("A_current", r5=0.5, r10=0.9, mrr=0.40),
        # recall@5 up, but recall@10 slips -- traded a deep gold away for a shallow one.
        "B_content": _recall_cr("B_content", r5=0.7, r10=0.7, mrr=0.55),
    }
    gate = evaluate_win_gate(
        results,
        challenger_prefix="B_",
        primary_improvement_metrics=RECALL_PRIMARIES,
        improvement_mode="any",
        guards_lower_is_better=(),
    )
    assert gate["graduates"] is False
    entry = next(e for e in gate["evaluated"] if e["condition"] == "B_content")
    assert entry["beats_eligible"] is True
    assert entry["no_eligible_regression"] is False


def test_gate_raises_when_configured_guard_is_missing_from_metrics() -> None:
    """A guard the run never produced must fail loudly, never pass vacuously.

    Softening this to a 0.0 default would make a mis-named guard silently guard
    nothing -- the exact failure a guard exists to prevent.
    """
    results = {
        "A_current": _recall_cr("A_current", r5=0.5, r10=0.9, mrr=0.40),
        "B_content": _recall_cr("B_content", r5=0.7, r10=0.9, mrr=0.55),
    }
    try:
        evaluate_win_gate(
            results,
            challenger_prefix="B_",
            primary_improvement_metrics=RECALL_PRIMARIES,
            improvement_mode="any",
            guards_lower_is_better=("a_guard_that_does_not_exist",),
        )
    except ValueError as exc:
        assert "a_guard_that_does_not_exist" in str(exc)
        assert "vacuously" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected ValueError for a guard absent from the metrics")


def test_gate_any_mode_blocks_on_guard_regression() -> None:
    """A recall win must not be bought by returning junk on negative queries."""
    results = {
        "A_current": _recall_cr("A_current", r5=0.5, r10=0.9, mrr=0.40, fp=0.10),
        "B_content": _recall_cr("B_content", r5=0.7, r10=0.9, mrr=0.55, fp=0.40),
    }
    gate = evaluate_win_gate(
        results,
        challenger_prefix="B_",
        primary_improvement_metrics=RECALL_PRIMARIES,
        improvement_mode="any",
        guards_lower_is_better=("negative_query_false_positive_rate",),
    )
    assert gate["graduates"] is False


def test_gate_higher_is_better_guard_blocks_trade_away() -> None:
    """A higher-is-better guard (a recall metric we must not trade away) blocks."""
    results = {
        "A_current": ConditionResult(
            condition="A_current",
            metrics={"recall_at_5": 0.5, "exact_string_recall": 0.9, "latency_ms": 0.0},
        ),
        "B_content": ConditionResult(
            condition="B_content",
            # recall@5 improves, but exact-string recall is sacrificed to get it.
            metrics={"recall_at_5": 0.8, "exact_string_recall": 0.4, "latency_ms": 0.0},
        ),
    }
    gate = evaluate_win_gate(
        results,
        challenger_prefix="B_",
        primary_improvement_metrics=("recall_at_5",),
        improvement_mode="any",
        guards_lower_is_better=(),
        guards_higher_is_better=("exact_string_recall",),
    )
    assert gate["graduates"] is False


def test_gate_rejects_unknown_improvement_mode() -> None:
    results = {"A_current": _recall_cr("A_current", r5=0.5, r10=0.9, mrr=0.4)}
    try:
        evaluate_win_gate(results, improvement_mode="most")
    except ValueError as exc:
        assert "improvement_mode" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected ValueError for an unknown improvement_mode")


# --- end-to-end stub run ---------------------------------------------------


def _tiny_fixture() -> R1Fixture:
    return R1Fixture(
        name="tiny",
        description="t",
        memories=[
            R1Memory(id="hit", text="alpha beta gamma symbol Foo.bar", symbols={"Foo.bar"}),
            R1Memory(id="noise", text="delta epsilon zeta"),
        ],
        queries=[
            R1Query(id="q1", text="alpha beta", family="symbol_name_query", support_ids=["hit"]),
        ],
    )


def test_stub_runner_is_deterministic_and_well_formed() -> None:
    fixture = _tiny_fixture()
    conditions = build_stub_conditions(fixture)
    art1 = R1BenchmarkRunner(fixture, conditions).run()
    art2 = R1BenchmarkRunner(fixture, build_stub_conditions(fixture)).run()

    # Rankings + non-latency metrics are deterministic (latency_ms is wall-clock).
    def _stable(art: dict) -> dict:
        return {
            name: {
                "per_query": res["per_query"],
                "metrics": {k: v for k, v in res["metrics"].items() if k != "latency_ms"},
            }
            for name, res in art["conditions"].items()
        }

    assert _stable(art1) == _stable(art2)
    assert art1["win_gate"] == art2["win_gate"]
    assert "A_current" in art1["conditions"]
    assert any(c.startswith("E_hybrid_a") for c in art1["conditions"])
    assert set(art1["win_gate"]) >= {"graduates", "recommended_condition", "baseline", "evaluated"}
    # the obvious hit ranks above noise for the lexical query
    assert art1["conditions"]["A_current"]["per_query"]["q1"][0] == "hit"


def test_demo_fixture_loads_and_runs() -> None:
    fixture = R1Fixture.from_file(DEMO)
    assert len(fixture.memories) > 0 and len(fixture.queries) > 0
    artifact = R1BenchmarkRunner(fixture, build_stub_conditions(fixture)).run()
    # all six headline metrics present on every condition
    for result in artifact["conditions"].values():
        for key in (
            "recall_at_5",
            "exact_string_recall",
            "symbol_recall",
            "stale_hit_rate",
            "wrong_scope_injection_rate",
            "latency_ms",
        ):
            assert key in result["metrics"]
    assert "graduates" in artifact["win_gate"]
