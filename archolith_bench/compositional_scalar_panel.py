"""Offline, source-labeled evaluation of Menhir's deterministic scalar composition.

The panel is independent of LLM captures.  Bench owns strict artifact validation and score
accounting; Menhir owns extraction, grounding, value normalization, and structural composition.
No network, model, database, Docker, or service call is made here.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import math
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

from archolith_bench.deterministic_scalar_shadow import (
    _git_metadata,
    _validate_menhir_import_identity,
    resolve_menhir_root,
)


PANEL_SCHEMA_VERSION = 1
REPORT_SCHEMA_VERSION = 1
PROMOTION_STATUS = "not_evaluable"
MIN_POSITIVE_HOLDOUT = 12
MIN_NEGATIVE_HOLDOUT = 12
MIN_RELATION_GROUPS = 4
MIN_PERTURBATIONS_PER_GROUP = 3
_TOP_LEVEL_FIELDS = frozenset({
    "schema_version",
    "panel_id",
    "non_lme",
    "split_policy",
    "source_sha256",
    "episodes",
    "cases",
})
_EPISODE_FIELDS = frozenset({"namespace", "uuid", "content"})
_CASE_FIELDS = frozenset({
    "case_id",
    "namespace",
    "episode_uuid",
    "span_start",
    "span_end",
    "span_sha256",
    "kind",
    "group_id",
    "perturbation_id",
    "split",
    "relation_group",
    "expected",
})
_POSITIVE_EXPECTED_FIELDS = frozenset({
    "subject",
    "relation_type",
    "target",
    "scope",
    "value_kind",
    "value",
    "unit",
    "operation",
    "effective_time",
})
_NEGATIVE_EXPECTED_FIELDS = frozenset({"status", "allowed_reason_codes", "risk_family"})
_KINDS = frozenset({"positive", "negative"})
_SPLITS = frozenset({"train", "holdout"})
_RISK_FAMILIES = frozenset({
    "ambiguous",
    "hedge",
    "hypothetical",
    "list",
    "modal",
    "one_off",
    "past_only",
    "question",
    "temporal",
    "unknown_relation",
    "unsupported_operation",
})
_FALSE_CURRENT_RISKS = frozenset({
    "hedge",
    "hypothetical",
    "modal",
    "one_off",
    "past_only",
    "temporal",
})
_ID_RE = re.compile(r"[a-z0-9][a-z0-9._-]*")
_SHA256_RE = re.compile(r"[0-9a-f]{64}")
_MISMATCH_FIELDS = (
    "subject",
    "relation_type",
    "target",
    "scope",
    "value_kind",
    "value",
    "unit",
    "operation",
    "effective_time",
)


class PanelError(ValueError):
    """Raised when a panel or Menhir result cannot be evaluated safely."""


@dataclass(frozen=True)
class PanelEpisode:
    namespace: str
    uuid: str
    content: str


@dataclass(frozen=True)
class ExpectedIdentity:
    subject: str
    relation_type: str
    target: str
    scope: str
    value_kind: str
    value: str
    unit: str
    operation: str
    effective_time: str | None

    def as_mapping(self) -> dict[str, str | None]:
        return {
            "subject": self.subject,
            "relation_type": self.relation_type,
            "target": self.target,
            "scope": self.scope,
            "value_kind": self.value_kind,
            "value": self.value,
            "unit": self.unit,
            "operation": self.operation,
            "effective_time": self.effective_time,
        }


@dataclass(frozen=True)
class NegativeExpectation:
    allowed_reason_codes: tuple[str, ...]
    risk_family: str


@dataclass(frozen=True)
class PanelCase:
    case_id: str
    namespace: str
    episode_uuid: str
    span_start: int
    span_end: int
    span_sha256: str
    kind: str
    group_id: str
    perturbation_id: str
    split: str
    relation_group: str
    expected_identity: ExpectedIdentity | None
    negative_expectation: NegativeExpectation | None


@dataclass(frozen=True)
class SemanticPanel:
    path: Path
    file_sha256: str
    panel_id: str
    source_sha256: str
    episodes: tuple[PanelEpisode, ...]
    cases: tuple[PanelCase, ...]
    population_requirements_met: bool


@dataclass(frozen=True)
class PanelMenhirApi:
    extractor_type: type
    compose: Callable[..., Any]
    ground_span: Callable[[str, str], tuple[int, int] | None]
    validate_value: Callable[[str, str, Any], None]
    normalize_when: Callable[[dict[str, Any]], tuple[bool, str | None]]
    normalize_scalar: Callable[[Any], str]
    normalize_identity_text: Callable[[str | None], str]
    relation_types: frozenset[str]
    value_kinds: frozenset[str]
    operations: frozenset[str]
    structural_reason_codes: frozenset[str]
    composer_version: str


def _error(context: str, message: str) -> PanelError:
    return PanelError(f"{context}: {message}")


def _exact_fields(raw: object, expected: frozenset[str], context: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise _error(context, "must be an object")
    actual = set(raw)
    if actual != expected:
        missing = sorted(expected - actual)
        unknown = sorted(actual - expected)
        raise _error(context, f"field mismatch; missing={missing}, unknown={unknown}")
    return raw


def _identifier(value: object, context: str) -> str:
    if not isinstance(value, str) or _ID_RE.fullmatch(value) is None:
        raise _error(context, "must be a canonical lowercase identifier")
    if value.startswith("lme-") or "longmemeval" in value:
        raise _error(context, "must not contain benchmark-specific identifiers")
    return value


def _canonical_text(
    value: object,
    context: str,
    normalizer: Callable[[str | None], str],
    *,
    allow_blank: bool = False,
) -> str:
    if not isinstance(value, str):
        raise _error(context, "must be a string")
    canonical = normalizer(value)
    if value != canonical or (not allow_blank and not value):
        raise _error(context, "must already be canonical trim/lower text")
    return value


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def source_sha256(episodes: list[dict[str, str]]) -> str:
    """Hash only canonical source episodes, independent of labels and file formatting."""
    canonical = sorted(episodes, key=lambda row: (row["namespace"], row["uuid"]))
    encoded = json.dumps(
        canonical,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return _sha256_bytes(encoded)


def load_panel_menhir_api(menhir_root: str | Path) -> PanelMenhirApi:
    """Load the selected checkout's real deterministic and structural scalar contracts."""
    root = resolve_menhir_root(menhir_root)
    source_root = str(root / "src")
    if source_root not in sys.path:
        sys.path.insert(0, source_root)
    try:
        identity = importlib.import_module("menhir.domain.scalar_identity")
        typed = importlib.import_module("menhir.domain.typed_assertion")
        rules = importlib.import_module("menhir.services.typed_scalar_rules")
        composition = importlib.import_module("menhir.services.compositional_scalar_identity")
        extractor = importlib.import_module("menhir.services.deterministic_scalar_extractor")
        composer = importlib.import_module("menhir.services.structural_scalar_composer")
        modules = (identity, typed, rules, composition, extractor, composer)
        _validate_menhir_import_identity(root, modules)
        return PanelMenhirApi(
            extractor_type=extractor.DeterministicScalarExtractor,
            compose=composer.compose_structural_scalar_identity,
            ground_span=rules._ground_span,
            validate_value=typed.validate_value,
            normalize_when=rules._normalize_when,
            normalize_scalar=typed.normalize_scalar,
            normalize_identity_text=composition._normalized_text,
            relation_types=frozenset(identity.RELATION_TYPES),
            value_kinds=frozenset(typed.VALUE_KINDS),
            operations=frozenset(typed.OPERATIONS),
            structural_reason_codes=frozenset(composer.STRUCTURAL_REASON_CODES),
            composer_version=str(composer.STRUCTURAL_COMPOSER_VERSION),
        )
    except (ImportError, AttributeError) as exc:
        raise PanelError(
            f"could not load the required Menhir scalar APIs from {root}: {exc}"
        ) from exc


