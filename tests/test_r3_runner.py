"""Tests for the R3 belief-currentness ladder + win gate.

Consumes menhir's real belief domain (menhir-frontier/src on PYTHONPATH via the
test invocation). Pins the headline: D (currentness policy) cuts stale-current
assertions to zero WITHOUT losing historical context, where Rung-0 buckets (C)
trade history away."""

from __future__ import annotations

from pathlib import Path

from archolith_bench.r3.models import BeliefFixture
from archolith_bench.r3.runner import R3BenchmarkRunner, evaluate_win_gate

REPO_ROOT = Path(__file__).resolve().parent.parent
DEMO = REPO_ROOT / "fixtures" / "r3_ce_willow.json"


def _run() -> dict:
    return R3BenchmarkRunner(BeliefFixture.from_file(DEMO)).run()


def test_demo_fixture_loads_and_all_conditions_run() -> None:
    art = _run()
    assert set(art["conditions"]) == {"A_assert_all", "C_belief_buckets", "D_currentness"}
    for res in art["conditions"].values():
        for key in ("stale_current_assertion_rate", "poisoned_context_injection_rate", "historical_context_preservation"):
            assert key in res["metrics"]


def test_baseline_asserts_stale_beliefs() -> None:
    art = _run()
    base = art["conditions"]["A_assert_all"]["metrics"]
    # the strawman asserts everything -> it asserts stale beliefs as current truth
    assert base["stale_current_assertion_rate"] > 0.0
    assert base["historical_context_preservation"] == 1.0  # but surfaces everything


def test_currentness_eliminates_stale_assertion_and_preserves_history() -> None:
    art = _run()
    d = art["conditions"]["D_currentness"]["metrics"]
    # the headline: no stale belief is asserted as current truth ...
    assert d["stale_current_assertion_rate"] == 0.0
    # ... and the former beliefs are still surfaced (as history), not dropped
    assert d["historical_context_preservation"] == 1.0
    assert d["poisoned_context_injection_rate"] == 0.0


def test_currentness_beats_naive_buckets_on_history() -> None:
    art = _run()
    c = art["conditions"]["C_belief_buckets"]["metrics"]
    d = art["conditions"]["D_currentness"]["metrics"]
    # Rung-0 buckets cut stale too, but lose historical context; D keeps it.
    assert d["historical_context_preservation"] > c["historical_context_preservation"]


def test_win_gate_graduates_on_demo() -> None:
    art = _run()
    gate = art["win_gate"]
    assert gate["graduates"] is True
    assert gate["stale_current_assertion_cut"] > 0.0
    assert gate["historical_preservation_loss"] <= 0.0


def test_gate_reports_missing_conditions() -> None:
    from archolith_bench.r3.runner import ConditionResult

    partial = {"A_assert_all": ConditionResult("A_assert_all", {})}
    gate = evaluate_win_gate(partial)
    assert gate["graduates"] is False
    assert "missing" in gate["reason"]
