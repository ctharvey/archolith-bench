from __future__ import annotations

import json
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest

from archolith_bench.dependency_scalar_bridge_measurement import (
    FIXTURE_SHA256,
    FIXTURE_VERSION,
    MeasurementError,
    _cue_and_edge_scores,
    _f1,
    _artifact_anchors,
    _git_identity,
    _identity_exact,
    _raw_candidate,
    _safe_ratio,
    _semantic_replay_signature,
    load_fixture,
    load_menhir_apis,
    resolve_menhir_root,
    measure_cases,
    write_outputs,
)


FIXTURE = Path(__file__).parents[1] / "fixtures" / "dependency_evidence_bridge_ops_v1.json"


def test_frozen_fixture_guard_loads_exact_sha_and_version() -> None:
    payload, actual_sha = load_fixture(FIXTURE)
    assert actual_sha == FIXTURE_SHA256
    assert payload["fixture_version"] == FIXTURE_VERSION
    assert len(payload["cases"]) == 48


def test_frozen_fixture_guard_rejects_expected_sha_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    import archolith_bench.dependency_scalar_bridge_measurement as measurement

    monkeypatch.setattr(measurement, "FIXTURE_SHA256", "0" * 64)
    with pytest.raises(MeasurementError, match="fixture_sha_or_version_mismatch"):
        load_fixture(FIXTURE)


def test_frozen_fixture_guard_rejects_manifest_denominator_drift() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    payload["metadata"]["denominators"]["gold_edge_count"] = 143
    path = Path(__file__).parent / f"dependency-bridge-manifest-{uuid.uuid4().hex}.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    try:
        with pytest.raises(MeasurementError, match="fixture_sha_or_version_mismatch"):
            load_fixture(path)
    finally:
        path.unlink(missing_ok=True)


def test_raw_candidate_is_unadmitted_and_preserves_signed_delta() -> None:
    payload, _ = load_fixture(FIXTURE)
    delta = next(case for case in payload["cases"] if case["operation_gold"] == "delta" and case["value"]["sign"] < 0)
    candidate = _raw_candidate(delta)
    assert candidate["episode"] == 0
    assert candidate["subject"] == delta["gold_dependency_path"]["node_literals"]["subject"]
    assert candidate["attribute"] == "bridge_measurement"
    assert candidate["operation"] == "delta"
    assert candidate["value"] == -delta["value"]["magnitude"]
    assert candidate["stated_span"] == delta["claim_span"]["text"]
    assert "admit_gold" not in candidate

    event = next(case for case in payload["cases"] if case["operation_gold"] is None)
    assert _raw_candidate(event)["operation"] == "absolute"


def test_menhir_root_resolution_is_explicit_and_import_identity_is_checked() -> None:
    root = resolve_menhir_root()
    assert (root / "src" / "menhir").is_dir()
    api = load_menhir_apis(root)
    assert callable(api.adapt_research_candidate)
    assert callable(api.compose_dependency_scalar_identity)


def test_git_identity_uses_local_safe_directory_and_untracked_status(monkeypatch: pytest.MonkeyPatch) -> None:
    import archolith_bench.dependency_scalar_bridge_measurement as measurement

    calls: list[list[str]] = []

    def fake_run(args: list[str], **_: object) -> SimpleNamespace:
        calls.append(args)
        return SimpleNamespace(stdout=("head" if "rev-parse" in args else "?? untracked"))

    monkeypatch.setattr(measurement.subprocess, "run", fake_run)
    result = _git_identity(Path.cwd())
    assert result == {"head": "head", "dirty": True}
    assert all("safe.directory=" in " ".join(call) for call in calls)
    assert any("--porcelain" in call and "--untracked-files=no" not in call for call in calls)


def test_artifact_anchors_are_relative_and_sha256_only() -> None:
    root = resolve_menhir_root()
    anchors = _artifact_anchors(Path(__file__).parents[1], root)
    assert len(anchors) == 9
    assert all(item["path"].startswith(("archolith_bench/", "src/menhir/")) for item in anchors)
    assert all(len(item["sha256"]) == 64 for item in anchors)


