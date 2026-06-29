"""Tests for the R3 Warden consolidation bench (consumes menhir.domain.warden)."""

from __future__ import annotations

from pathlib import Path

from archolith_bench.r3.warden import WardenBenchRunner, WardenFixture, evaluate_win_gate

REPO_ROOT = Path(__file__).resolve().parent.parent
DEMO = REPO_ROOT / "fixtures" / "r3_warden_chain.json"


def _run() -> dict:
    return WardenBenchRunner(WardenFixture.from_file(DEMO)).run()


def test_chain_beats_every_single_warden_without_overblocking() -> None:
    art = _run()
    conds = art["conditions"]
    chain = conds["chain"]["metrics"]
    # each single warden only catches its own axis
    for single in ("currentness_only", "exhaustion_only", "scope_only"):
        assert conds[single]["metrics"]["refuse_recall"] < chain["refuse_recall"]
    # the chain catches all wrong candidates ...
    assert chain["refuse_recall"] == 1.0
    # ... and never blocks the safe one
    assert chain["admit_retention"] == 1.0
    assert art["win_gate"]["graduates"] is True


def test_each_single_warden_admits_retention_one() -> None:
    """No warden over-blocks the genuinely-safe candidate."""
    art = _run()
    for cond in art["conditions"].values():
        assert cond["metrics"]["admit_retention"] == 1.0


def test_gate_reports_missing_chain() -> None:
    gate = evaluate_win_gate({"currentness_only": {"refuse_recall": 1.0, "admit_retention": 1.0}})
    assert gate["graduates"] is False
    assert "missing" in gate["reason"]