def _parse_positive_expected(
    raw: object, api: PanelMenhirApi, context: str
) -> ExpectedIdentity:
    expected = _exact_fields(raw, _POSITIVE_EXPECTED_FIELDS, context)
    subject = _canonical_text(
        expected["subject"], f"{context}.subject", api.normalize_identity_text
    )
    relation = _canonical_text(
        expected["relation_type"], f"{context}.relation_type", api.normalize_identity_text
    )
    if relation not in api.relation_types:
        raise _error(f"{context}.relation_type", f"must be one of {sorted(api.relation_types)}")
    target = _canonical_text(
        expected["target"], f"{context}.target", api.normalize_identity_text, allow_blank=True
    )
    scope = _canonical_text(
        expected["scope"], f"{context}.scope", api.normalize_identity_text, allow_blank=True
    )
    if not target and not scope:
        raise _error(context, "target or scope must be non-blank")
    value_kind = _canonical_text(
        expected["value_kind"], f"{context}.value_kind", api.normalize_identity_text
    )
    operation = _canonical_text(
        expected["operation"], f"{context}.operation", api.normalize_identity_text
    )
    unit = _canonical_text(
        expected["unit"], f"{context}.unit", api.normalize_identity_text, allow_blank=True
    )
    if value_kind not in api.value_kinds:
        raise _error(f"{context}.value_kind", f"must be one of {sorted(api.value_kinds)}")
    if operation not in api.operations:
        raise _error(f"{context}.operation", f"must be one of {sorted(api.operations)}")
    try:
        api.validate_value(value_kind, operation, expected["value"])
    except ValueError as exc:
        raise _error(context, f"value fails Menhir validation: {exc}") from exc
    normalized_value = api.normalize_scalar(expected["value"])
    when_ok, normalized_when = api.normalize_when({"when": expected["effective_time"]})
    if not when_ok or normalized_when != expected["effective_time"]:
        raise _error(context, "effective_time must be null or a canonical normalized ISO timestamp")
    return ExpectedIdentity(
        subject=subject,
        relation_type=relation,
        target=target,
        scope=scope,
        value_kind=value_kind,
        value=normalized_value,
        unit=unit,
        operation=operation,
        effective_time=normalized_when,
    )


