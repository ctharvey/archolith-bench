"""Offline tests for the independently labeled compositional scalar panel."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

from archolith_bench.compositional_scalar_panel import (
    PanelError,
    analyze_panel,
    load_panel,
    load_panel_menhir_api,
    source_sha256,
)


def _menhir_root() -> Path:
    candidates = []
    if os.environ.get("MENHIR_ROOT"):
        candidates.append(Path(os.environ["MENHIR_ROOT"]))
    candidates.extend((Path.cwd() / "menhir", Path.cwd().parent / "menhir"))
    for candidate in candidates:
        if (candidate / "src" / "menhir" / "services" / "structural_scalar_composer.py").is_file():
            return candidate.resolve()
    pytest.skip("set MENHIR_ROOT or provide a local ../menhir sibling")


@pytest.fixture(scope="module")
def api():
    return load_panel_menhir_api(_menhir_root())


def _span_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _positive_case(episode, *, case_id="case-positive", group_id="quantity-family"):
    span = "I have 12 books"
    start = episode["content"].index(span)
    return {
        "case_id": case_id,
        "namespace": episode["namespace"],
        "episode_uuid": episode["uuid"],
        "span_start": start,
        "span_end": start + len(span),
        "span_sha256": _span_hash(span),
        "kind": "positive",
        "group_id": group_id,
        "perturbation_id": "plain",
        "split": "holdout",
        "relation_group": "quantity",
        "expected": {
            "subject": "user",
            "relation_type": "quantity",
            "target": "books",
            "scope": "",
            "value_kind": "count",
            "value": 12,
            "unit": "",
            "operation": "absolute",
            "effective_time": None,
        },
    }


def _negative_case(episode):
    span = "I used to wake up at 7:30"
    start = episode["content"].index(span)
    return {
        "case_id": "case-negative",
        "namespace": episode["namespace"],
        "episode_uuid": episode["uuid"],
        "span_start": start,
        "span_end": start + len(span),
        "span_sha256": _span_hash(span),
        "kind": "negative",
        "group_id": "schedule-safety",
        "perturbation_id": "expired",
        "split": "holdout",
        "relation_group": "schedule_time",
        "expected": {
            "status": "abstain",
            "allowed_reason_codes": ["struct.operation_unsupported"],
            "risk_family": "past_only",
        },
    }


def _payload():
    episodes = [
        {"namespace": "generic-panel", "uuid": "episode-positive", "content": "I have 12 books."},
        {
            "namespace": "generic-panel",
            "uuid": "episode-negative",
            "content": "I used to wake up at 7:30.",
        },
    ]
    return {
        "schema_version": 1,
        "panel_id": "generic-scalar-panel-test",
        "non_lme": True,
        "split_policy": "whole_group_holdout",
        "source_sha256": source_sha256(episodes),
        "episodes": episodes,
        "cases": [_positive_case(episodes[0]), _negative_case(episodes[1])],
    }


def _write(tmp_path, payload):
    path = tmp_path / "panel.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_tiny_panel_scores_real_extractor_and_composer(tmp_path, api):
    path = _write(tmp_path, _payload())

    report = analyze_panel(
        path,
        menhir_root=_menhir_root(),
        generated_at="2026-08-05T00:00:00+00:00",
        enforce_population_requirements=False,
        api=api,
    )

    assert report["aggregate"]["positive"]["correct"] == 1
    assert report["aggregate"]["positive"]["coverage"]["ratio"] == 1.0
    assert report["aggregate"]["positive"]["exact_join_rate"]["ratio"] == 1.0
    assert report["aggregate"]["positive"]["wilson_lower_95"]["status"] == "measured"
    assert report["aggregate"]["negative"]["correct_abstention"] == 1
    assert report["aggregate"]["negative"]["unjoinable"] == 0
    assert report["aggregate"]["negative"]["false_current"] == 0
    assert report["aggregate"]["negative"]["false_current_rate"]["ratio"] == 0.0
    assert report["aggregate"]["promotion_status"] == "not_evaluable"
    assert report["provenance"]["llm_used"] is False


def test_wrong_expected_identity_reports_dimensions(tmp_path, api):
    payload = _payload()
    payload["cases"][0]["expected"]["target"] = "records"
    path = _write(tmp_path, payload)

    report = analyze_panel(
        path,
        menhir_root=_menhir_root(),
        enforce_population_requirements=False,
        api=api,
    )

    assert report["aggregate"]["positive"]["wrong"] == 1
    assert report["aggregate"]["positive"]["mismatch_dimension_counts"] == {"target": 1}
    assert report["cases"][0]["mismatch_dimensions"] == ["target"]


def test_zero_denominators_are_not_measured(tmp_path, api):
    payload = _payload()
    payload["cases"] = [payload["cases"][1]]
    path = _write(tmp_path, payload)

    report = analyze_panel(
        path,
        menhir_root=_menhir_root(),
        enforce_population_requirements=False,
        api=api,
    )

    assert report["aggregate"]["positive"]["precision"] == {
        "status": "not_measured",
        "numerator": None,
        "denominator": None,
        "ratio": None,
    }
    assert report["aggregate"]["positive"]["wilson_lower_95"] == {
        "status": "not_measured",
        "successes": None,
        "total": None,
        "lower": None,
    }


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda value: value.update({"unexpected": True}), "field mismatch"),
        (lambda value: value.update({"source_sha256": "0" * 64}), "source_sha256 mismatch"),
        (
            lambda value: value["cases"][0].update({"span_sha256": "0" * 64}),
            "span_sha256 mismatch",
        ),
        (
            lambda value: value["cases"][0]["expected"].update({"target": "Books"}),
            "canonical trim/lower text",
        ),
        (
            lambda value: value["cases"][0]["expected"].update({"target": "book  shelf"}),
            "canonical trim/lower text",
        ),
        (
            lambda value: value["cases"][1]["expected"].update(
                {"allowed_reason_codes": ["made-up"]}
            ),
            "known Menhir structural reason codes",
        ),
    ],
)
def test_panel_contract_fails_closed(tmp_path, api, mutate, message):
    payload = _payload()
    mutate(payload)
    path = _write(tmp_path, payload)

    with pytest.raises(PanelError, match=message):
        load_panel(path, api=api, enforce_population_requirements=False)


def test_group_split_leakage_is_rejected(tmp_path, api):
    payload = _payload()
    payload["cases"][1]["group_id"] = payload["cases"][0]["group_id"]
    payload["cases"][1]["split"] = "train"
    path = _write(tmp_path, payload)

    with pytest.raises(PanelError, match="group_id leaks"):
        load_panel(path, api=api, enforce_population_requirements=False)


def test_negative_without_exact_candidate_is_unjoinable_not_abstention(tmp_path, api):
    payload = _payload()
    episode = payload["episodes"][1]
    episode["content"] = "Could I wake up at 7:30?"
    case = payload["cases"][1]
    span = "Could I wake up at 7:30"
    case.update(
        {
            "span_start": 0,
            "span_end": len(span),
            "span_sha256": _span_hash(span),
            "perturbation_id": "question",
            "expected": {
                "status": "abstain",
                "allowed_reason_codes": ["struct.unsafe_question"],
                "risk_family": "question",
            },
        }
    )
    payload["source_sha256"] = source_sha256(payload["episodes"])
    path = _write(tmp_path, payload)

    report = analyze_panel(
        path,
        menhir_root=_menhir_root(),
        enforce_population_requirements=False,
        api=api,
    )

    assert report["aggregate"]["negative"]["correct_abstention"] == 0
    assert report["aggregate"]["negative"]["unjoinable"] == 1
    assert report["aggregate"]["negative"]["system_non_admission_rate"]["ratio"] == 1.0
    assert report["cases"][1]["outcome"] == "unjoinable_negative"


def test_episode_uuid_must_be_globally_unique(tmp_path, api):
    payload = _payload()
    payload["episodes"][1]["uuid"] = payload["episodes"][0]["uuid"]
    payload["episodes"][1]["namespace"] = "other-panel"
    payload["source_sha256"] = source_sha256(payload["episodes"])
    path = _write(tmp_path, payload)

    with pytest.raises(PanelError, match="globally unique"):
        load_panel(path, api=api, enforce_population_requirements=False)


def test_population_minimums_are_fail_closed_by_default(tmp_path, api):
    path = _write(tmp_path, _payload())

    with pytest.raises(PanelError, match="generic holdout minimums not met"):
        load_panel(path, api=api)
