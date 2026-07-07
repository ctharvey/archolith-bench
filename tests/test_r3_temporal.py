"""Tests for the R3 rung-B temporal-metadata ladder (consumes menhir.domain.temporal)."""

from __future__ import annotations

from pathlib import Path

from archolith_bench.r3.temporal import (
    TemporalBenchRunner,
    TemporalFixture,
    evaluate_win_gate,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
DEMO = REPO_ROOT / "fixtures" / "r3_temporal_ce_willow.json"


def test_temporal_fixture_graduates_cutting_leak_without_recall_loss() -> None:
    art = TemporalBenchRunner(TemporalFixture.from_file(DEMO)).run()
    a = art["conditions"]["A_no_temporal"]["metrics"]
    b = art["conditions"]["B_temporal"]["metrics"]
    assert b["temporal_precision"] > a["temporal_precision"]   # cuts leakage
    assert b["leak_rate"] < a["leak_rate"]
    assert b["temporal_recall"] >= a["temporal_recall"]        # no recall loss
    assert b["leak_rate"] == 0.0
    assert art["win_gate"]["graduates"] is True


def test_current_belief_excludes_superseded_patch_belief() -> None:
    """The whole point: 'patch fixed it' (expired belief) must not be returned as current."""
    fixture = TemporalFixture.from_file(DEMO)
    runner = TemporalBenchRunner(fixture)
    q = next(q for q in fixture.queries if q.id == "q_current_belief")
    returned = runner._returned("B_temporal", q)
    assert "B_patch_fixed" not in returned
    assert "C_load_order_cause" in returned and "D_real_fix" in returned


def test_as_known_at_surfaces_former_belief() -> None:
    """'what did I believe before the load-order fix' -> the former belief B is returned."""
    fixture = TemporalFixture.from_file(DEMO)
    runner = TemporalBenchRunner(fixture)
    q = next(q for q in fixture.queries if q.id == "q_knew_wednesday")
    returned = runner._returned("B_temporal", q)
    assert "B_patch_fixed" in returned        # the former belief, surfaced for the drift story
    assert "C_load_order_cause" not in returned  # not yet known on Wednesday


def test_baseline_leaks_everything() -> None:
    fixture = TemporalFixture.from_file(DEMO)
    runner = TemporalBenchRunner(fixture)
    q = next(q for q in fixture.queries if q.id == "q_current_belief")
    # temporal-blind returns all facts -> leaks the superseded belief
    assert runner._returned("A_no_temporal", q) == {f.id for f in fixture.facts}


def test_gate_reports_missing_condition() -> None:
    from archolith_bench.r3.temporal import ConditionResult

    gate = evaluate_win_gate({"A_no_temporal": ConditionResult("A_no_temporal", {})})
    assert gate["graduates"] is False
    assert "missing" in gate["reason"]