def _parse_negative_expected(
    raw: object, api: PanelMenhirApi, context: str
) -> NegativeExpectation:
    expected = _exact_fields(raw, _NEGATIVE_EXPECTED_FIELDS, context)
    if expected["status"] != "abstain":
        raise _error(f"{context}.status", "must be 'abstain'")
    reasons = expected["allowed_reason_codes"]
    if not isinstance(reasons, list) or not reasons:
        raise _error(f"{context}.allowed_reason_codes", "must be a non-empty list")
    if any(not isinstance(reason, str) or reason not in api.structural_reason_codes for reason in reasons):
        raise _error(
            f"{context}.allowed_reason_codes",
            "must contain only known Menhir structural reason codes",
        )
    if len(set(reasons)) != len(reasons):
        raise _error(f"{context}.allowed_reason_codes", "must not contain duplicates")
    risk_family = _identifier(expected["risk_family"], f"{context}.risk_family")
    if risk_family not in _RISK_FAMILIES:
        raise _error(f"{context}.risk_family", f"must be one of {sorted(_RISK_FAMILIES)}")
    return NegativeExpectation(tuple(sorted(reasons)), risk_family)


def _population_requirements(cases: list[PanelCase]) -> dict[str, Any]:
    holdout = [case for case in cases if case.split == "holdout"]
    positives = [case for case in holdout if case.kind == "positive"]
    negatives = [case for case in holdout if case.kind == "negative"]
    relation_groups = {case.relation_group for case in positives}
    perturbations: dict[str, set[str]] = defaultdict(set)
    for case in holdout:
        perturbations[case.group_id].add(case.perturbation_id)
    underfilled = sorted(
        group_id
        for group_id, values in perturbations.items()
        if len(values) < MIN_PERTURBATIONS_PER_GROUP
    )
    met = (
        len(positives) >= MIN_POSITIVE_HOLDOUT
        and len(negatives) >= MIN_NEGATIVE_HOLDOUT
        and len(relation_groups) >= MIN_RELATION_GROUPS
        and not underfilled
    )
    return {
        "met": met,
        "positive_holdout": len(positives),
        "negative_holdout": len(negatives),
        "positive_relation_groups": len(relation_groups),
        "underfilled_group_ids": underfilled,
        "minimums": {
            "positive_holdout": MIN_POSITIVE_HOLDOUT,
            "negative_holdout": MIN_NEGATIVE_HOLDOUT,
            "positive_relation_groups": MIN_RELATION_GROUPS,
            "perturbations_per_group": MIN_PERTURBATIONS_PER_GROUP,
        },
    }


