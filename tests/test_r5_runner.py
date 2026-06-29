"""Tests for the R5 StructureTemporalOracle bench (consumes menhir.domain.structure_temporal)."""

from __future__ import annotations

from pathlib import Path

from archolith_bench.r5.runner import R5BenchRunner, R5Fixture, evaluate_win_gate

REPO_ROOT = Path(__file__).resolve().parent.parent
DEMO = REPO_ROOT / "fixtures" / "r5_seed_blast_radius.json"


def _run() -> dict:
    return R5BenchRunner(R5Fixture.from_file(DEMO)).run()


def test_time_aware_oracle_finds_culprit_where_structure_cannot() -> None:
    art = _run()
    a = art["conditions"]["A_structure_only"]["metrics"]
    b = art["conditions"]["B_structure_temporal"]["metrics"]
    # structure-only cannot rank the in-window-changed culprit first
    assert a["culprit_at_1"] == 0.0
    # the time-aware oracle does
    assert b["culprit_at_1"] == 1.0
    assert b["noise_at_1"] == 0.0
    assert art["win_gate"]["graduates"] is True


def test_both_have_culprit_in_blast_radius() -> None:
    """The culprit is structurally reachable in both (it's a real dependency); the
    difference is purely RANKING — only time tells which sibling to suspect."""
    art = _run()
    assert art["conditions"]["A_structure_only"]["metrics"]["culprit_recall_at_k"] == 1.0
    assert art["conditions"]["B_structure_temporal"]["metrics"]["culprit_recall_at_k"] == 1.0


def test_gate_reports_missing_condition() -> None:
    gate = evaluate_win_gate({"A_structure_only": {"culprit_at_1": 0.0, "noise_at_1": 1.0}})
    assert gate["graduates"] is False
    assert "missing" in gate["reason"]
