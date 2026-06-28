"""Tests for the oracle ladder runner + promotion gate."""

from __future__ import annotations

from pathlib import Path

from archolith_bench.oracle.models import OracleFixture
from archolith_bench.oracle.runner import CONDITIONS, OracleBenchmarkRunner

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "oracle_demo.json"


def _artifact() -> dict:
    return OracleBenchmarkRunner(OracleFixture.from_file(FIXTURE)).run(include_traces=False)


def test_run_has_all_conditions() -> None:
    art = _artifact()
    assert set(art["conditions"]) == set(CONDITIONS)


def test_metrics_present_and_in_range() -> None:
    art = _artifact()
    for cond in CONDITIONS:
        m = art["conditions"][cond]["metrics"]
        for key in ("recall_at_5", "stale_hit_rate", "wrong_scope_injection_rate",
                    "current_truth_suppression_accuracy", "historical_context_preservation"):
            assert 0.0 <= m[key] <= 1.0


def test_all_conditions_are_deterministic() -> None:
    art = _artifact()
    for cond in CONDITIONS:
        assert art["conditions"][cond]["metrics"]["ranking_determinism"] == 1.0


def test_combining_oracles_beats_single_semantic_on_stale() -> None:
    # The whole point of the ladder: oracle combination suppresses stale/wrong-scope
    # that a lone semantic signal lets through.
    art = _artifact()
    a = art["conditions"]["A_semantic"]["metrics"]
    e = art["conditions"]["E_weighted"]["metrics"]
    assert e["stale_hit_rate"] <= a["stale_hit_rate"]
    assert e["wrong_scope_injection_rate"] <= a["wrong_scope_injection_rate"]
    assert e["recall_at_5"] >= a["recall_at_5"]


def test_promotion_gate_shape() -> None:
    gate = _artifact()["promotion_gate"]
    for key in ("graduates", "improved_any", "recall_loss", "recall_acceptable",
                "improvements_vs_best_baseline", "baseline_reference"):
        assert key in gate
    assert isinstance(gate["graduates"], bool)


def test_run_is_reproducible() -> None:
    # Rankings/metrics are deterministic; latency_ms naturally wobbles, so exclude it.
    def _stable(art: dict) -> dict:
        m = dict(art["conditions"]["F_logspace"]["metrics"])
        m.pop("latency_ms", None)
        return m

    assert _stable(_artifact()) == _stable(_artifact())