def load_panel(
    path: str | Path,
    *,
    api: PanelMenhirApi,
    enforce_population_requirements: bool = True,
) -> SemanticPanel:
    resolved = Path(path).expanduser().resolve()
    context = f"panel {resolved}"
    if not resolved.is_file():
        raise _error(context, "file does not exist")
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise _error(context, f"could not read canonical JSON: {exc}") from exc
    top = _exact_fields(payload, _TOP_LEVEL_FIELDS, context)
    if top["schema_version"] != PANEL_SCHEMA_VERSION:
        raise _error(context, f"schema_version must be {PANEL_SCHEMA_VERSION}")
    panel_id = _identifier(top["panel_id"], f"{context}.panel_id")
    if top["non_lme"] is not True:
        raise _error(context, "non_lme must be true")
    if top["split_policy"] != "whole_group_holdout":
        raise _error(context, "split_policy must be 'whole_group_holdout'")
    if not isinstance(top["source_sha256"], str) or _SHA256_RE.fullmatch(top["source_sha256"]) is None:
        raise _error(context, "source_sha256 must be a canonical lowercase SHA-256")

    raw_episodes = top["episodes"]
    if not isinstance(raw_episodes, list) or not raw_episodes:
        raise _error(context, "episodes must be a non-empty list")
    episodes: list[PanelEpisode] = []
    source_rows: list[dict[str, str]] = []
    episode_keys: set[tuple[str, str]] = set()
    episode_uuids: set[str] = set()
    for index, raw in enumerate(raw_episodes):
        item_context = f"{context}.episodes[{index}]"
        episode = _exact_fields(raw, _EPISODE_FIELDS, item_context)
        namespace = _identifier(episode["namespace"], f"{item_context}.namespace")
        uuid = _identifier(episode["uuid"], f"{item_context}.uuid")
        content = episode["content"]
        if not isinstance(content, str) or not content:
            raise _error(f"{item_context}.content", "must be a non-empty string")
        key = (namespace, uuid)
        if key in episode_keys:
            raise _error(item_context, "duplicates an episode namespace/uuid")
        if uuid in episode_uuids:
            raise _error(item_context, "episode uuid must be globally unique across namespaces")
        episode_keys.add(key)
        episode_uuids.add(uuid)
        episodes.append(PanelEpisode(namespace, uuid, content))
        source_rows.append({"namespace": namespace, "uuid": uuid, "content": content})
    actual_source_hash = source_sha256(source_rows)
    if top["source_sha256"] != actual_source_hash:
        raise _error(context, f"source_sha256 mismatch; expected {actual_source_hash}")

    raw_cases = top["cases"]
    if not isinstance(raw_cases, list) or not raw_cases:
        raise _error(context, "cases must be a non-empty list")
    by_episode = {(episode.namespace, episode.uuid): episode for episode in episodes}
    cases: list[PanelCase] = []
    case_ids: set[str] = set()
    locators: set[tuple[str, str, int, int]] = set()
    perturbations: set[tuple[str, str]] = set()
    group_splits: dict[str, str] = {}
    for index, raw in enumerate(raw_cases):
        item_context = f"{context}.cases[{index}]"
        case = _exact_fields(raw, _CASE_FIELDS, item_context)
        case_id = _identifier(case["case_id"], f"{item_context}.case_id")
        namespace = _identifier(case["namespace"], f"{item_context}.namespace")
        episode_uuid = _identifier(case["episode_uuid"], f"{item_context}.episode_uuid")
        group_id = _identifier(case["group_id"], f"{item_context}.group_id")
        perturbation_id = _identifier(case["perturbation_id"], f"{item_context}.perturbation_id")
        relation_group = _identifier(case["relation_group"], f"{item_context}.relation_group")
        if relation_group not in api.relation_types and relation_group != "safety":
            raise _error(
                f"{item_context}.relation_group",
                f"must be a Menhir relation type or 'safety', found {relation_group!r}",
            )
        kind = case["kind"]
        split = case["split"]
        if kind not in _KINDS:
            raise _error(f"{item_context}.kind", f"must be one of {sorted(_KINDS)}")
        if split not in _SPLITS:
            raise _error(f"{item_context}.split", f"must be one of {sorted(_SPLITS)}")
        if case_id in case_ids:
            raise _error(item_context, "duplicates case_id")
        case_ids.add(case_id)
        episode = by_episode.get((namespace, episode_uuid))
        if episode is None:
            raise _error(item_context, "references an unknown namespace/episode_uuid")
        start, end = case["span_start"], case["span_end"]
        if (
            not isinstance(start, int)
            or isinstance(start, bool)
            or not isinstance(end, int)
            or isinstance(end, bool)
            or not 0 <= start < end <= len(episode.content)
        ):
            raise _error(item_context, "span_start/span_end must locate a non-empty source substring")
        locator = (namespace, episode_uuid, start, end)
        if locator in locators:
            raise _error(item_context, "duplicates a source locator")
        locators.add(locator)
        stated_span = episode.content[start:end]
        expected_span_hash = _sha256_bytes(stated_span.encode("utf-8"))
        if case["span_sha256"] != expected_span_hash:
            raise _error(item_context, f"span_sha256 mismatch; expected {expected_span_hash}")
        if api.ground_span(episode.content, stated_span) != (start, end):
            raise _error(item_context, "span must have unique Menhir grounding at its offsets")
        perturbation_key = (group_id, perturbation_id)
        if perturbation_key in perturbations:
            raise _error(item_context, "duplicates group_id/perturbation_id")
        perturbations.add(perturbation_key)
        previous_split = group_splits.setdefault(group_id, split)
        if previous_split != split:
            raise _error(item_context, "group_id leaks across train and holdout splits")
        expected_identity = None
        negative_expectation = None
        if kind == "positive":
            expected_identity = _parse_positive_expected(case["expected"], api, f"{item_context}.expected")
            if relation_group != expected_identity.relation_type:
                raise _error(item_context, "relation_group must equal expected relation_type")
        else:
            negative_expectation = _parse_negative_expected(
                case["expected"], api, f"{item_context}.expected"
            )
        cases.append(
            PanelCase(
                case_id=case_id,
                namespace=namespace,
                episode_uuid=episode_uuid,
                span_start=start,
                span_end=end,
                span_sha256=case["span_sha256"],
                kind=kind,
                group_id=group_id,
                perturbation_id=perturbation_id,
                split=split,
                relation_group=relation_group,
                expected_identity=expected_identity,
                negative_expectation=negative_expectation,
            )
        )

    requirements = _population_requirements(cases)
    if enforce_population_requirements and not requirements["met"]:
        raise _error(context, f"generic holdout minimums not met: {requirements}")
    return SemanticPanel(
        path=resolved,
        file_sha256=_sha256_bytes(resolved.read_bytes()),
        panel_id=panel_id,
        source_sha256=actual_source_hash,
        episodes=tuple(episodes),
        cases=tuple(cases),
        population_requirements_met=bool(requirements["met"]),
    )


