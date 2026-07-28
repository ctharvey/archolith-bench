"""Tests for the PR card renderer."""

from __future__ import annotations

from archolith_bench.ci.card import render_pr_card
from archolith_bench.ci.compare import Comparison, GateResult, TypeDelta
from archolith_bench.ci.stratified import StratifiedResult, TypeResult


def _make_result(overall: float = 0.247) -> StratifiedResult:
    return StratifiedResult(
        overall=overall,
        by_type={"temporal-reasoning": 0.350, "multi-session": 0.250},
        n_total=120,
        input_tokens=100000,
        output_tokens=50000,
        cost_usd=1.84,
        per_question={},
        type_results=[
            TypeResult(type="temporal-reasoning", score=0.350, n=20, input_tokens=50000,
                       output_tokens=25000, cost_usd=0.92),
            TypeResult(type="multi-session", score=0.250, n=20, input_tokens=50000,
                       output_tokens=25000, cost_usd=0.92),
        ],
    )


def _make_comparison(gate: GateResult = GateResult.PASS) -> Comparison:
    return Comparison(
        overall_baseline=0.230,
        overall_current=0.247,
        overall_delta=0.017,
        overall_pct_delta=7.4,
        type_deltas=[
            TypeDelta(type="temporal-reasoning", baseline=0.350, current=0.350, delta=0.0, status="─"),
            TypeDelta(type="multi-session", baseline=0.180, current=0.250, delta=0.070, status="▲"),
        ],
        gate=gate,
        gate_reason="overall delta +0.017 within threshold",
    )


def test_pass_card_has_emoji_and_score():
    card = render_pr_card(
        pr_number=123,
        pr_author="alice",
        head_sha="abc123def456",
        result=_make_result(),
        comparison=_make_comparison(GateResult.PASS),
        max_calls=200,
        max_usd=5.0,
        llm_calls_used=187,
        usd_used=1.84,
    )
    assert "✅ Recall Benchmark — PASS" in card
    assert "0.247" in card
    assert "0.230" in card
    assert "@alice" in card
    assert "187" in card
    assert "$1.84" in card


def test_fail_card_has_fail_emoji():
    card = render_pr_card(
        pr_number=123,
        pr_author="alice",
        head_sha="abc123def456",
        result=_make_result(overall=0.200),
        comparison=_make_comparison(GateResult.FAIL),
        max_calls=200,
        max_usd=5.0,
        llm_calls_used=187,
        usd_used=1.84,
    )
    assert "❌ Recall Benchmark — FAIL" in card


def test_warn_card_has_warn_emoji():
    card = render_pr_card(
        pr_number=123,
        pr_author="alice",
        head_sha="abc123def456",
        result=_make_result(),
        comparison=_make_comparison(GateResult.WARN),
        max_calls=200,
        max_usd=5.0,
        llm_calls_used=187,
        usd_used=1.84,
    )
    assert "⚠️ Recall Benchmark — WARN" in card


def test_killed_card_has_abort_message():
    card = render_pr_card(
        pr_number=123,
        pr_author="alice",
        head_sha="abc123def456",
        result=_make_result(),
        comparison=_make_comparison(),
        max_calls=200,
        max_usd=5.0,
        llm_calls_used=200,
        usd_used=5.0,
        killed=True,
        kill_reason="LLM call cap exceeded (200 / 200)",
    )
    assert "❌ Recall Benchmark — ABORTED" in card
    assert "LLM call cap exceeded" in card


def test_card_includes_per_type_table():
    card = render_pr_card(
        pr_number=123,
        pr_author="alice",
        head_sha="abc123def456",
        result=_make_result(),
        comparison=_make_comparison(),
        max_calls=200,
        max_usd=5.0,
        llm_calls_used=187,
        usd_used=1.84,
    )
    assert "Per-type breakdown" in card
    assert "temporal-reasoning" in card
    assert "multi-session" in card