def test_cue_and_edge_scoring_uses_gold_offsets_not_role_labels() -> None:
    case = {
        "gold_dependency_path": {
            "node_char_offsets": {"subject": 0, "predicate": 2, "numeric": 7, "target": 9},
            "node_literals": {"subject": "I", "predicate": "have", "numeric": "4", "target": "maps"},
            "edges": [
                {"head_char": 2, "dependent_char": 0, "dependency_label": "nsubj"},
                {"head_char": 9, "dependent_char": 7, "dependency_label": "nummod"},
                {"head_char": 2, "dependent_char": 9, "dependency_label": "dobj"},
            ],
        }
    }
    payload = {
        "cues": {
            "subject": {"start": 0, "end": 1},
            "predicate": {"start": 2, "end": 6},
            "numeric_value": {"start": 7, "end": 8},
            "target": {"start": 9, "end": 13},
        },
        "tokens": [
            {"token_index": 0, "span": {"start": 0, "end": 1}},
            {"token_index": 1, "span": {"start": 2, "end": 6}},
            {"token_index": 2, "span": {"start": 7, "end": 8}},
            {"token_index": 3, "span": {"start": 9, "end": 13}},
        ],
        "edges": [
            {"head_index": 1, "dependent_index": 0, "label": "nsubj"},
            {"head_index": 3, "dependent_index": 2, "label": "nummod"},
            {"head_index": 1, "dependent_index": 3, "label": "dobj"},
        ],
    }
    assert _cue_and_edge_scores(case, payload) == (4, 4, 3, 3, 3)


def test_metric_math_is_zero_safe() -> None:
    assert _safe_ratio(0, 0) == 0.0
    assert _safe_ratio(3, 4) == 0.75
    assert _f1(0.0, 0.0) == 0.0
    assert _f1(1.0, 1.0) == 1.0


@dataclass(frozen=True)
class _ReplayReceipt:
    reason: str
    checks: tuple[str, ...]


@dataclass(frozen=True)
class _ReplayResult:
    identity: tuple[str, ...]
    bridge_receipt: _ReplayReceipt
    receipt: _ReplayReceipt


def test_complete_replay_signature_detects_bounded_receipt_drift() -> None:
    first = _ReplayResult(("user", "quantity", "maps", "4"), _ReplayReceipt("ok", ("a",)), _ReplayReceipt("ok", ("b",)))
    changed = _ReplayResult(("user", "quantity", "maps", "4"), _ReplayReceipt("drift", ("a",)), _ReplayReceipt("ok", ("b",)))
    assert _semantic_replay_signature(first) != _semantic_replay_signature(changed)


def test_identity_semantics_and_provenance_are_scored_separately() -> None:
    payload, _ = load_fixture(FIXTURE)
    case = next(item for item in payload["cases"] if item["phase_a_expectation"] == "supported")
    api = load_menhir_apis(resolve_menhir_root())
    identity = SimpleNamespace(
        subject="user",
        relation_type=case["relation_type"],
        target_or_scope=(case["target_literal"].lower(), ""),
        value_kind="count",
        value=str(case["value"]["magnitude"]),
        unit="",
        operation="absolute",
        effective_time=None,
        provenance=SimpleNamespace(
            episode_uuid=case["episode_id"],
            span_start=case["claim_span"]["start_char"],
            span_end=case["claim_span"]["end_char"],
            claim_ordinal=case["claim_ordinal"],
            source_key=case["source_key"],
            derivation_kind="research_dependency_rule",
            derivation_version=api.dependency_rule_version,
            rule_id=api.dependency_rule_id,
        ),
    )
    assert _identity_exact(identity, case, api) == (True, True)
    identity.provenance.source_key = "wrong"  # type: ignore[misc]
    assert _identity_exact(identity, case, api) == (True, False)


def test_output_refuses_overwrite_and_creates_no_partial_report() -> None:
    report = measure_cases([], SimpleNamespace(root=Path.cwd()))
    root = Path(__file__).parent / f"dependency-bridge-output-{uuid.uuid4().hex}"
    json_path, markdown_path = root / "nested" / "report.json", root / "nested" / "report.md"
    try:
        write_outputs(report, json_path, markdown_path)
        assert json_path.exists() and markdown_path.exists()
        with pytest.raises(MeasurementError, match="refusing_to_overwrite"):
            write_outputs(report, json_path, markdown_path)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_optional_real_six_case_spacy_smoke() -> None:
    pytest.importorskip("spacy")
    pytest.importorskip("en_core_web_sm")
    from archolith_bench.dependency_evidence_spacy import CandidateLocator, ParsedSpan, emit_dependency_evidence, parse_with_spacy

    payload = json.loads((Path(__file__).parents[1] / "fixtures" / "dependency_evidence_smoke_v1.json").read_text(encoding="utf-8"))
    for case in payload["cases"]:
        syntax = case["syntax"]
        source = case["source"]
        candidate = CandidateLocator(*syntax["candidate_span"], "a" * 64)
        parsed = parse_with_spacy(
            source,
            candidate,
            ParsedSpan(*syntax["numeric_value_span"]),
            model_name="en_core_web_sm",
            config={},
        )
        assert parsed.status == "parsed", parsed.reason
        assert parsed.document is not None
        emitted = emit_dependency_evidence(parsed.document, candidate)
        assert emitted.status == "emitted", emitted.reason