def _ratio(numerator: int, denominator: int) -> dict[str, Any]:
    if denominator == 0:
        return {"status": "not_measured", "numerator": None, "denominator": None, "ratio": None}
    return {
        "status": "measured",
        "numerator": numerator,
        "denominator": denominator,
        "ratio": numerator / denominator,
    }


def _wilson_lower(successes: int, total: int, z: float = 1.96) -> float | None:
    if total == 0:
        return None
    proportion = successes / total
    z_squared = z * z
    center = proportion + z_squared / (2 * total)
    margin = z * math.sqrt(
        proportion * (1 - proportion) / total + z_squared / (4 * total * total)
    )
    return (center - margin) / (1 + z_squared / total)


def _wilson_record(successes: int, total: int) -> dict[str, Any]:
    lower = _wilson_lower(successes, total)
    if lower is None:
        return {"status": "not_measured", "successes": None, "total": None, "lower": None}
    return {"status": "measured", "successes": successes, "total": total, "lower": lower}


def _identity_mapping(identity: Any) -> dict[str, str | None]:
    target, scope = identity.target_or_scope
    return {
        "subject": identity.subject,
        "relation_type": identity.relation_type,
        "target": target,
        "scope": scope,
        "value_kind": identity.value_kind,
        "value": identity.value,
        "unit": identity.unit,
        "operation": identity.operation,
        "effective_time": identity.effective_time,
    }


