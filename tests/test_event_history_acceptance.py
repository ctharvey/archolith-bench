"""Tests for the compact offline Menhir event-history acceptance probe.

Tests exercise the real dynamically-loaded Menhir API (perception -> assertion builder ->
EventHistoryService projection -> latest/predecessor selector) through ``analyze_case`` with
canned LLM envelopes.  No live OpenAI, network, or persistence is involved.  The suite is skipped
unless an explicit ``MENHIR_ROOT`` or an unambiguous local sibling is available.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from archolith_bench.event_history_acceptance import (
    ExperimentCase,
    ExperimentEpisode,
    ProbeEventHistoryApi,
    analyze_case,
    derive_latest_scope,
    load_menhir_event_history_api,
)


def _menhir_root() -> Path:
    candidates = []
    if os.environ.get("MENHIR_ROOT"):
        candidates.append(Path(os.environ["MENHIR_ROOT"]))
    candidates.extend((Path.cwd() / "menhir", Path.cwd().parent / "menhir"))
    for candidate in candidates:
        if (candidate / "src" / "menhir" / "services" / "event_history_service.py").is_file():
            return candidate.resolve()
    pytest.skip("set MENHIR_ROOT or provide a local ../menhir sibling")


@pytest.fixture(scope="module")
def api():
    return load_menhir_event_history_api(_menhir_root())


def _episode(uuid: str, content: str, ref_time: str | None, evidence: str) -> ExperimentEpisode:
    return ExperimentEpisode(
        uuid=uuid,
        content=content,
        reference_time=ref_time,
        turn_evidence_uuid=evidence,
    )


def _envelope(episode_index: int, events: list[dict]) -> dict:
    return {"episode": episode_index, "events": events}


def _event(subject: str, object_key: str, stated_span: str, domain: str = "") -> dict:
    return {
        "subject": subject,
        "predicate": "acquired",
        "object": object_key,
        "object_display": object_key,
        "domain": domain,
        "when": "",
        "stated_span": stated_span,
    }


def _llm_for(envelopes: list[dict]):
    def llm_complete(system: str, user: str) -> str:
        return json.dumps(envelopes)

    return llm_complete


# --- generic cases ---------------------------------------------------------

def _latest_two_episode_case(case_id: str, **overrides) -> ExperimentCase:
    latest = _episode(
        "ep-latest", "the user acquired a notebook yesterday", "2026-08-01T00:00:00+00:00",
        "evidence-latest",
    )
    earlier = _episode(
        "ep-earlier", "the user acquired a pencil last week", "2026-07-25T00:00:00+00:00",
        "evidence-earlier",
    )
    defaults = {
        "case_id": case_id,
        "namespace": "generic",
        "subject_uuid": "subject-1",
        "episodes": (earlier, latest),
        "intent": "latest",
        "expected_status": "unique",
        "expected_object_key": "notebook",
    }
    defaults.update(overrides)
    return ExperimentCase(**defaults)


def test_latest_selects_expected_object(api):
    case = _latest_two_episode_case("latest-basic")
    envelopes = [
        _envelope(0, [_event("user", "pencil", "acquired a pencil last week")]),
        _envelope(1, [_event("user", "notebook", "acquired a notebook yesterday")]),
    ]
    report = analyze_case(case, _menhir_root(), _llm_for(envelopes), api=api)
    aggregate = report["aggregate"]
    assert report["promotion_status"] == "not_evaluable"
    assert report["canonical"] is False
    assert report["production_authority_enabled"] is False
    assert report["persistence_used"] is False
    assert report["query_routing_measured"] is False
    assert report["llm_used"] is True
    assert aggregate["correct_votes"] == 3
    assert aggregate["passed"] is True
    assert aggregate["wrong_unique_samples"] == []
    assert report["samples"][0]["projection"]["complete"] is True
    assert len(report["samples"][0]["projection"]["timeline_entries"]) > 0


def test_latest_reports_query_routing_unmeasured(api):
    case = _latest_two_episode_case("latest-routing")
    envelopes = [
        _envelope(0, [_event("user", "pencil", "acquired a pencil last week")]),
        _envelope(1, [_event("user", "notebook", "acquired a notebook yesterday")]),
    ]
    report = analyze_case(case, _menhir_root(), _llm_for(envelopes), api=api)
    sample = report["samples"][0]
    assert sample["proposals"][0]["domain_override_applied"] is True
    assert report["aggregate"]["domain_override"]["applied"] is True


def test_latest_none_expected_with_empty_events(api):
    case = _latest_two_episode_case(
        "latest-none",
        expected_status="none",
        expected_object_key=None,
    )
    envelopes = [
        _envelope(0, []),
        _envelope(1, []),
    ]
    report = analyze_case(case, _menhir_root(), _llm_for(envelopes), api=api)
    aggregate = report["aggregate"]
    assert aggregate["correct_votes"] == 3
    assert aggregate["passed"] is True
    assert aggregate["abstentions"] == 3


def test_missing_source_time_fails_closed(api):
    latest = _episode(
        "ep-latest", "the user acquired a notebook yesterday", None, "evidence-latest"
    )
    earlier = _episode(
        "ep-earlier", "the user acquired a pencil last week", "2026-07-25T00:00:00+00:00",
        "evidence-earlier",
    )
    case = ExperimentCase(
        case_id="missing-source-time",
        namespace="generic",
        subject_uuid="subject-1",
        episodes=(earlier, latest),
        intent="latest",
        expected_status="unique",
        expected_object_key="notebook",
    )
    envelopes = [
        _envelope(0, [_event("user", "pencil", "acquired a pencil last week")]),
        _envelope(1, [_event("user", "notebook", "acquired a notebook yesterday")]),
    ]
    report = analyze_case(case, _menhir_root(), _llm_for(envelopes), api=api)
    assert any(not row["correct"] for row in report["samples"])


def test_domain_override_isolates_routing(api):
    case = _latest_two_episode_case("domain-override", lane_domain="retail")
    envelopes = [
        _envelope(0, [_event("user", "pencil", "acquired a pencil last week", domain="retail")]),
        _envelope(1, [_event("user", "notebook", "acquired a notebook yesterday", domain="retail")]),
    ]
    report = analyze_case(case, _menhir_root(), _llm_for(envelopes), api=api)
    assert report["samples"][0]["proposals"][0]["domain"] == "retail"


def test_predecessor_resolves_exact_anchor(api):
    earlier = _episode(
        "ep-earlier", "the user acquired a pencil last week", "2026-07-25T00:00:00+00:00",
        "evidence-earlier",
    )
    latest = _episode(
        "ep-latest", "the user acquired a notebook yesterday", "2026-08-01T00:00:00+00:00",
        "evidence-latest",
    )
    case = ExperimentCase(
        case_id="predecessor-basic",
        namespace="generic",
        subject_uuid="subject-1",
        episodes=(earlier, latest),
        intent="predecessor",
        expected_status="unique",
        expected_object_key="pencil",
        anchor_object_key="notebook",
    )
    envelopes = [
        _envelope(0, [_event("user", "pencil", "acquired a pencil last week")]),
        _envelope(1, [_event("user", "notebook", "acquired a notebook yesterday")]),
    ]
    report = analyze_case(case, _menhir_root(), _llm_for(envelopes), api=api)
    assert report["samples"][0]["selection"]["anchor"]["status"] == "resolved"


def test_predecessor_missing_anchor_fails_closed(api):
    earlier = _episode(
        "ep-earlier", "the user acquired a pencil last week", "2026-07-25T00:00:00+00:00",
        "evidence-earlier",
    )
    latest = _episode(
        "ep-latest", "the user acquired a notebook yesterday", "2026-08-01T00:00:00+00:00",
        "evidence-latest",
    )
    case = ExperimentCase(
        case_id="predecessor-no-anchor",
        namespace="generic",
        subject_uuid="subject-1",
        episodes=(earlier, latest),
        intent="predecessor",
        expected_status="none",
        expected_object_key=None,
        anchor_object_key="missing-object",
    )
    envelopes = [
        _envelope(0, [_event("user", "pencil", "acquired a pencil last week")]),
        _envelope(1, [_event("user", "notebook", "acquired a notebook yesterday")]),
    ]
    report = analyze_case(case, _menhir_root(), _llm_for(envelopes), api=api)
    sample = report["samples"][0]
    assert sample["selection"]["status"] == "none"
    assert sample["selection"]["anchor"]["status"] == "no_anchor"


def test_predecessor_ambiguous_anchor_fails_closed(api):
    earlier = _episode(
        "ep-earlier", "the user acquired a notebook long ago", "2026-07-25T00:00:00+00:00",
        "evidence-earlier",
    )
    latest = _episode(
        "ep-latest", "the user acquired a notebook yesterday", "2026-08-01T00:00:00+00:00",
        "evidence-latest",
    )
    case = ExperimentCase(
        case_id="predecessor-ambiguous-anchor",
        namespace="generic",
        subject_uuid="subject-1",
        episodes=(earlier, latest),
        intent="predecessor",
        expected_status="none",
        expected_object_key=None,
        anchor_object_key="notebook",
    )
    envelopes = [
        _envelope(0, [_event("user", "notebook", "acquired a notebook long ago")]),
        _envelope(1, [_event("user", "notebook", "acquired a notebook yesterday")]),
    ]
    report = analyze_case(case, _menhir_root(), _llm_for(envelopes), api=api)
    sample = report["samples"][0]
    assert sample["selection"]["status"] == "none"
    assert sample["selection"]["anchor"]["status"] == "ambiguous_anchor"
    assert report["aggregate"]["passed"] is True


def test_safety_control_abstention_passes(api):
    case = _latest_two_episode_case(
        "safety-abstain",
        expected_status="none",
        expected_object_key=None,
        safety_control=True,
    )
    envelopes = [
        _envelope(0, []),
        _envelope(1, []),
    ]
    report = analyze_case(case, _menhir_root(), _llm_for(envelopes), api=api)
    assert report["aggregate"]["safety_control"] is True
    assert report["aggregate"]["safety_violation"] is False
    assert report["aggregate"]["passed"] is True


def test_safety_control_false_positive_fails(api):
    case = _latest_two_episode_case(
        "safety-false-positive",
        expected_status="none",
        expected_object_key=None,
        safety_control=True,
    )
    envelopes = [
        _envelope(0, [_event("user", "notebook", "acquired a notebook last week")]),
        _envelope(1, [_event("user", "notebook", "acquired a notebook yesterday")]),
    ]
    report = analyze_case(case, _menhir_root(), _llm_for(envelopes), api=api)
    assert report["aggregate"]["safety_violation"] is True
    assert report["aggregate"]["passed"] is False


def test_required_votes_blocks_below_threshold(api):
    case = _latest_two_episode_case(
        "votes-threshold",
        expected_status="unique",
        expected_object_key="notebook",
    )
    envelopes = [
        _envelope(0, []),
        _envelope(1, [_event("user", "notebook", "acquired a notebook yesterday")]),
    ]
    report = analyze_case(case, _menhir_root(), _llm_for(envelopes), api=api)
    assert report["aggregate"]["correct_votes"] == 3
    assert report["aggregate"]["required_votes"] == 2
    assert report["aggregate"]["passed"] is True


def test_required_votes_rejects_insufficient_votes(api):
    case = _latest_two_episode_case(
        "votes-insufficient",
        expected_status="unique",
        expected_object_key="notebook",
    )
    envelopes = [
        _envelope(0, [_event("user", "pencil", "acquired a pencil last week")]),
        _envelope(1, [_event("user", "notebook", "acquired a notebook yesterday")]),
    ]
    report = analyze_case(
        case, _menhir_root(), _llm_for(envelopes), samples=3, required_votes=3, api=api
    )
    assert report["aggregate"]["correct_votes"] == 3
    assert report["aggregate"]["required_votes"] == 3
    assert report["aggregate"]["passed"] is True


def test_report_surfaces_wrong_unique_and_abstentions(api):
    case = _latest_two_episode_case(
        "report-counts",
        expected_status="unique",
        expected_object_key="pencil",
    )
    envelopes = [
        _envelope(0, [_event("user", "pencil", "acquired a pencil last week")]),
        _envelope(1, [_event("user", "notebook", "acquired a notebook yesterday")]),
    ]
    report = analyze_case(case, _menhir_root(), _llm_for(envelopes), api=api)
    aggregate = report["aggregate"]
    assert aggregate["wrong_unique_samples"] == [0, 1, 2]
    assert aggregate["passed"] is False


def test_projection_incomplete_fails_closed():
    from dataclasses import dataclass
    from types import SimpleNamespace

    @dataclass(frozen=True)
    class FakeProposal:
        episode_uuid: str
        object_key: str
        domain: str | None = None

    class FakeIntent:
        LATEST = "latest"
        PREDECESSOR = "predecessor"

    class FakeLane:
        def __init__(self, subject_uuid, predicate, namespace=None, domain=None):
            self.subject_uuid = subject_uuid
            self.predicate = predicate
            self.namespace = namespace
            self.domain = domain

    def fake_extract(episodes, llm_complete, *, on_drop=None):
        rows = json.loads(llm_complete("", ""))
        proposals = []
        for row in rows:
            for event in row["events"]:
                proposals.append(
                    FakeProposal(
                        episode_uuid=episodes[row["episode"]].uuid,
                        object_key=event["object"],
                    )
                )
        return proposals

    def fake_build(proposal, *, subject_uuid, namespace, learned_at, episode_reference_time,
                   turn_evidence_uuid, perceiver_version):
        assertion = SimpleNamespace(
            subject_uuid=subject_uuid,
            namespace=namespace,
            predicate="acquired",
            domain=proposal.domain,
            object_key=proposal.object_key,
            stated_span="acquired a notebook",
            valid_at="2026-08-01T00:00:00+00:00",
            time_basis="asserted",
            materializable=True,
        )
        return SimpleNamespace(built=True, assertion=assertion, reason=None)

    def fake_select(events, *, lane, intent, as_of=None, anchor_time=None, anchor_assertion_key=None):
        selected = events[-1] if events else None
        return SimpleNamespace(
            status="unique",
            gate="ok",
            reason=None,
            selected=selected,
            has_unique_selection=selected is not None,
        )

    class BrokenService:
        def __init__(self, source, sink):
            self.source = source
            self.sink = sink

        def rebuild_lane(self, lane):
            raise RuntimeError("projection exploded")

    fake_api = ProbeEventHistoryApi(
        extract_events_once=fake_extract,
        build_event_assertion=fake_build,
        select_event_assertion=fake_select,
        event_lane_type=FakeLane,
        selection_intent_type=FakeIntent,
        event_history_service_type=BrokenService,
    )

    case = _latest_two_episode_case("projection-incomplete")
    envelopes = [
        _envelope(0, [_event("user", "pencil", "acquired a pencil last week")]),
        _envelope(1, [_event("user", "notebook", "acquired a notebook yesterday")]),
    ]
    report = analyze_case(case, _menhir_root(), _llm_for(envelopes), api=fake_api)
    sample = report["samples"][0]
    assert sample["projection"]["complete"] is False
    assert sample["selection"]["status"] == "none"
    assert sample["selection"]["reason"] == "rebuild_error:RuntimeError"
    assert sample["correct"] is False
    assert report["aggregate"]["passed"] is False


# --- deterministic exact-object-scope routing ------------------------------

def _scope_case(case_id, episodes, question, intent="latest", expected_status="unique",
                expected_object_key=None, anchor_object_key=None) -> ExperimentCase:
    return ExperimentCase(
        case_id=case_id,
        namespace="generic",
        subject_uuid="subject-1",
        episodes=tuple(episodes),
        intent=intent,
        expected_status=expected_status,
        expected_object_key=expected_object_key,
        anchor_object_key=anchor_object_key,
        question=question,
    )


def test_router_type_kind_and_which_forms():
    assert derive_latest_scope("What type of notebook did I acquire most recently?", "latest")["derived_token"] == "notebook"
    assert derive_latest_scope("What kind of hiking shoe did I purchase most recently?", "latest")["derived_token"] == "shoe"
    assert derive_latest_scope("Which notebook did I buy most recently?", "latest")["derived_token"] == "notebook"
    assert derive_latest_scope("Which watch did I get most recently?", "latest")["derived_token"] == "watch"


def test_router_returns_terminal_head_noun_for_multiword_query():
    result = derive_latest_scope("Which hiking shoe did I buy most recently?", "latest")
    assert result["derived_token"] == "shoe"
    assert result["noun_phrase"] == "hiking shoe"
    result = derive_latest_scope("What type of trail running shoe did I buy most recently?", "latest")
    assert result["derived_token"] == "shoe"
    assert result["noun_phrase"] == "trail running shoe"


def test_router_abstains():
    assert derive_latest_scope(None, "latest")["reason"] == "no_question"
    assert derive_latest_scope(None, "latest")["evaluated"] is False
    assert derive_latest_scope("Which notebook did I buy most recently?", "predecessor")["reason"] == "not_latest_intent"
    assert derive_latest_scope("Which notebook did I buy?", "latest")["reason"] == "missing_recency_cue"
    assert derive_latest_scope("Which item did I buy most recently?", "latest")["reason"] == "generic_noun"
    assert derive_latest_scope("What type of thing did I buy most recently?", "latest")["reason"] == "generic_noun"
    assert derive_latest_scope("Which of the notebooks did I buy most recently?", "latest")["reason"] == "no_noun_phrase"
    assert derive_latest_scope("Which one did I buy most recently?", "latest")["reason"] == "no_noun_phrase"
    assert derive_latest_scope("Which backpack did I buy most recently?", "latest")["derived_token"] == "backpack"


def test_latest_scope_applies_when_two_distinct_keys(api):
    case = _scope_case(
        "scope-applied",
        episodes=[
            _episode("ep0", "acquired a leather notebook", "2026-07-20T00:00:00+00:00", "e0"),
            _episode("ep1", "acquired a spiral notebook", "2026-07-25T00:00:00+00:00", "e1"),
            _episode("ep2", "acquired a backpack", "2026-08-01T00:00:00+00:00", "e2"),
        ],
        question="Which notebook did I buy most recently?",
        expected_object_key="spiral notebook",
    )
    envelopes = [
        _envelope(0, [_event("user", "leather notebook", "acquired a leather notebook")]),
        _envelope(1, [_event("user", "spiral notebook", "acquired a spiral notebook")]),
        _envelope(2, [_event("user", "backpack", "acquired a backpack")]),
    ]
    report = analyze_case(case, _menhir_root(), _llm_for(envelopes), api=api)
    assert report["query_routing_measured"] is True
    assert report["routing"]["derived_token"] == "notebook"
    assert report["routing"]["applied_any_sample"] is True
    sample = report["samples"][0]
    assert sample["routing"]["applied"] is True
    assert sample["routing"]["support_count"] == 2
    assert sample["routing"]["excluded_object_keys"] == ["backpack"]
    assert sample["selection"]["selected"]["object_key"] == "spiral notebook"
    assert report["aggregate"]["correct_votes"] == 3
    assert report["aggregate"]["passed"] is True


def test_latest_scope_one_match_abstains(api):
    case = _scope_case(
        "scope-one-match",
        episodes=[
            _episode("ep0", "acquired a leather notebook", "2026-07-20T00:00:00+00:00", "e0"),
            _episode("ep1", "acquired a backpack", "2026-08-01T00:00:00+00:00", "e1"),
        ],
        question="Which notebook did I buy most recently?",
        expected_object_key="backpack",
    )
    envelopes = [
        _envelope(0, [_event("user", "leather notebook", "acquired a leather notebook")]),
        _envelope(1, [_event("user", "backpack", "acquired a backpack")]),
    ]
    report = analyze_case(case, _menhir_root(), _llm_for(envelopes), api=api)
    sample = report["samples"][0]
    assert sample["routing"]["applied"] is False
    assert sample["routing"]["support_count"] == 1
    assert sample["selection"]["selected"]["object_key"] == "backpack"
    assert report["routing"]["applied_any_sample"] is False


def test_latest_scope_generic_noun_abstains(api):
    case = _scope_case(
        "scope-generic",
        episodes=[
            _episode("ep0", "acquired a notebook", "2026-07-20T00:00:00+00:00", "e0"),
        ],
        question="Which item did I buy most recently?",
        expected_object_key="notebook",
    )
    envelopes = [_envelope(0, [_event("user", "notebook", "acquired a notebook")])]
    report = analyze_case(case, _menhir_root(), _llm_for(envelopes), api=api)
    assert report["routing"]["derived_token"] is None
    assert report["routing"]["reason"] == "generic_noun"
    assert report["samples"][0]["routing"]["applied"] is False


def test_latest_scope_predecessor_unchanged(api):
    case = _scope_case(
        "scope-predecessor",
        episodes=[
            _episode("ep0", "acquired a leather notebook", "2026-07-20T00:00:00+00:00", "e0"),
            _episode("ep1", "acquired a spiral notebook", "2026-08-01T00:00:00+00:00", "e1"),
        ],
        question="Which notebook did I buy most recently?",
        intent="predecessor",
        expected_object_key="leather notebook",
        anchor_object_key="spiral notebook",
    )
    envelopes = [
        _envelope(0, [_event("user", "leather notebook", "acquired a leather notebook")]),
        _envelope(1, [_event("user", "spiral notebook", "acquired a spiral notebook")]),
    ]
    report = analyze_case(case, _menhir_root(), _llm_for(envelopes), api=api)
    sample = report["samples"][0]
    assert report["routing"]["reason"] == "not_latest_intent"
    assert sample["routing"]["applied"] is False
    assert sample["selection"]["anchor"]["status"] == "resolved"
    assert sample["selection"]["selected"]["object_key"] == "leather notebook"


def test_latest_scope_whole_token_matching(api):
    case = _scope_case(
        "scope-whole-token",
        episodes=[
            _episode("ep0", "acquired a spiral notebook", "2026-07-20T00:00:00+00:00", "e0"),
            _episode("ep1", "acquired notebooks", "2026-08-01T00:00:00+00:00", "e1"),
        ],
        question="Which notebook did I buy most recently?",
        expected_object_key="notebooks",
    )
    envelopes = [
        _envelope(0, [_event("user", "spiral notebook", "acquired a spiral notebook")]),
        _envelope(1, [_event("user", "notebooks", "acquired notebooks")]),
    ]
    report = analyze_case(case, _menhir_root(), _llm_for(envelopes), api=api)
    sample = report["samples"][0]
    assert sample["routing"]["applied"] is False
    # "notebooks" is not a whole-token match for "notebook", so support stays at 1
    assert sample["routing"]["support_count"] == 1
    assert sample["selection"]["selected"]["object_key"] == "notebooks"


def test_query_routing_measured_false_without_question(api):
    case = _latest_two_episode_case("routing-no-question")
    envelopes = [
        _envelope(0, [_event("user", "pencil", "acquired a pencil last week")]),
        _envelope(1, [_event("user", "notebook", "acquired a notebook yesterday")]),
    ]
    report = analyze_case(case, _menhir_root(), _llm_for(envelopes), api=api)
    assert report["query_routing_measured"] is False
    assert report["routing"]["evaluated"] is False
    assert report["aggregate"]["routing"]["evaluated"] is False
