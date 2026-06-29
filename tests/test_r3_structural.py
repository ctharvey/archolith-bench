"""Tests for the R3 rung-F structural-expansion ladder (consumes menhir.domain.structural_expansion)."""

from __future__ import annotations

from pathlib import Path

from archolith_bench.r3.structural import (
    StructuralBenchRunner,
    StructuralFixture,
    evaluate_win_gate,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
DEMO = REPO_ROOT / "fixtures" / "r3_structural_graph.json"


def test_unflag_structural_fixture_graduates() -> None:
    art = StructuralBenchRunner(StructuralFixture.from_file(DEMO)).run()
    a = art["conditions"]["A_semantic_only"]["metrics"]
    f = art["conditions"]["F_structural_expansion"]["metrics"]
    # semantic-only misses the bug-relevant neighbors entirely
    assert a["structural_neighbor_recall"] == 0.0
    # bounded expansion surfaces them all
    assert f["structural_neighbor_recall"] == 1.0
    # without admitting the hub, and within the cap
    assert f["hub_kept_out"] == 1.0
    assert art["win_gate"]["graduates"] is True


def test_hub_node_never_enters_pool() -> None:
    art = StructuralBenchRunner(StructuralFixture.from_file(DEMO)).run()
    pool = art["conditions"]["F_structural_expansion"]["pool"]
    assert "entity_node_generic" not in pool  # degree 500, suppressed


def test_pool_stays_bounded() -> None:
    art = StructuralBenchRunner(StructuralFixture.from_file(DEMO)).run()
    gate = art["win_gate"]
    assert gate["bounded"] is True
    assert gate["pool_size"] <= gate["pool_bound"]


def test_gate_reports_missing_condition() -> None:
    from archolith_bench.r3.structural import ConditionResult

    fx = StructuralFixture.from_file(DEMO)
    gate = evaluate_win_gate({"A_semantic_only": ConditionResult("A_semantic_only", {})}, fx)
    assert gate["graduates"] is False
    assert "missing" in gate["reason"]