def _score_cases(panel: SemanticPanel, api: PanelMenhirApi) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    episode_objects = [SimpleNamespace(uuid=episode.uuid, content=episode.content) for episode in panel.episodes]
    extraction = api.extractor_type().extract(episode_objects)
    proposals: dict[tuple[str, int, int], list[Any]] = defaultdict(list)
    for proposal in extraction.proposals:
        proposals[(proposal.episode_uuid, proposal.span_start, proposal.span_end)].append(proposal)
    sources = {episode.uuid: episode.content for episode in panel.episodes}

    rows: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    mismatch_counts: Counter[str] = Counter()
    unresolved_reasons: Counter[str] = Counter()
    negative_reasons: Counter[str] = Counter()
    risk_counts: Counter[str] = Counter()
    relation_scores: dict[str, Counter[str]] = defaultdict(Counter)
    for case in panel.cases:
        candidates = proposals.get((case.episode_uuid, case.span_start, case.span_end), [])
        row: dict[str, Any] = {
            "case_id": case.case_id,
            "kind": case.kind,
            "split": case.split,
            "relation_group": case.relation_group,
            "span_sha256": case.span_sha256,
            "outcome": None,
            "reason_code": None,
            "mismatch_dimensions": [],
        }
        counts[f"{case.kind}_total"] += 1
        relation = None
        expected_negative = None
        if case.kind == "positive":
            relation = relation_scores[case.relation_group]
            relation["total"] += 1
        else:
            expected_negative = case.negative_expectation
            assert expected_negative is not None
            risk_counts[f"{expected_negative.risk_family}.total"] += 1
        if len(candidates) > 1:
            row["outcome"] = "ambiguous_locator"
            counts[f"{case.kind}_ambiguous_locator"] += 1
            if relation is not None:
                relation["ambiguous"] += 1
            else:
                assert expected_negative is not None
                risk_counts[f"{expected_negative.risk_family}.ambiguous"] += 1
            rows.append(row)
            continue
        if not candidates:
            if case.kind == "negative":
                row["outcome"] = "unjoinable_negative"
                counts["negative_unjoinable"] += 1
                assert expected_negative is not None
                risk_counts[f"{expected_negative.risk_family}.unjoinable"] += 1
            else:
                row["outcome"] = "unjoinable_positive"
                counts["positive_unjoinable"] += 1
                assert relation is not None
                relation["unjoinable"] += 1
            rows.append(row)
            continue

        composition = api.compose(candidates[0], sources[case.episode_uuid], canonical_self=True)
        reason = composition.receipt.reason_code
        row["reason_code"] = reason
        if case.kind == "positive":
            assert relation is not None
            if composition.identity is None:
                row["outcome"] = "unresolved_positive"
                counts["positive_unresolved"] += 1
                relation["unresolved"] += 1
                unresolved_reasons[str(reason or "missing_reason")] += 1
            else:
                counts["positive_admissions"] += 1
                relation["admissions"] += 1
                actual = _identity_mapping(composition.identity)
                expected = case.expected_identity
                assert expected is not None
                mismatches = [
                    field for field in _MISMATCH_FIELDS if actual[field] != expected.as_mapping()[field]
                ]
                row["mismatch_dimensions"] = mismatches
                if mismatches:
                    row["outcome"] = "wrong_semantic_admission"
                    counts["positive_wrong"] += 1
                    relation["wrong"] += 1
                    mismatch_counts.update(mismatches)
                else:
                    row["outcome"] = "correct_semantic_admission"
                    counts["positive_correct"] += 1
                    relation["correct"] += 1
        else:
            assert expected_negative is not None
            if composition.identity is not None:
                row["outcome"] = "false_admission"
                counts["negative_false_admission"] += 1
                risk_counts[f"{expected_negative.risk_family}.false_admission"] += 1
                if expected_negative.risk_family in _FALSE_CURRENT_RISKS:
                    counts["negative_false_current"] += 1
            elif reason in expected_negative.allowed_reason_codes:
                row["outcome"] = "correct_abstention_composer"
                counts["negative_correct_abstention"] += 1
                negative_reasons[str(reason)] += 1
            else:
                row["outcome"] = "safe_abstention_reason_mismatch"
                counts["negative_reason_mismatch"] += 1
                negative_reasons[str(reason or "missing_reason")] += 1
        rows.append(row)

    per_relation: dict[str, Any] = {}
    for relation, relation_count in sorted(relation_scores.items()):
        admissions = relation_count["admissions"]
        correct = relation_count["correct"]
        per_relation[relation] = {
            "positive_total": relation_count["total"],
            "positive_exact_joined": admissions + relation_count["unresolved"],
            "positive_admissions": admissions,
            "positive_correct": correct,
            "positive_wrong": relation_count["wrong"],
            "positive_unresolved": relation_count["unresolved"],
            "positive_unjoinable": relation_count["unjoinable"],
            "positive_ambiguous_locator": relation_count["ambiguous"],
            "exact_join_rate": _ratio(
                admissions + relation_count["unresolved"], relation_count["total"]
            ),
            "coverage": _ratio(correct, relation_count["total"]),
            "precision": _ratio(correct, admissions),
            "wilson_lower_95": _wilson_record(correct, admissions),
        }
    aggregate = {
        "promotion_status": PROMOTION_STATUS,
        "promotion_reason": "bounded_panel_without_preregistered_population_gate",
        "positive": {
            "total": counts["positive_total"],
            "exact_joined": counts["positive_admissions"] + counts["positive_unresolved"],
            "admissions": counts["positive_admissions"],
            "correct": counts["positive_correct"],
            "wrong": counts["positive_wrong"],
            "unresolved": counts["positive_unresolved"],
            "unjoinable": counts["positive_unjoinable"],
            "ambiguous_locator": counts["positive_ambiguous_locator"],
            "exact_join_rate": _ratio(
                counts["positive_admissions"] + counts["positive_unresolved"],
                counts["positive_total"],
            ),
            "coverage": _ratio(counts["positive_correct"], counts["positive_total"]),
            "precision": _ratio(counts["positive_correct"], counts["positive_admissions"]),
            "wilson_lower_95": _wilson_record(
                counts["positive_correct"], counts["positive_admissions"]
            ),
            "mismatch_dimension_counts": dict(sorted(mismatch_counts.items())),
            "unresolved_reason_counts": dict(sorted(unresolved_reasons.items())),
        },
        "negative": {
            "total": counts["negative_total"],
            "correct_abstention": counts["negative_correct_abstention"],
            "false_admission": counts["negative_false_admission"],
            "false_current": counts["negative_false_current"],
            "reason_mismatch": counts["negative_reason_mismatch"],
            "unjoinable": counts["negative_unjoinable"],
            "ambiguous_locator": counts["negative_ambiguous_locator"],
            "exact_joined": (
                counts["negative_total"]
                - counts["negative_unjoinable"]
                - counts["negative_ambiguous_locator"]
            ),
            "exact_join_rate": _ratio(
                counts["negative_total"]
                - counts["negative_unjoinable"]
                - counts["negative_ambiguous_locator"],
                counts["negative_total"],
            ),
            "system_non_admission": (
                counts["negative_correct_abstention"]
                + counts["negative_reason_mismatch"]
                + counts["negative_unjoinable"]
            ),
            "system_non_admission_rate": _ratio(
                counts["negative_correct_abstention"]
                + counts["negative_reason_mismatch"]
                + counts["negative_unjoinable"],
                counts["negative_total"],
            ),
            "correct_abstention_rate": _ratio(
                counts["negative_correct_abstention"], counts["negative_total"]
            ),
            "false_admission_rate": _ratio(
                counts["negative_false_admission"], counts["negative_total"]
            ),
            "false_current_rate": _ratio(
                counts["negative_false_current"], counts["negative_total"]
            ),
            "reason_counts": dict(sorted(negative_reasons.items())),
            "risk_counts": dict(sorted(risk_counts.items())),
        },
        "per_relation": per_relation,
    }
    return rows, aggregate


def analyze_panel(
    panel_path: str | Path,
    *,
    menhir_root: str | Path,
    expected_menhir_commit: str | None = None,
    generated_at: str | None = None,
    enforce_population_requirements: bool = True,
    api: PanelMenhirApi | None = None,
) -> dict[str, Any]:
    root = resolve_menhir_root(menhir_root)
    loaded_api = api or load_panel_menhir_api(root)
    panel = load_panel(
        panel_path,
        api=loaded_api,
        enforce_population_requirements=enforce_population_requirements,
    )
    rows, aggregate = _score_cases(panel, loaded_api)
    requirements = _population_requirements(list(panel.cases))
    return {
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "generated_at": generated_at or datetime.now(timezone.utc).isoformat(),
        "provenance": {
            "panel_id": panel.panel_id,
            "panel_path": str(panel.path),
            "panel_file_sha256": panel.file_sha256,
            "source_sha256": panel.source_sha256,
            "panel_schema_version": PANEL_SCHEMA_VERSION,
            "menhir": _git_metadata(root, expected_menhir_commit),
            "composer_version": loaded_api.composer_version,
            "llm_used": False,
        },
        "population_requirements": requirements,
        "aggregate": aggregate,
        "cases": rows,
    }
