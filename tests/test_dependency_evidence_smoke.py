from __future__ import annotations

import json
from pathlib import Path

import pytest

from archolith_bench.dependency_evidence_spacy import (
    CandidateLocator,
    ParsedSpan,
    emit_dependency_evidence,
    parse_with_spacy,
)

FIXTURE = Path(__file__).parents[1] / "fixtures" / "dependency_evidence_smoke_v1.json"


def test_smoke_fixture_is_small_split_disjoint_and_source_authored() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    cases = payload["cases"]

    assert payload["schema_version"] == "dependency-evidence-smoke-v1"
    assert len(cases) == 6
    assert {case["split"] for case in cases} == {"train", "holdout"}
    assert sum(case["expected"]["admit"] for case in cases) == 3
    assert sum(not case["expected"]["admit"] for case in cases) == 3
    assert sum(case["expected"]["admit"] for case in cases if case["split"] == "train") == 2
    assert sum(case["expected"]["admit"] for case in cases if case["split"] == "holdout") == 1
    assert len({case["case_id"] for case in cases}) == len(cases)
    assert all("benchmark" not in case["source"].lower() for case in cases)
    assert all("lme" not in case["source"].lower() for case in cases)

    train_sources = {case["source"] for case in cases if case["split"] == "train"}
    holdout_sources = {case["source"] for case in cases if case["split"] == "holdout"}
    assert train_sources.isdisjoint(holdout_sources)


def test_smoke_fixture_syntax_annotations_match_pinned_adapter() -> None:
    pytest.importorskip("spacy")
    pytest.importorskip("en_core_web_sm")
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    for case in payload["cases"]:
        syntax = case["syntax"]
        source = case["source"]
        candidate = CandidateLocator(*syntax["candidate_span"], candidate_hash="a" * 64)
        numeric = ParsedSpan(*syntax["numeric_value_span"])
        outcome = parse_with_spacy(
            source,
            candidate,
            numeric,
            model_name="en_core_web_sm",
            config={},
        )
        assert outcome.status == "parsed", (case["case_id"], outcome.reason)
        assert outcome.document is not None
        document = outcome.document
        observed = {
            "candidate_span": [document.clause_span.start, document.clause_span.end],
            "numeric_value_span": [document.cues.numeric_value.start, document.cues.numeric_value.end],
            "subject_span": [document.cues.subject.start, document.cues.subject.end] if document.cues.subject else None,
            "predicate_span": [document.cues.predicate.start, document.cues.predicate.end] if document.cues.predicate else None,
            "target_span": [document.cues.target.start, document.cues.target.end] if document.cues.target else None,
            "marker_categories": sorted({marker.category for marker in document.markers}),
            "clause_root_token": document.cues.clause_root_token,
        }
        assert observed == syntax, case["case_id"]
        emission = emit_dependency_evidence(document, candidate)
        assert emission.status == "emitted", (case["case_id"], emission.reason)
        assert emission.evidence is not None
        evidence_json = json.dumps(emission.evidence, sort_keys=True)
        assert source not in evidence_json
        for forbidden in ("admission", "currentness", "relation", "operation", "identity"):
            assert forbidden not in evidence_json
        # Semantic labels remain fixture annotations; this parser assertion does not infer them.
        assert set(case["expected"]) >= {"semantic_role", "admit"}
