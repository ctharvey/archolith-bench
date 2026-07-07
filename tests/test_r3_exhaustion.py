"""Tests for the R3 rung-E exhaustion session ladder (consumes menhir.domain.exhaustion)."""

from __future__ import annotations

from pathlib import Path

from archolith_bench.r3.session import (
    ExhaustionSessionRunner,
    SessionFixture,
    SessionItem,
    SessionTurn,
    evaluate_win_gate,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
DEMO = REPO_ROOT / "fixtures" / "r3_session_loop.json"


def test_demo_session_graduates() -> None:
    art = ExhaustionSessionRunner(SessionFixture.from_file(DEMO)).run()
    gate = art["win_gate"]
    assert gate["graduates"] is True
    # E eliminates loop injections...
    assert art["conditions"]["E_exhaustion"]["metrics"]["loop_injection_rate"] == 0.0
    # ...while the baseline poisons via the loop...
    assert art["conditions"]["A_no_penalty"]["metrics"]["loop_injection_rate"] > 0.0
    # ...and nothing useful/exempt is over-suppressed.
    assert gate["productive_retention"] == 1.0
    assert gate["exempt_retention"] == 1.0


def test_progress_resets_counter_so_productive_recency_is_never_penalized() -> None:
    """A loop trap that produces progress every couple of turns never reaches the
    suppress threshold — productive recency is preserved (the whole point)."""
    fixture = SessionFixture(
        name="productive",
        description="t",
        items=[SessionItem(id="m", is_loop_trap=True)],
        turns=[
            SessionTurn(retrieved=["m"], progress=False),
            SessionTurn(retrieved=["m"], progress=True),   # progress resets the counter
            SessionTurn(retrieved=["m"], progress=False),
            SessionTurn(retrieved=["m"], progress=True),
            SessionTurn(retrieved=["m"], progress=False),
        ],
    )
    art = ExhaustionSessionRunner(fixture).run()
    # never crossed suppress_at between progress events -> no loop injections under either
    assert art["conditions"]["A_no_penalty"]["metrics"]["loop_injection_rate"] == 0.0
    assert art["conditions"]["E_exhaustion"]["metrics"]["loop_injection_rate"] == 0.0


def test_exempt_item_never_suppressed_even_when_looping() -> None:
    fixture = SessionFixture(
        name="exempt",
        description="t",
        items=[SessionItem(id="err", exempt_reason="active_error_log")],
        turns=[SessionTurn(retrieved=["err"], progress=False) for _ in range(8)],
    )
    art = ExhaustionSessionRunner(fixture).run()
    assert art["conditions"]["E_exhaustion"]["metrics"]["exempt_retention"] == 1.0


def test_gate_reports_missing_condition() -> None:
    from archolith_bench.r3.session import ConditionResult

    gate = evaluate_win_gate({"A_no_penalty": ConditionResult("A_no_penalty", {})})
    assert gate["graduates"] is False
    assert "missing" in gate["reason"]
