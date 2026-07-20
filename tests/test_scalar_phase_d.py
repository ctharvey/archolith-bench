"""Phase D counterfactual recall scorer -- offline (no menhir, no neo4j).

Proves the deterministic contract: current-state detection, the seven per-question dimensions, the
counterfactual View-aware composition, and the PRIMARY-over-correct-views vs end-to-end-coverage split.
"""

from __future__ import annotations

import pytest

from archolith_bench.harness.scalar_phase_d import (
    PhaseDCase,
    StubPhaseDClient,
    aggregate_phase_d,
    is_current_state_question,
    phase_d_cases,
    run_phase_d,
    score_question,
    value_matches,
)


# ---------------------------------------------------------------------------- current-state detection


@pytest.mark.parametrize("q,expected", [
    ("How many coins do I own now?", True),
    ("What time do I wake up these days?", True),
    ("What is my current mood?", True),
    ("How many coins did I own a while ago?", False),   # historical cue wins
    ("What time did I used to wake up?", False),
    ("How many coins do I own?", False),                 # no current cue, no history -> not current-state
])
def test_current_state_detection(q, expected):
    assert is_current_state_question(q) is expected


def test_historical_cue_overrides_current_cue():
    # both a current AND a historical cue -> historical wins (the wrongful-suppression tripwire).
    assert is_current_state_question("What is my mood now, and what was it previously?") is False


# ---------------------------------------------------------------------------- value matching


@pytest.mark.parametrize("exp,act,ok", [
    (37.0, "37", True), (37.0, 37, True), (20.0, "2023", False),   # whole-token numeric via _value_in_text
    ("Wednesday", "wednesday", True), ("07:30", "07:30", True), ("red", "bright red", True),
])
def test_value_matches(exp, act, ok):
    assert value_matches(exp, act) is ok


# ---------------------------------------------------------------------------- per-question scoring


def _view(attr, kind, val):
    return {"subject_uuid": "self", "ss_attribute": attr, "ss_kind": kind,
            "ss_value": val, "ss_display": val, "view_value": 0.0}


def test_current_case_view_improves_over_stale_baseline():
    case = PhaseDCase(
        case_id="c", kind="current", slot_attribute="owned", expect_kind="count",
        question="How many coins do I own now?", current_answer=37.0, stale_answer=20.0,
    )
    # baseline is ambiguous: surfaces BOTH the stale 20 and current 37.
    r = score_question(case, ["I owned 20 coins.", "I own 37 coins."], [_view("owned", "count", "37")], [])
    assert r.current_state_detected and r.slot_overlap and r.view_status == "correct"
    assert r.stale_in_baseline is True
    assert r.baseline_answer_correct is False        # ambiguous baseline is not "correct"
    assert r.answer_improved is True
    assert r.wrongful_suppression is False
    assert str(r.view_aware_answer) == "37"


def test_current_case_no_improvement_when_baseline_already_unambiguous():
    case = PhaseDCase(
        case_id="c", kind="current", slot_attribute="owned", expect_kind="count",
        question="How many coins do I own now?", current_answer=37.0, stale_answer=20.0,
    )
    # baseline surfaces ONLY the current value -> already correct, so the View adds nothing.
    r = score_question(case, ["I own 37 coins."], [_view("owned", "count", "37")], [])
    assert r.baseline_answer_correct is True
    assert r.answer_improved is False


def test_wrong_view_is_flagged_and_never_counted_correct():
    case = PhaseDCase(
        case_id="c", kind="current", slot_attribute="owned", expect_kind="count",
        question="How many coins do I own now?", current_answer=37.0, stale_answer=20.0,
    )
    r = score_question(case, ["I own 37 coins."], [_view("owned", "count", "20")], [])  # View has stale value
    assert r.view_status == "wrong"
    assert r.answer_improved is False
    assert r.wrongful_suppression is True            # applied a wrong value as authority


def test_historical_control_falls_back_and_is_not_suppressed():
    case = PhaseDCase(
        case_id="h", kind="historical", slot_attribute="owned", expect_kind="count",
        question="How many coins did I own a while ago?", current_answer=37.0, stale_answer=20.0,
    )
    r = score_question(case, ["I owned 20 coins."], [_view("owned", "count", "37")], [])
    assert r.current_state_detected is False          # historical -> not current-state
    assert r.wrongful_suppression is False            # View not applied, stale answer preserved
    assert "20 coins" in str(r.view_aware_answer)      # fell back to baseline (the correct history)


def test_historical_control_violation_when_misdetected():
    # If a historical question is WRONGLY detected as current-state, applying the current View suppresses
    # the correct (stale) answer -> wrongful_suppression must fire. Force detection via a current cue.
    case = PhaseDCase(
        case_id="h", kind="historical", slot_attribute="owned", expect_kind="count",
        question="How many coins do I own now, historically?", current_answer=37.0, stale_answer=20.0,
    )
    # "now" present and no historical cue in this phrasing -> detected True (the failure mode).
    r = score_question(case, ["I owned 20 coins."], [_view("owned", "count", "37")], [])
    assert r.current_state_detected is True
    assert r.wrongful_suppression is True


def test_noview_control_falls_back_never_fabricates_authority():
    case = PhaseDCase(
        case_id="n", kind="noview", slot_attribute="mood", expect_kind="status",
        question="What is my current mood?", current_answer="happy",
    )
    r = score_question(case, [], [], [])              # no View, no baseline
    assert r.slot_overlap is False and r.view_status == "absent"
    assert r.wrongful_suppression is False
    assert r.answer_improved is False


# ---------------------------------------------------------------------------- aggregate split


def test_primary_metrics_only_over_correct_views():
    cases = [
        PhaseDCase("a", "current", "owned", "count", "How many now?", 37.0, 20.0),
        PhaseDCase("b", "current", "wake_time", "clock_time", "What time now?", "07:30", "09:00"),
    ]
    results = [
        score_question(cases[0], ["20", "37"], [_view("owned", "count", "37")], []),        # correct view
        score_question(cases[1], ["09:00"], [_view("wake_time", "clock_time", "09:00")], []),  # WRONG view
    ]
    agg = aggregate_phase_d(results)
    # only the correct-view row is in the primary denominator
    assert agg["primary_over_correct_views"]["correct_view_rows"] == 1
    assert agg["primary_over_correct_views"]["answer_improved"] == 1
    # end-to-end coverage still counts all questions
    assert agg["coverage_all_questions"]["total_questions"] == 2
    assert agg["coverage_all_questions"]["view_correct"] == 1


# ---------------------------------------------------------------------------- stub end-to-end


def test_stub_happy_path():
    stub = StubPhaseDClient()
    res = run_phase_d(stub, stub, namespace="pd-test")
    m = res.metrics
    assert m["primary_over_correct_views"]["correct_view_rows"] == 3
    assert m["primary_over_correct_views"]["answer_improved"] == 3
    assert m["primary_over_correct_views"]["answer_improved_rate"] == 1.0
    assert m["primary_over_correct_views"]["wrongful_suppression"] == 0
    assert m["controls_clean"] is True
    assert m["control_violations"] == []


def test_default_fixture_has_current_and_control_kinds():
    kinds = {c.kind for c in phase_d_cases()}
    assert {"current", "historical", "noview"} <= kinds
    assert sum(1 for c in phase_d_cases() if c.kind == "current") >= 3
