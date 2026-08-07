"""Offline measurement harness for the 48-case dependency-evidence bridge.

This module measures evidence plumbing and the Menhir-owned Phase-A rule.  Candidate operation,
value, subject, exact claim text, and gold locators are explicit supplied inputs; they are not
recognition predictions.  It never falls back from the bridge to the baseline composer.  The full
fixture is loaded only by the explicit CLI; importing this module does no work.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import platform
import subprocess
import sys
from collections import Counter
from dataclasses import asdict, dataclass, is_dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Mapping, Sequence

from archolith_bench.dependency_evidence_spacy import (
    CandidateLocator,
    PINNED_MODEL_HASH,
    PINNED_MODEL_NAME,
    PINNED_SPACY_VERSION,
    ParsedSpan,
    emit_dependency_evidence,
    parse_with_spacy,
)


FIXTURE_PATH = Path(__file__).parents[1] / "fixtures" / "dependency_evidence_bridge_ops_v1.json"
FIXTURE_SHA256 = "bde118508cf55c94bbd10fc88fbc625a0f465859a545f3ca79deb391a25ba57b"
FIXTURE_SCHEMA_VERSION = "dependency-evidence-bridge-ops-v1"
FIXTURE_VERSION = "1.0.0"
REPORT_SCHEMA_VERSION = 1
MEASUREMENT_VERSION = "dependency-bridge-measurement-v1"
# Pinned from the Bench adapter's canonical empty-config pipeline metadata. A drifted adapter
# fails the Menhir provenance check rather than copying a pipeline hash out of evidence.
PINNED_PIPELINE_HASH = "8aa8bd0fcc490c03b1cfd08c7c649c8157b9238e417adc6136a29bf7738719f6"


class MeasurementError(ValueError):
    """Raised when the frozen measurement contract cannot be proven."""


@dataclass(frozen=True, slots=True)
class MenhirApis:
    root: Path
    adapt_research_candidate: Callable[..., Any]
    SourceBoundSpan: type
    TokenEvidence: type
    DependencyEdge: type
    ScalarCueEvidence: type
    MarkerEvidence: type
    ScalarDependencyEvidence: type
    compose_dependency_scalar_identity: Callable[..., Any]
    dependency_rule_id: str
    dependency_rule_version: str


@dataclass(frozen=True, slots=True)
class CaseMeasurement:
    case_id: str
    split: str
    topology: str
    role_gold: str
    role_variant: str | None
    operation_gold: str | None
    phase_a_expectation: str
    candidate_operation_source: str
    candidate_value_source: str
    proposal_operation: str | None
    proposal_value: str | None
    span_recognition: str
    role_prediction: str
    operation_prediction: str
    adapter_status: str
    adapter_reason: str | None
    baseline_status: str
    baseline_reason: str | None
    parser_status: str
    parser_reason: str | None
    proposal_provenance_exact: bool
    cue_exact_count: int
    cue_denominator: int
    edge_true_positive: int
    edge_predicted: int
    edge_gold: int
    emission_status: str
    emission_reason: str | None
    provenance_integrity: bool
    bridge_provenance_validated: bool
    bridge_status: str
    bridge_reason: str | None
    bridge_composed: bool
    identity_exact: bool
    identity_provenance_exact: bool
    deterministic_replay: str


@dataclass(frozen=True, slots=True)
class MeasurementReport:
    report_schema_version: int
    measurement_version: str
    fixture_sha256: str
    fixture_version: str
    case_count: int
    parser_id: str
    parser_version: str
    model_hash: str
    pipeline_hash: str
    environment: dict[str, Any]
    supplied_inputs: tuple[str, ...]
    aggregates: dict[str, Any]
    cases: tuple[CaseMeasurement, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "report_schema_version": self.report_schema_version,
            "measurement_version": self.measurement_version,
            "fixture_sha256": self.fixture_sha256,
            "fixture_version": self.fixture_version,
            "case_count": self.case_count,
            "provenance": {
                "parser_id": self.parser_id,
                "parser_version": self.parser_version,
                "model_hash": self.model_hash,
                "pipeline_hash": self.pipeline_hash,
                "environment": self.environment,
            },
            "supplied_inputs": list(self.supplied_inputs),
            "aggregates": self.aggregates,
            "cases": [asdict(case) for case in self.cases],
        }


def resolve_menhir_root(value: str | Path | None = None) -> Path:
    """Resolve an explicit MENHIR_ROOT or one unambiguous local sibling."""

    candidates: list[Path]
    if value is not None:
        candidates = [Path(value).expanduser().resolve()]
    elif os.environ.get("MENHIR_ROOT"):
        candidates = [Path(os.environ["MENHIR_ROOT"]).expanduser().resolve()]
    else:
        candidates = [
            Path.cwd() / "menhir",
            Path.cwd().parent / "menhir",
            Path(__file__).resolve().parents[2] / "menhir",
        ]
    valid = sorted({candidate.resolve() for candidate in candidates if (candidate / "src" / "menhir").is_dir()})
    if len(valid) != 1:
        raise MeasurementError("MENHIR_ROOT must resolve to exactly one root containing src/menhir")
    return valid[0]


def load_menhir_apis(root: str | Path | None = None) -> MenhirApis:
    menhir_root = resolve_menhir_root(root)
    source_root = str(menhir_root / "src")
    if source_root not in sys.path:
        sys.path.insert(0, source_root)
    names = (
        "menhir.services.research_scalar_adapter",
        "menhir.domain.scalar_dependency_evidence",
        "menhir.services.research_scalar_dependency_rules",
    )
    try:
        adapter = importlib.import_module(names[0])
        evidence = importlib.import_module(names[1])
        rules = importlib.import_module(names[2])
    except (ImportError, AttributeError) as exc:
        raise MeasurementError(f"Menhir APIs unavailable from {menhir_root}: {exc}") from exc
    for module in (adapter, evidence, rules):
        module_path = getattr(module, "__file__", None)
        if module_path is None or not Path(module_path).resolve().is_relative_to(Path(source_root).resolve()):
            raise MeasurementError("Menhir import identity mismatch")
    return MenhirApis(
        root=menhir_root,
        adapt_research_candidate=adapter.adapt_research_candidate,
        SourceBoundSpan=evidence.SourceBoundSpan,
        TokenEvidence=evidence.TokenEvidence,
        DependencyEdge=evidence.DependencyEdge,
        ScalarCueEvidence=evidence.ScalarCueEvidence,
        MarkerEvidence=evidence.MarkerEvidence,
        ScalarDependencyEvidence=evidence.ScalarDependencyEvidence,
        compose_dependency_scalar_identity=rules.compose_dependency_scalar_identity,
        dependency_rule_id=rules.DEPENDENCY_RULE_ID,
        dependency_rule_version=rules.DEPENDENCY_RULE_VERSION,
    )


def load_fixture(path: str | Path = FIXTURE_PATH) -> tuple[dict[str, Any], str]:
    fixture_path = Path(path)
    try:
        payload = json.loads(fixture_path.read_text(encoding="utf-8"))
        canonical = json.dumps(payload["cases"], sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        actual_sha = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    except (OSError, KeyError, TypeError, ValueError) as exc:
        raise MeasurementError(f"fixture_invalid: {exc}") from exc
    denominators = payload.get("metadata", {}).get("denominators", {})
    expected_denominators = {
        "cases": 48,
        "claim_spans": 48,
        "dependency_paths": 48,
        "gold_edge_count": 144,
        "role_labels": 48,
        "operation_labels": 48,
        "relation_payloads": 48,
        "target_scope_payloads": 48,
        "value_payloads": 48,
    }
    expected_phase = {
        "phase_a_supported": 6,
        "phase_a_unsupported": 14,
        "phase_a_true_negatives": 28,
    }
    if (
        payload.get("schema_version") != FIXTURE_SCHEMA_VERSION
        or payload.get("fixture_version") != FIXTURE_VERSION
        or actual_sha != FIXTURE_SHA256
        or payload.get("metadata", {}).get("fixture_sha256") != FIXTURE_SHA256
        or len(payload.get("cases", [])) != 48
        or denominators != expected_denominators
        or any(payload.get("metadata", {}).get(key) != value for key, value in expected_phase.items())
    ):
        raise MeasurementError("fixture_sha_or_version_mismatch")
    return payload, actual_sha


def _raw_candidate(case: Mapping[str, Any]) -> dict[str, Any]:
    value_info = case["value"]
    operation = case.get("operation_gold") or "absolute"
    magnitude = int(value_info["magnitude"])
    value = magnitude * int(value_info["sign"]) if operation == "delta" else magnitude
    return {
        "candidate_id": case["case_id"],
        "episode": 0,
        "subject": case["gold_dependency_path"]["node_literals"]["subject"],
        "attribute": "bridge_measurement",
        "scope": case.get("role_scope", "") or "",
        "value_kind": "count",
        "unit": "",
        "operation": operation,
        "value": value,
        "stated_span": case["claim_span"]["text"],
        "when": None,
        "display": "",
        "claim_ordinal": 0,
    }


def _span(api: MenhirApis, payload: Mapping[str, Any] | None) -> Any:
    if payload is None:
        return None
    return api.SourceBoundSpan(
        payload["start"],
        payload["end"],
        payload["surface_sha256"],
        payload.get("token_start"),
        payload.get("token_end"),
    )


def _menhir_evidence(api: MenhirApis, payload: Mapping[str, Any]) -> Any:
    tokens = tuple(
        api.TokenEvidence(
            token["token_index"],
            _span(api, token["span"]),
            token["head_index"],
            token["dependency_label"],
            token["pos_tag"],
            token["lemma_sha256"],
        )
        for token in payload["tokens"]
    )
    edges = tuple(api.DependencyEdge(edge["head_index"], edge["dependent_index"], edge["label"]) for edge in payload["edges"])
    cue_payload = payload["cues"]
    cues = api.ScalarCueEvidence(
        subject=_span(api, cue_payload.get("subject")),
        predicate=_span(api, cue_payload.get("predicate")),
        numeric_value=_span(api, cue_payload["numeric_value"]),
        unit=_span(api, cue_payload.get("unit")),
        target=_span(api, cue_payload.get("target")),
        modifiers=tuple(_span(api, item) for item in cue_payload.get("modifiers", [])),
        scope=_span(api, cue_payload.get("scope")),
        clause_root_token=cue_payload["clause_root_token"],
    )
    markers = tuple(
        api.MarkerEvidence(item["category"], _span(api, item["span"]), tuple(item.get("token_indices", [])))
        for item in payload.get("markers", [])
    )
    return api.ScalarDependencyEvidence(
        schema_version=payload["schema_version"],
        evidence_version=payload["evidence_version"],
        parser_id=payload["parser_id"],
        parser_version=payload["parser_version"],
        model_hash=payload["model_hash"],
        pipeline_hash=payload["pipeline_hash"],
        source_hash=payload["source_hash"],
        source_length=payload["source_length"],
        candidate_hash=payload["candidate_hash"],
        clause_span=_span(api, payload["clause_span"]),
        tokens=tokens,
        edges=edges,
        cues=cues,
        markers=markers,
        evidence_sha256=payload.get("evidence_sha256", ""),
    )


def _cue_and_edge_scores(case: Mapping[str, Any], payload: Mapping[str, Any]) -> tuple[int, int, int, int, int]:
    gold = case["gold_dependency_path"]
    nodes = gold["node_char_offsets"]
    cue_payload = payload["cues"]
    observed = {
        "subject": cue_payload.get("subject"),
        "predicate": cue_payload.get("predicate"),
        "numeric": cue_payload.get("numeric_value"),
        "target": cue_payload.get("target"),
    }
    exact = 0
    for key, item in observed.items():
        if item is not None and item["start"] == nodes[key] and item["end"] == nodes[key] + len(gold["node_literals"][key]):
            exact += 1
    token_starts = {item["token_index"]: item["span"]["start"] for item in payload["tokens"]}
    actual_edges = {
        (token_starts.get(edge["head_index"]), token_starts.get(edge["dependent_index"]), edge["label"])
        for edge in payload["edges"]
    }
    gold_edges = {(item["head_char"], item["dependent_char"], item["dependency_label"]) for item in gold["edges"]}
    return exact, 4, len(actual_edges & gold_edges), len(actual_edges), len(gold_edges)


def _semantic_replay_signature(result: Any) -> Any:
    """Return complete bounded semantic/receipt output; timing fields are intentionally absent."""

    def freeze(value: Any) -> Any:
        if is_dataclass(value):
            return freeze(asdict(value))
        if isinstance(value, Mapping):
            return tuple((str(key), freeze(item)) for key, item in sorted(value.items(), key=lambda pair: str(pair[0])))
        if isinstance(value, (tuple, list)):
            return tuple(freeze(item) for item in value)
        return value

    return freeze(result)


def _identity_exact(identity: Any, case: Mapping[str, Any], api: MenhirApis) -> tuple[bool, bool]:
    if identity is None or case.get("phase_a_expectation") != "supported":
        return False, False
    semantics = (
        identity.subject == "user"
        and identity.relation_type == case["relation_type"]
        and identity.target_or_scope == (case["target_literal"].lower(), case.get("role_scope", "") or "")
        and identity.value_kind == "count"
        and identity.value == str(case["value"]["magnitude"])
        and identity.unit == ""
        and identity.operation == "absolute"
        and identity.effective_time is None
    )
    provenance = identity.provenance
    provenance_exact = (
        provenance.episode_uuid == case["episode_id"]
        and provenance.span_start == case["claim_span"]["start_char"]
        and provenance.span_end == case["claim_span"]["end_char"]
        and provenance.claim_ordinal == case["claim_ordinal"]
        and provenance.source_key == case["source_key"]
        and provenance.derivation_kind == "research_dependency_rule"
        and provenance.derivation_version == api.dependency_rule_version
        and provenance.rule_id == api.dependency_rule_id
    )
    return semantics, provenance_exact


def _git_identity(root: Path) -> dict[str, Any]:
    try:
        resolved = root.resolve()
        git_prefix = ["git", "-c", f"safe.directory={resolved}", "-C", str(resolved)]
        head = subprocess.run(
            [*git_prefix, "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        dirty = bool(subprocess.run(
            [*git_prefix, "status", "--porcelain"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip())
        return {"head": head, "dirty": dirty}
    except (OSError, subprocess.SubprocessError):
        return {"head": "unknown", "dirty": "unknown"}


def _artifact_anchors(bench_root: Path, menhir_root: Path) -> list[dict[str, str]]:
    paths = [
        (bench_root, Path("archolith_bench/dependency_scalar_bridge_measurement.py")),
        (bench_root, Path("archolith_bench/dependency_evidence_spacy.py")),
        (menhir_root, Path("src/menhir/services/research_scalar_adapter.py")),
        (menhir_root, Path("src/menhir/domain/scalar_dependency_evidence.py")),
        (menhir_root, Path("src/menhir/services/research_scalar_dependency_bridge.py")),
        (menhir_root, Path("src/menhir/services/research_scalar_dependency_rules.py")),
        (menhir_root, Path("src/menhir/services/compositional_scalar_identity.py")),
        (menhir_root, Path("src/menhir/services/structural_scalar_composer.py")),
        (menhir_root, Path("src/menhir/services/typed_scalar_rules.py")),
    ]
    anchors: list[dict[str, str]] = []
    for root, relative in paths:
        path = (root / relative).resolve()
        normalized = relative.as_posix()
        try:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
        except (OSError, ValueError) as exc:
            anchors.append({"path": normalized, "sha256": "unknown", "error": type(exc).__name__})
        else:
            anchors.append({"path": normalized, "sha256": digest})
    return anchors


def _environment_identity(menhir_root: Path) -> dict[str, Any]:
    bench_root = Path(__file__).resolve().parents[1]
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "bench_git": _git_identity(bench_root),
        "menhir_git": _git_identity(menhir_root),
        "menhir_root": str(menhir_root),
        "artifact_anchors": _artifact_anchors(bench_root, menhir_root),
    }


def _safe_ratio(numerator: int | float, denominator: int | float) -> float:
    return numerator / denominator if denominator else 0.0


def _f1(precision: float, recall: float) -> float:
    return _safe_ratio(2 * precision * recall, precision + recall)


def measure_cases(cases: Sequence[Mapping[str, Any]], api: MenhirApis) -> MeasurementReport:
    records: list[CaseMeasurement] = []
    for case in cases:
        source = case["text"]
        episode = SimpleNamespace(uuid=case["episode_id"], content=source)
        raw = _raw_candidate(case)
        adapted = api.adapt_research_candidate(raw, [episode], candidate_id=case["case_id"], canonical_self=True)
        proposal = adapted.proposal
        baseline_status = "not_run"
        baseline_reason = None
        if adapted.composition is not None:
            baseline_status = "composed" if adapted.composition.composed else "abstained"
            baseline_reason = adapted.composition.receipt.reason_code
        parser_status = "not_run_no_proposal"
        parser_reason = None
        proposal_provenance_exact = False
        proposal_operation = proposal.operation if proposal is not None else None
        proposal_value = proposal.normalized_value if proposal is not None else None
        cue_exact = edge_tp = edge_pred = edge_gold = 0
        emission_status = "not_run"
        emission_reason = None
        provenance = False
        bridge_provenance_validated = False
        bridge_status = "not_run_no_proposal"
        bridge_reason = None
        bridge_composed = False
        identity_exact = False
        identity_provenance_exact = False
        deterministic_replay = "not_run_no_proposal"
        cue_denominator = 4
        edge_gold = len(case["gold_dependency_path"]["edges"])
        if proposal is not None:
            proposal_provenance_exact = (
                proposal.episode_uuid == case["episode_id"]
                and proposal.span_start == case["claim_span"]["start_char"]
                and proposal.span_end == case["claim_span"]["end_char"]
                and proposal.claim_ordinal == case["claim_ordinal"]
                and proposal.source_key == case["source_key"]
            )
            if not proposal_provenance_exact:
                parser_status = "not_run_proposal_provenance_mismatch"
                parser_reason = "proposal_provenance_mismatch"
                bridge_status = "not_run_proposal_provenance_mismatch"
            else:
                candidate = CandidateLocator(case["claim_span"]["start_char"], case["claim_span"]["end_char"], adapted.receipt.candidate_hash)
                quantity = case["quantity_span"]
                parsed = parse_with_spacy(
                    source,
                    candidate,
                    ParsedSpan(quantity["start_char"], quantity["end_char"]),
                    model_name=PINNED_MODEL_NAME,
                    config={},
                )
                parser_status = parsed.status
                parser_reason = parsed.reason
                if parsed.status == "parsed" and parsed.document is not None:
                    emitted = emit_dependency_evidence(parsed.document, candidate)
                    emission_status = emitted.status
                    emission_reason = emitted.reason
                    if emitted.evidence is not None:
                        cue_exact, cue_denominator, edge_tp, edge_pred, edge_gold = _cue_and_edge_scores(case, emitted.evidence)
                        provenance = (
                            emitted.evidence.get("candidate_hash") == adapted.receipt.candidate_hash
                            and emitted.evidence.get("source_hash") == case["source_sha256"]
                            and emitted.evidence.get("clause_span", {}).get("start") == case["claim_span"]["start_char"]
                            and emitted.evidence.get("clause_span", {}).get("end") == case["claim_span"]["end_char"]
                            and emitted.evidence.get("parser_id") == "spacy"
                            and emitted.evidence.get("parser_version") == PINNED_SPACY_VERSION
                            and emitted.evidence.get("model_hash") == PINNED_MODEL_HASH
                            and emitted.evidence.get("pipeline_hash") == PINNED_PIPELINE_HASH
                        )
                    if emitted.status == "emitted" and emitted.evidence is not None:
                        try:
                            evidence = _menhir_evidence(api, emitted.evidence)
                            provenance = provenance and bool(emitted.evidence.get("evidence_sha256"))
                            compose_kwargs = {
                                "expected_candidate_hash": adapted.receipt.candidate_hash,
                                "expected_parser_id": "spacy",
                                "expected_parser_version": PINNED_SPACY_VERSION,
                                "expected_model_hash": PINNED_MODEL_HASH,
                                "expected_pipeline_hash": PINNED_PIPELINE_HASH,
                                "expected_episode_uuid": proposal.episode_uuid,
                                "expected_source_key": proposal.source_key,
                            }
                            bridge = api.compose_dependency_scalar_identity(evidence, source, proposal, **compose_kwargs)
                            bridge_composed = bridge.composed
                            bridge_status = "composed" if bridge.composed else "abstained"
                            bridge_reason = bridge.receipt.reason
                            bridge_provenance_validated = (
                                getattr(getattr(bridge, "bridge_receipt", None), "outcome", None) == "validated"
                            )
                            identity_exact, identity_provenance_exact = _identity_exact(bridge.identity, case, api)
                            replay = api.compose_dependency_scalar_identity(evidence, source, proposal, **compose_kwargs)
                            deterministic_replay = (
                                "stable" if _semantic_replay_signature(bridge) == _semantic_replay_signature(replay)
                                else "mismatch"
                            )
                        except (AttributeError, IndexError, KeyError, TypeError, ValueError) as exc:
                            bridge_status = "error"
                            bridge_reason = type(exc).__name__
                            deterministic_replay = "error"
                else:
                    bridge_status = "not_run_parser_unavailable"
                    deterministic_replay = "not_run_parser_unavailable"
        records.append(
            CaseMeasurement(
                case_id=case["case_id"],
                split=case["split"],
                topology=case["topology"],
                role_gold=case["role_gold"],
                role_variant=case.get("role_variant"),
                operation_gold=case.get("operation_gold"),
                phase_a_expectation=case["phase_a_expectation"],
                candidate_operation_source=("gold_operation_supplied" if case.get("operation_gold") is not None else "null_default_absolute"),
                candidate_value_source=("gold_signed_delta_supplied" if case.get("operation_gold") == "delta" else "gold_magnitude_supplied"),
                proposal_operation=proposal_operation,
                proposal_value=proposal_value,
                span_recognition="not_measured_gold_locator_supplied",
                role_prediction="not_measured",
                operation_prediction="not_measured",
                adapter_status=adapted.receipt.parse_status,
                adapter_reason=adapted.receipt.parse_reason,
                baseline_status=baseline_status,
                baseline_reason=baseline_reason,
                parser_status=parser_status,
                parser_reason=parser_reason,
                proposal_provenance_exact=proposal_provenance_exact,
                cue_exact_count=cue_exact,
                cue_denominator=cue_denominator,
                edge_true_positive=edge_tp,
                edge_predicted=edge_pred,
                edge_gold=edge_gold,
                emission_status=emission_status,
                emission_reason=emission_reason,
                provenance_integrity=provenance,
                bridge_provenance_validated=bridge_provenance_validated,
                bridge_status=bridge_status,
                bridge_reason=bridge_reason,
                bridge_composed=bridge_composed,
                identity_exact=identity_exact,
                identity_provenance_exact=identity_provenance_exact,
                deterministic_replay=deterministic_replay,
            )
        )
    supported = [record for record in records if record.phase_a_expectation == "supported"]
    unsupported = [record for record in records if record.phase_a_expectation == "unsupported_abstain"]
    negatives = [record for record in records if record.phase_a_expectation == "negative"]

    cue_exact = sum(record.cue_exact_count for record in records)
    cue_gold = sum(record.cue_denominator for record in records)
    edge_tp = sum(record.edge_true_positive for record in records)
    edge_pred = sum(record.edge_predicted for record in records)
    edge_gold = sum(record.edge_gold for record in records)
    edge_precision = _safe_ratio(edge_tp, edge_pred)
    edge_recall = _safe_ratio(edge_tp, edge_gold)
    edge_f1 = _f1(edge_precision, edge_recall)
    emitted = sum(record.emission_status == "emitted" for record in records)
    emission_denominator = sum(record.proposal_provenance_exact for record in records)
    supported_composed = sum(record.bridge_composed for record in supported)
    unsupported_composed = sum(record.bridge_composed for record in unsupported)
    false_current = sum(record.bridge_composed for record in negatives)
    negative_true = len(negatives) - false_current

    def slice_outcome(field: str) -> dict[str, Any]:
        keys = sorted({str(getattr(record, field)) for record in records})
        return {
            key: {
                "cases": sum(str(getattr(record, field)) == key for record in records),
                "supported_composed": sum(str(getattr(record, field)) == key and record.phase_a_expectation == "supported" and record.bridge_composed for record in records),
                "supported_identity_exact": sum(str(getattr(record, field)) == key and record.phase_a_expectation == "supported" and record.identity_exact for record in records),
                "false_current": sum(str(getattr(record, field)) == key and record.phase_a_expectation == "negative" and record.bridge_composed for record in records),
                "unsupported_composed": sum(str(getattr(record, field)) == key and record.phase_a_expectation == "unsupported_abstain" and record.bridge_composed for record in records),
            }
            for key in keys
        }

    aggregates = {
        "denominators": {
            "cases": len(records),
            "supported": len(supported),
            "unsupported": len(unsupported),
            "negative": len(negatives),
            "gold_cues": sum(record.cue_denominator for record in records),
            "gold_edges": sum(record.edge_gold for record in records),
            "proposal_provenance": sum(record.proposal_provenance_exact for record in records),
        },
        "cue_accuracy": {"exact": cue_exact, "gold": cue_gold, "accuracy": _safe_ratio(cue_exact, cue_gold)},
        "edge_micro": {
            "true_positive": edge_tp,
            "predicted": edge_pred,
            "gold": edge_gold,
            "precision": edge_precision,
            "recall": edge_recall,
            "f1": edge_f1,
        },
        "emission": {"emitted": emitted, "denominator": emission_denominator, "rate": _safe_ratio(emitted, emission_denominator)},
        "provenance": {
            "integrity": sum(record.provenance_integrity for record in records),
            "denominator": emitted,
            "rate": _safe_ratio(sum(record.provenance_integrity for record in records), emitted),
        },
        "bridge_provenance": {
            "validated": sum(record.bridge_provenance_validated for record in records),
            "denominator": emitted,
            "rate": _safe_ratio(sum(record.bridge_provenance_validated for record in records), emitted),
        },
        "parser_status_counts": dict(Counter(record.parser_status for record in records)),
        "baseline_status_counts": dict(Counter(record.baseline_status for record in records)),
        "bridge_reason_counts": dict(Counter(record.bridge_reason for record in records if record.bridge_reason)),
        "deterministic_replay_counts": dict(Counter(record.deterministic_replay for record in records)),
        "phase_a": {
            "supported_tp": supported_composed,
            "supported_denominator": len(supported),
            "supported_recall": _safe_ratio(supported_composed, len(supported)),
            "supported_precision": _safe_ratio(supported_composed, supported_composed + unsupported_composed + false_current),
            "unsupported_composed": unsupported_composed,
            "unsupported_denominator": len(unsupported),
            "negative_fp_false_current": false_current,
            "negative_denominator": len(negatives),
            "negative_tn": negative_true,
            "negative_specificity": _safe_ratio(negative_true, len(negatives)),
            "supported_identity_exact": sum(record.identity_exact for record in supported),
            "identity_provenance_exact": sum(record.identity_provenance_exact for record in supported),
        },
        "slices": {"split": slice_outcome("split"), "topology": slice_outcome("topology"), "role_gold": slice_outcome("role_gold")},
        "gates": {
            "role_classification": "not_measured",
            "operation_classification": "not_measured",
            "span_recognition": "not_measured",
            "performance": "not_measured",
            "cache": "not_measured",
            "parser_version_comparison": "not_measured",
            "determinism_replay": "composer_only",
            "full_adapter_parser_emission_replay": "not_measured",
            "promotion_status": "not_evaluable",
        },
        "supplied_inputs": [
            "subject_text_from_gold_dependency_node",
            "operation_gold_or_null_default_absolute",
            "value_magnitude_and_sign_from_gold",
            "exact_stated_span_from_gold",
            "gold_claim_and_numeric_locators",
        ],
    }
    return MeasurementReport(
        REPORT_SCHEMA_VERSION,
        MEASUREMENT_VERSION,
        FIXTURE_SHA256,
        FIXTURE_VERSION,
        len(records),
        "spacy",
        PINNED_SPACY_VERSION,
        PINNED_MODEL_HASH,
        PINNED_PIPELINE_HASH,
        _environment_identity(api.root),
        (
            "subject_text_from_gold_dependency_node",
            "operation_gold_or_null_default_absolute",
            "value_magnitude_and_sign_from_gold",
            "exact_stated_span_from_gold",
            "gold_claim_and_numeric_locators",
        ),
        aggregates,
        tuple(records),
    )


def render_markdown(report: MeasurementReport) -> str:
    aggregates = report.aggregates
    denominators = aggregates["denominators"]
    phase_a = aggregates["phase_a"]
    edge = aggregates["edge_micro"]
    gates = aggregates["gates"]
    lines = [
        "# Dependency scalar bridge measurement",
        "",
        "Offline, source-free measurement; no LLM, network, runtime, Neo4j, cache, or fallback lane.",
        "",
        f"- Fixture SHA: `{report.fixture_sha256}` (version `{report.fixture_version}`)",
        f"- Cases: {report.case_count}; parser pins: `spacy` `{report.parser_version}`, model `{report.model_hash}`, pipeline `{report.pipeline_hash}`",
        f"- Supplied inputs (not predictions): {', '.join(report.supplied_inputs)}",
        "- Gold claim/numeric locators are supplied; span recognition is `not_measured_gold_locator_supplied`.",
        "- Candidate operation/value and subject/span fields are supplied inputs; role and operation recognition remain `not_measured`.",
        "",
        "## Measured outcomes",
        "",
        f"- Cue exact accuracy: {aggregates['cue_accuracy']['exact']}/{aggregates['cue_accuracy']['gold']} ({aggregates['cue_accuracy']['accuracy']:.3f})",
        f"- Edge micro: TP {edge['true_positive']} / predicted {edge['predicted']} / gold {edge['gold']}; precision {edge['precision']:.3f}, recall {edge['recall']:.3f}, F1 {edge['f1']:.3f}",
        f"- Emission: {aggregates['emission']['emitted']}/{aggregates['emission']['denominator']}; evidence provenance integrity {aggregates['provenance']['integrity']}/{aggregates['provenance']['denominator']}; Menhir bridge provenance validated {aggregates['bridge_provenance']['validated']}/{aggregates['bridge_provenance']['denominator']}",
        f"- Phase A supported recall {phase_a['supported_tp']}/{phase_a['supported_denominator']} ({phase_a['supported_recall']:.3f}), precision {phase_a['supported_precision']:.3f}; unsupported composed {phase_a['unsupported_composed']}/{phase_a['unsupported_denominator']}; negative false-current {phase_a['negative_fp_false_current']}/{phase_a['negative_denominator']}; specificity {phase_a['negative_specificity']:.3f}",
        f"- Proposal provenance exact: {denominators['proposal_provenance']}/{denominators['cases']}",
        "",
        "## Safety gates",
        "",
    ]
    lines.extend(f"- `{key}`: `{value}`" for key, value in gates.items())
    lines.append("")
    return "\n".join(lines)


def write_outputs(report: MeasurementReport, json_out: Path, markdown_out: Path) -> None:
    json_path = Path(json_out).expanduser()
    markdown_path = Path(markdown_out).expanduser()
    if json_path.resolve() == markdown_path.resolve():
        raise MeasurementError("json_and_markdown_outputs_must_differ")
    existing = [str(path) for path in (json_path, markdown_path) if path.exists()]
    if existing:
        raise MeasurementError(f"refusing_to_overwrite: {', '.join(existing)}")
    try:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(report.as_dict(), sort_keys=True, indent=2) + "\n", encoding="utf-8")
        markdown_path.write_text(render_markdown(report), encoding="utf-8")
    except OSError as exc:
        raise MeasurementError(f"output_write_failed: {exc}") from exc


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Measure the offline 48-case dependency bridge")
    parser.add_argument("--fixture", type=Path, default=FIXTURE_PATH)
    parser.add_argument("--menhir-root", type=Path, default=None)
    parser.add_argument("--json-out", type=Path, required=True)
    parser.add_argument("--markdown-out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        fixture, _ = load_fixture(args.fixture)
        api = load_menhir_apis(args.menhir_root)
        report = measure_cases(fixture["cases"], api)
        write_outputs(report, args.json_out, args.markdown_out)
    except MeasurementError as exc:
        parser.error(str(exc))
    return 0


__all__ = [
    "FIXTURE_PATH",
    "FIXTURE_SHA256",
    "MenhirApis",
    "MeasurementError",
    "MeasurementReport",
    "PINNED_PIPELINE_HASH",
    "CaseMeasurement",
    "load_fixture",
    "load_menhir_apis",
    "measure_cases",
    "resolve_menhir_root",
]
