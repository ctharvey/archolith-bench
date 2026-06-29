"""Tests for the IntentOracle bench prototype (menhir Phase 4).

Covers the four producer pieces (classifier / roles / matrix / oracle) and the
end-to-end ladder + promotion gate. Pure stdlib; runs in remote sessions.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from archolith_bench.intent.classifier import (
    IntentConfidence,
    TaskIntent,
    classify_intent,
    primary_intent,
)
from archolith_bench.intent.matrix import (
    Affinity,
    affinity,
    resolve_affinity,
    task_intents_to_query_intent,
)
from archolith_bench.intent.models import IntentFixture
from archolith_bench.intent.oracle import IntentOracle
from archolith_bench.intent.roles import ContentRole, derive_content_role
from archolith_bench.intent.runner import IntentBenchmarkRunner
from archolith_bench.oracle.models import CandidateMemory, OraclePolarity, QueryContext

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "intent_floor_corpus.json"


# --- classifier -------------------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    ("why is the floor failing", TaskIntent.DEBUG_FAILURE),
    ("have we already tried this floor", TaskIntent.AVOID_REPEAT),
    ("why did we choose the floor", TaskIntent.EXPLAIN_DECISION),
    ("is the floor doc still accurate", TaskIntent.VERIFY_CURRENTNESS),
    ("which benchmark verifies the floor", TaskIntent.EVIDENCE_LOOKUP),
    ("what changed in the floor", TaskIntent.CHANGE_ANALYSIS),
    ("what should i do next on the floor", TaskIntent.PLAN_NEXT_ACTION),
    ("how does the floor work", TaskIntent.UNDERSTAND_SYSTEM),
])
def test_classifier_primary_intent(text: str, expected: TaskIntent) -> None:
    hits, conf = classify_intent(text)
    assert primary_intent(hits) is expected
    assert conf is IntentConfidence.HIGH


def test_classifier_default_is_low_confidence() -> None:
    hits, conf = classify_intent("floor recall vector cosine")
    assert primary_intent(hits) is TaskIntent.UNDERSTAND_SYSTEM
    assert conf is IntentConfidence.LOW


def test_classifier_returns_cue() -> None:
    hits, _ = classify_intent("why is it failing")
    assert any(h.cue == "failing" for h in hits)


def test_classifier_multi_hit() -> None:
    # AVOID_REPEAT ("already tried") + DEBUG_FAILURE ("failing")
    hits, _ = classify_intent("have we already tried fixing the failing floor")
    intents = {h.intent for h in hits}
    assert TaskIntent.AVOID_REPEAT in intents
    assert TaskIntent.DEBUG_FAILURE in intents
    assert primary_intent(hits) is TaskIntent.AVOID_REPEAT  # precedence


# --- roles ------------------------------------------------------------------

@pytest.mark.parametrize("artifact_type,role", [
    ("failure", ContentRole.FAILURE),
    ("decision", ContentRole.DECISION),
    ("experiment", ContentRole.EXPERIMENT),
    ("benchmark", ContentRole.BENCHMARK),
    ("plan", ContentRole.PLAN),
    ("evidence", ContentRole.EVIDENCE),
])
def test_role_from_artifact_type(artifact_type: str, role: ContentRole) -> None:
    assert role in derive_content_role({"artifact_type": artifact_type})


def test_role_default_is_reference() -> None:
    assert derive_content_role({}) == {ContentRole.REFERENCE}


def test_role_from_anchor_and_evidence() -> None:
    roles = derive_content_role({"anchors": (".agent/plans/x-plan.md",), "evidence_kinds": ("test",)})
    assert ContentRole.PLAN in roles
    assert ContentRole.TEST in roles


# --- matrix -----------------------------------------------------------------

def test_matrix_signs_load_bearing_cells() -> None:
    assert affinity(TaskIntent.DEBUG_FAILURE, ContentRole.FAILURE) is Affinity.PREFER
    assert affinity(TaskIntent.EXPLAIN_DECISION, ContentRole.DECISION) is Affinity.PREFER
    assert affinity(TaskIntent.PLAN_NEXT_ACTION, ContentRole.PLAN) is Affinity.PREFER
    assert affinity(TaskIntent.UNDERSTAND_SYSTEM, ContentRole.REFERENCE) is Affinity.PREFER
    assert affinity(TaskIntent.UNDERSTAND_SYSTEM, ContentRole.INCIDENT) is Affinity.PENALIZE


def test_resolve_affinity_max_over_cross_product() -> None:
    # one intent prefers FAILURE, other penalizes; max wins -> PREFER
    aff, win_intent, win_role = resolve_affinity(
        [TaskIntent.DEBUG_FAILURE, TaskIntent.UNDERSTAND_SYSTEM],
        {ContentRole.FAILURE, ContentRole.REFERENCE},
    )
    assert aff is Affinity.PREFER


def test_status_lens_history_wins_on_conflict() -> None:
    # AVOID_REPEAT wants history, DEBUG wants current -> history wins
    assert task_intents_to_query_intent([TaskIntent.AVOID_REPEAT, TaskIntent.DEBUG_FAILURE]) == "historical"
    assert task_intents_to_query_intent([TaskIntent.DEBUG_FAILURE]) == "current"


# --- oracle -----------------------------------------------------------------

def test_oracle_prefers_matching_role() -> None:
    ctx = QueryContext(text="why is the floor failing")
    failure = CandidateMemory(id="f", content="x", metadata={"artifact_type": "failure"})
    decision = CandidateMemory(id="d", content="x", metadata={"artifact_type": "decision"})
    assert IntentOracle().evaluate(ctx, failure).probability > IntentOracle().evaluate(ctx, decision).probability


def test_oracle_neutral_on_low_confidence() -> None:
    ctx = QueryContext(text="floor recall vector")  # no intent cue
    res = IntentOracle().evaluate(ctx, CandidateMemory(id="f", content="x", metadata={"artifact_type": "failure"}))
    assert res.polarity is OraclePolarity.NEUTRAL


def test_oracle_never_contradicts() -> None:
    # even a penalized role is SUPPORT(low) or NEUTRAL, never CONTRADICT (pure relevance).
    ctx = QueryContext(text="how does the floor work")
    res = IntentOracle().evaluate(ctx, CandidateMemory(id="i", content="x", metadata={"artifact_type": "incident"}))
    assert res.polarity in (OraclePolarity.SUPPORT, OraclePolarity.NEUTRAL)


def test_oracle_is_read_only() -> None:
    md = {"artifact_type": "failure"}
    cand = CandidateMemory(id="f", content="x", metadata=md)
    IntentOracle().evaluate(QueryContext(text="why is it failing"), cand)
    assert md == {"artifact_type": "failure"}  # caller's dict untouched


# --- end-to-end -------------------------------------------------------------

def test_fixture_loads() -> None:
    fx = IntentFixture.from_file(FIXTURE)
    assert fx.memories and fx.queries and fx.no_harm_queries


def test_ladder_graduates() -> None:
    art = IntentBenchmarkRunner(IntentFixture.from_file(FIXTURE)).run()
    ic = art["intent_correct_at_1"]
    assert ic["intent_on"] > ic["baseline"]
    assert art["determinism"] == 1.0
    assert art["promotion_gate"]["graduates"] is True
