"""Offline measurement of Menhir's deterministic typed-scalar shadow extractor.

This module deliberately contains no extraction, gating, normalizing, or comparison logic of its
own.  It loads those contracts from a caller-selected Menhir checkout and only owns capture
validation, report accounting, and rendering.  In particular, it never imports an HTTP client,
Neo4j driver, LLM client, or service runner.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import importlib
import json
import math
import re
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping


REPORT_SCHEMA_VERSION = 2
LABEL_SCHEMA_VERSION = 1
MENHIR_SHADOW_SCHEMA_VERSION = 2
MENHIR_COMPOSITIONAL_SCHEMA_VERSION = 1
COMPOSITIONAL_PROMOTION_STATUS = "not_evaluable"
DEFAULT_THRESHOLD = 2 / 3
DEFAULT_ALIGN_SPANS = True
UNCLASSIFIED_BUCKET = "unclassified_or_ambiguous"
_CAPTURE_SETTINGS_REQUIRED = (
    "model",
    "k",
    "temp",
    "max_tokens",
    "truncated_completions",
    "llm_calls",
)
_CAPTURE_SAMPLING_POLICY_FIELDS = ("model", "k", "temp", "max_tokens")
_LABEL_VALUES = frozenset({"false_positive", "false_current"})
LABEL_METRIC_SEMANTICS = "known_negative_target_hit_rate"
_SHA256_RE = re.compile(r"[0-9a-f]{64}")


class CaptureError(ValueError):
    """Raised when an input capture or sidecar cannot be measured safely."""


@dataclass(frozen=True)
class FrozenEpisode:
    """The exact episode fields emitted by ``freeze_scalar_samples.py``."""

    uuid: str
    content: str


@dataclass(frozen=True)
class LoadedNamespace:
    name: str
    capture_path: Path
    capture_sha256: str
    settings: dict[str, Any]
    episodes: tuple[FrozenEpisode, ...]
    samples: tuple[tuple[dict[str, Any], ...], ...]


@dataclass(frozen=True)
class LoadedCapture:
    path: Path
    sha256: str
    settings: dict[str, Any]
    namespaces: tuple[LoadedNamespace, ...]


@dataclass(frozen=True)
class LabelTarget:
    namespace: str
    episode_uuid: str
    span_start: int
    span_end: int
    label: str


@dataclass(frozen=True)
class LabelSidecar:
    path: Path
    capture_sha256: tuple[str, ...]
    labels: tuple[LabelTarget, ...]


@dataclass(frozen=True)
class MenhirApi:
    """The small, real Menhir surface used by the offline instrument."""

    proposal_type: type
    gate_typed_scalars: Callable[..., list[Any]]
    extractor_type: type
    canonical_compare: Callable[..., dict[str, Any]]
    matched_indices: Callable[..., set[int]]
    exact_match: Callable[..., bool]
    aligned_match: Callable[..., bool]
    validate_value: Callable[[str, str, Any], None]
    normalize_when: Callable[[dict[str, Any]], tuple[bool, str | None]]
    ground_span: Callable[[str, str], tuple[int, int] | None]


def _error(context: str, message: str) -> CaptureError:
    return CaptureError(f"{context}: {message}")


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_finite_json_value(value: object) -> bool:
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, list):
        return all(_is_finite_json_value(item) for item in value)
    return not isinstance(value, dict)


def _read_json(path: Path, context: str) -> Any:
    try:
        with path.open(encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError as exc:
        raise _error(context, "file does not exist") from exc
    except OSError as exc:
        raise _error(context, f"could not read file: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise _error(context, f"invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}") from exc


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise _error(str(path), f"could not hash file: {exc}") from exc
    return digest.hexdigest()


def _validate_settings(raw: Any, context: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise _error(context, "top-level 'settings' must be an object")
    missing = [key for key in _CAPTURE_SETTINGS_REQUIRED if key not in raw]
    if missing:
        raise _error(context, f"settings missing required fields: {', '.join(missing)}")

    settings = dict(raw)
    if not isinstance(settings["model"], str) or not settings["model"].strip():
        raise _error(context, "settings.model must be a non-blank string")
    if not _is_int(settings["k"]) or settings["k"] <= 0:
        raise _error(context, "settings.k must be a positive integer")
    if (
        not _is_number(settings["temp"])
        or not math.isfinite(float(settings["temp"]))
        or float(settings["temp"]) < 0
    ):
        raise _error(context, "settings.temp must be a non-negative finite number")
    if not _is_int(settings["max_tokens"]) or settings["max_tokens"] <= 0:
        raise _error(context, "settings.max_tokens must be a positive integer")
    for key in ("truncated_completions", "llm_calls"):
        if not _is_int(settings[key]) or settings[key] < 0:
            raise _error(context, f"settings.{key} must be a non-negative integer")
    if settings["truncated_completions"] > 0:
        raise _error(
            context,
            "settings.truncated_completions is greater than zero; the capture is contaminated, "
            "re-freeze with a larger --max-tokens",
        )
    return settings


def _proposal_field_names(proposal_type: type) -> set[str]:
    try:
        return {field.name for field in dataclasses.fields(proposal_type)}
    except TypeError as exc:
        raise CaptureError("Menhir TypedScalarProposal is not a dataclass") from exc


def _validate_proposal(
    raw: Any,
    *,
    proposal_type: type,
    field_names: set[str],
    namespace: str,
    sample_index: int,
    proposal_index: int,
    episodes_by_uuid: Mapping[str, FrozenEpisode],
    validate_value: Callable[[str, str, Any], None],
    normalize_when: Callable[[dict[str, Any]], tuple[bool, str | None]],
    ground_span: Callable[[str, str], tuple[int, int] | None],
) -> dict[str, Any]:
    context = f"namespace {namespace!r}, sample {sample_index}, proposal {proposal_index}"
    if not isinstance(raw, dict):
        raise _error(context, "proposal must be an object")
    missing = sorted(field_names - raw.keys())
    extra = sorted(raw.keys() - field_names)
    if missing:
        raise _error(context, f"proposal missing TypedScalarProposal fields: {', '.join(missing)}")
    if extra:
        raise _error(context, f"proposal has unknown fields: {', '.join(extra)}")

    string_fields = (
        "subject_text",
        "attribute",
        "scope",
        "value_kind",
        "unit",
        "operation",
        "stated_span",
        "episode_uuid",
        "display",
    )
    for field_name in string_fields:
        if not isinstance(raw[field_name], str):
            raise _error(context, f"{field_name} must be a string")
    for field_name in ("subject_text", "attribute", "operation", "stated_span", "value_kind"):
        if not raw[field_name].strip():
            raise _error(context, f"{field_name} must not be blank")
    when_ok, normalized_when = normalize_when(raw)
    if not when_ok or normalized_when != raw["when"]:
        raise _error(context, "when must be null or Menhir's canonical normalized ISO timestamp")
    if not _is_int(raw["span_start"]) or not _is_int(raw["span_end"]):
        raise _error(context, "span_start and span_end must be integers")
    if raw["span_start"] < 0 or raw["span_end"] <= raw["span_start"]:
        raise _error(context, "span must satisfy 0 <= span_start < span_end")
    if not _is_int(raw["claim_ordinal"]) or raw["claim_ordinal"] != 0:
        raise _error(context, "claim_ordinal must be the canonical value 0")
    if raw["value"] is None:
        raise _error(context, "value must not be null")
    if not _is_finite_json_value(raw["value"]):
        raise _error(context, "value must be a finite JSON scalar or range")
    try:
        validate_value(raw["value_kind"], raw["operation"], raw["value"])
    except ValueError as exc:
        raise _error(context, f"value fails Menhir kind/operation validation: {exc}") from exc

    episode_uuid = raw["episode_uuid"].strip()
    if not episode_uuid:
        raise _error(context, "proposal episode_uuid must not be blank")
    if raw["episode_uuid"] != episode_uuid:
        raise _error(context, "proposal episode_uuid must not have surrounding whitespace")
    episode = episodes_by_uuid.get(episode_uuid)
    if episode is None:
        raise _error(
            context,
            f"proposal episode_uuid {episode_uuid!r} is not present in the namespace episode capture",
        )
    start = raw["span_start"]
    end = raw["span_end"]
    if end > len(episode.content):
        raise _error(
            context,
            f"span [{start}, {end}) exceeds episode {episode_uuid!r} content length {len(episode.content)}",
        )
    if episode.content[start:end] != raw["stated_span"]:
        raise _error(
            context,
            f"stated_span does not equal episode content[{start}:{end}] for {episode_uuid!r}",
        )
    if ground_span(episode.content, raw["stated_span"]) != (start, end):
        raise _error(
            context,
            "stated_span must have Menhir's unique case-insensitive grounding at the serialized offsets",
        )

    try:
        proposal = proposal_type(**raw)
        # These are Menhir's own canonical properties.  Evaluating them catches malformed values
        # without reproducing normalize_scalar, source-key, or slot-key semantics here.
        _ = proposal.source_key
        _ = proposal.slot_key
        _ = proposal.normalized_value
    except Exception as exc:  # the real dataclass has no validation in __init__
        raise _error(context, f"proposal fails Menhir canonical property validation: {exc}") from exc
    return dict(raw)


def _load_capture(path: Path, api: MenhirApi) -> LoadedCapture:
    resolved = path.expanduser().resolve()
    context = f"capture {resolved}"
    if not resolved.is_file():
        raise _error(context, "path is not a regular file")
    payload = _read_json(resolved, context)
    if not isinstance(payload, dict):
        raise _error(context, "top-level JSON value must be an object")
    if "settings" not in payload or "namespaces" not in payload:
        raise _error(context, "capture must contain top-level 'settings' and 'namespaces'")
    settings = _validate_settings(payload["settings"], context)
    namespaces_raw = payload["namespaces"]
    if not isinstance(namespaces_raw, dict) or not namespaces_raw:
        raise _error(context, "top-level 'namespaces' must be a non-empty object")

    field_names = _proposal_field_names(api.proposal_type)
    namespace_rows: list[LoadedNamespace] = []
    expected_calls = 0
    capture_hash = _sha256(resolved)
    for namespace, raw_namespace in namespaces_raw.items():
        ns_context = f"capture {resolved}, namespace {namespace!r}"
        if not isinstance(namespace, str) or not namespace.strip():
            raise _error(context, "namespace keys must be non-blank strings")
        if not isinstance(raw_namespace, dict):
            raise _error(ns_context, "namespace payload must be an object")
        if "episodes" not in raw_namespace or "samples" not in raw_namespace:
            raise _error(ns_context, "namespace must contain 'episodes' and 'samples'")
        episodes_raw = raw_namespace["episodes"]
        samples_raw = raw_namespace["samples"]
        if not isinstance(episodes_raw, list) or not episodes_raw:
            raise _error(ns_context, "episodes must be a non-empty array")
        if not isinstance(samples_raw, list):
            raise _error(ns_context, "samples must be an array")
        if len(samples_raw) != settings["k"]:
            raise _error(
                ns_context,
                f"sample-count mismatch: settings.k={settings['k']} but got {len(samples_raw)} samples",
            )

        episodes: list[FrozenEpisode] = []
        episodes_by_uuid: dict[str, FrozenEpisode] = {}
        for episode_index, raw_episode in enumerate(episodes_raw):
            episode_context = f"{ns_context}, episode {episode_index}"
            if not isinstance(raw_episode, dict):
                raise _error(episode_context, "episode row must be an object")
            if set(raw_episode) != {"uuid", "content"}:
                raise _error(episode_context, "episode row must contain exactly uuid and content")
            uuid = raw_episode["uuid"]
            content = raw_episode["content"]
            if not isinstance(uuid, str) or not uuid.strip():
                raise _error(episode_context, "episode uuid must be a non-blank string")
            uuid = uuid.strip()
            if raw_episode["uuid"] != uuid:
                raise _error(episode_context, "episode uuid must not have surrounding whitespace")
            if uuid in episodes_by_uuid:
                raise _error(ns_context, f"duplicate episode uuid {uuid!r}")
            if not isinstance(content, str):
                raise _error(episode_context, "episode content must be a string")
            episode = FrozenEpisode(uuid=uuid, content=content)
            episodes.append(episode)
            episodes_by_uuid[uuid] = episode

        samples: list[tuple[dict[str, Any], ...]] = []
        for sample_index, raw_sample in enumerate(samples_raw):
            sample_context = f"{ns_context}, sample {sample_index}"
            if not isinstance(raw_sample, list):
                raise _error(sample_context, "sample must be an array of serialized proposals")
            validated_sample = tuple(
                _validate_proposal(
                    raw_proposal,
                    proposal_type=api.proposal_type,
                    field_names=field_names,
                    namespace=namespace,
                    sample_index=sample_index,
                    proposal_index=proposal_index,
                    episodes_by_uuid=episodes_by_uuid,
                    validate_value=api.validate_value,
                    normalize_when=api.normalize_when,
                    ground_span=api.ground_span,
                )
                for proposal_index, raw_proposal in enumerate(raw_sample)
            )
            samples.append(validated_sample)
        namespace_rows.append(
            LoadedNamespace(
                name=namespace,
                capture_path=resolved,
                capture_sha256=capture_hash,
                settings=settings,
                episodes=tuple(episodes),
                samples=tuple(samples),
            )
        )
        expected_calls += settings["k"]

    if settings["llm_calls"] != expected_calls:
        raise _error(
            context,
            f"settings.llm_calls={settings['llm_calls']} does not equal k calls per captured namespace "
            f"({expected_calls}); capture may be incomplete",
        )
    return LoadedCapture(
        path=resolved,
        sha256=capture_hash,
        settings=settings,
        namespaces=tuple(namespace_rows),
    )


def _validate_capture_sampling_policy(captures: tuple[LoadedCapture, ...]) -> None:
    if len(captures) < 2:
        return
    baseline = captures[0]
    for capture in captures[1:]:
        mismatches = []
        for field in _CAPTURE_SAMPLING_POLICY_FIELDS:
            expected = baseline.settings[field]
            actual = capture.settings[field]
            if actual != expected:
                mismatches.append(f"settings.{field}={actual!r} (expected {expected!r})")
        if mismatches:
            fields = ", ".join(f"settings.{field}" for field in _CAPTURE_SAMPLING_POLICY_FIELDS)
            raise CaptureError(
                f"capture sampling policy mismatch: {capture.path} differs from {baseline.path}; "
                f"{fields} must match across captures ({'; '.join(mismatches)})"
            )


def _valid_menhir_source(root: Path) -> bool:
    return (root / "src" / "menhir" / "services" / "typed_scalar_rules.py").is_file()


def resolve_menhir_root(value: str | Path | None = None) -> Path:
    """Resolve an explicit Menhir root, or one unambiguous local ``../menhir`` sibling."""
    if value is not None:
        root = Path(value).expanduser().resolve()
        if not _valid_menhir_source(root):
            raise CaptureError(
                f"Menhir root {root} is invalid; expected src/menhir/services/typed_scalar_rules.py"
            )
        return root

    candidates = {
        candidate.resolve()
        for candidate in (
            Path.cwd() / "menhir",
            Path.cwd().parent / "menhir",
            Path(__file__).resolve().parents[1].parent / "menhir",
        )
        if _valid_menhir_source(candidate)
    }
    if len(candidates) == 1:
        return next(iter(candidates))
    if not candidates:
        raise CaptureError(
            "could not find an unambiguous local Menhir sibling; pass --menhir-root "
            "C:\\path\\to\\menhir"
        )
    raise CaptureError(
        "multiple local Menhir roots were found; pass --menhir-root explicitly: "
        + ", ".join(str(candidate) for candidate in sorted(candidates))
    )


def _validate_menhir_import_identity(root: Path, modules: Iterable[Any]) -> None:
    source_path = (root / "src").resolve()
    for module in modules:
        module_name = getattr(module, "__name__", "<unnamed module>")
        module_path = getattr(module, "__file__", None)
        if module_path is None:
            raise CaptureError(
                f"Menhir import identity mismatch: selected root {root}; "
                f"{module_name} has no __file__"
            )
        resolved_module_path = Path(module_path).resolve()
        if not resolved_module_path.is_relative_to(source_path):
            raise CaptureError(
                f"Menhir import identity mismatch: selected root {root}; "
                f"{module_name} imported from {resolved_module_path}"
            )


def load_menhir_api(menhir_root: str | Path) -> MenhirApi:
    """Load the real Menhir proposal, gate, deterministic extractor, and comparator contracts."""
    root = resolve_menhir_root(menhir_root)
    source_root = str(root / "src")
    if source_root not in sys.path:
        sys.path.insert(0, source_root)
    try:
        rules = importlib.import_module("menhir.services.typed_scalar_rules")
        typed_assertion = importlib.import_module("menhir.domain.typed_assertion")
        deterministic = importlib.import_module("menhir.services.deterministic_scalar_extractor")
        service = importlib.import_module("menhir.services.typed_scalar_service")
        loaded_modules = (rules, typed_assertion, deterministic, service)
        _validate_menhir_import_identity(root, loaded_modules)
        return MenhirApi(
            proposal_type=rules.TypedScalarProposal,
            gate_typed_scalars=rules.gate_typed_scalars,
            extractor_type=deterministic.DeterministicScalarExtractor,
            canonical_compare=service._compare_deterministic_shadow,
            matched_indices=service._matched_llm_indices,
            exact_match=service._exact_shadow_match,
            aligned_match=service._aligned_shadow_match,
            validate_value=typed_assertion.validate_value,
            normalize_when=rules._normalize_when,
            ground_span=rules._ground_span,
        )
    except (ImportError, AttributeError) as exc:
        raise CaptureError(
            f"could not load the required Menhir scalar APIs from {root}: {exc}"
        ) from exc


def _git_metadata(root: Path, expected_commit: str | None) -> dict[str, Any]:
    def run(*args: str) -> str | None:
        try:
            result = subprocess.run(
                ["git", "-C", str(root), *args],
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        if result.returncode != 0:
            return None
        return result.stdout.strip()

    commit = run("rev-parse", "HEAD")
    if expected_commit is not None:
        expected = expected_commit.strip()
        if not expected:
            raise CaptureError("expected Menhir commit must not be blank")
        if commit != expected:
            actual = commit or "unavailable"
            raise CaptureError(f"Menhir commit drift: expected {expected}, found {actual}")
    status = run("status", "--porcelain", "--untracked-files=all")
    return {
        "root": str(root),
        "commit": commit,
        "dirty": None if status is None else bool(status),
        "state": "unavailable" if commit is None or status is None else ("dirty" if status else "clean"),
        "expected_commit_checked": expected_commit is not None,
    }


def _load_labels(path: str | Path, captures: tuple[LoadedCapture, ...]) -> LabelSidecar:
    resolved = Path(path).expanduser().resolve()
    context = f"label sidecar {resolved}"
    payload = _read_json(resolved, context)
    if not isinstance(payload, dict):
        raise _error(context, "top-level JSON value must be an object")
    if payload.get("schema_version") != LABEL_SCHEMA_VERSION:
        raise _error(context, f"schema_version must be {LABEL_SCHEMA_VERSION}")
    raw_labels = payload.get("labels")
    if not isinstance(raw_labels, list):
        raise _error(context, "labels must be an array")

    if "capture_sha256" not in payload:
        raise _error(context, "capture_sha256 is required")
    hashes = payload["capture_sha256"]
    if not isinstance(hashes, list) or not hashes:
        raise _error(context, "capture_sha256 must be a non-empty array")
    if any(not isinstance(item, str) or _SHA256_RE.fullmatch(item) is None for item in hashes):
        raise _error(context, "capture_sha256 must contain canonical lowercase SHA-256 hex strings")
    if len(set(hashes)) != len(hashes):
        raise _error(context, "capture_sha256 must not contain duplicate hashes")
    input_hashes = {capture.sha256 for capture in captures}
    if set(hashes) != input_hashes:
        raise _error(context, "capture_sha256 must exactly match the measured capture hashes")

    namespaces: dict[str, LoadedNamespace] = {
        namespace.name: namespace
        for capture in captures
        for namespace in capture.namespaces
    }
    labels: list[LabelTarget] = []
    seen: set[tuple[str, str, int, int]] = set()
    required = {"namespace", "episode_uuid", "span_start", "span_end", "label"}
    for index, raw_label in enumerate(raw_labels):
        label_context = f"{context}, label {index}"
        if not isinstance(raw_label, dict) or set(raw_label) != required:
            raise _error(
                label_context,
                "label must contain exactly namespace, episode_uuid, span_start, span_end, label",
            )
        namespace = raw_label["namespace"]
        episode_uuid = raw_label["episode_uuid"]
        if not isinstance(namespace, str) or namespace not in namespaces:
            raise _error(label_context, f"unknown namespace {namespace!r}")
        if not isinstance(episode_uuid, str) or episode_uuid not in {
            episode.uuid for episode in namespaces[namespace].episodes
        }:
            raise _error(label_context, f"unknown episode_uuid {episode_uuid!r} in namespace {namespace!r}")
        if not _is_int(raw_label["span_start"]) or not _is_int(raw_label["span_end"]):
            raise _error(label_context, "span_start and span_end must be integers")
        start, end = raw_label["span_start"], raw_label["span_end"]
        episode = next(episode for episode in namespaces[namespace].episodes if episode.uuid == episode_uuid)
        if start < 0 or end <= start or end > len(episode.content):
            raise _error(label_context, "label span must be inside its episode content")
        label = raw_label["label"]
        if label not in _LABEL_VALUES:
            raise _error(label_context, f"label must be one of {sorted(_LABEL_VALUES)}")
        key = (namespace, episode_uuid, start, end)
        if key in seen:
            raise _error(label_context, "duplicate label target")
        seen.add(key)
        labels.append(LabelTarget(namespace, episode_uuid, start, end, label))
    return LabelSidecar(
        path=resolved,
        capture_sha256=tuple(sorted(hashes)),
        labels=tuple(sorted(labels, key=lambda item: (item.namespace, item.episode_uuid, item.span_start, item.label))),
    )


def _ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def _ratio_record(numerator: int, denominator: int, denominator_name: str) -> dict[str, Any]:
    return {
        "numerator": numerator,
        "denominator": denominator,
        "denominator_name": denominator_name,
        "ratio": _ratio(numerator, denominator),
    }


def _counter_dict(value: Mapping[str, int] | Counter[str]) -> dict[str, int]:
    return {key: int(value[key]) for key in sorted(value)}


def _class_by_proposal_id(deterministic: Any) -> dict[int, str]:
    classes: dict[int, set[str]] = defaultdict(set)
    for episode in deterministic.episode_receipts:
        for candidate in episode.candidate_receipts:
            if candidate.outcome == "admitted" and candidate.proposal is not None:
                classes[id(candidate.proposal)].add(candidate.class_id)
    return {
        proposal_id: next(iter(values)) if len(values) == 1 else UNCLASSIFIED_BUCKET
        for proposal_id, values in classes.items()
    }


def _class_attribution(
    deterministic: Any,
    committed_llm: list[Any],
    comparison: Mapping[str, Any],
    api: MenhirApi,
    *,
    canonical_self: bool,
) -> dict[str, dict[str, int]]:
    det_proposals = list(deterministic.proposals)
    class_by_id = _class_by_proposal_id(deterministic)
    counts: dict[str, Counter[str]] = defaultdict(Counter)

    def classes_for(llm: Any, predicate: Callable[[Any, Any], bool]) -> set[str]:
        return {
            class_by_id.get(id(det), UNCLASSIFIED_BUCKET)
            for det in det_proposals
            if predicate(det, llm)
        }

    exact_indices = api.matched_indices(
        det_proposals,
        committed_llm,
        lambda det, llm: api.exact_match(det, llm, canonical_self=canonical_self),
    )
    aligned_indices = api.matched_indices(
        det_proposals,
        committed_llm,
        lambda det, llm: api.aligned_match(det, llm, canonical_self=canonical_self),
    )
    eligible = set(deterministic.fully_eligible_episode_uuids)
    for index in sorted(exact_indices):
        classes = classes_for(
            committed_llm[index],
            lambda det, llm: api.exact_match(det, llm, canonical_self=canonical_self),
        )
        bucket = next(iter(classes)) if len(classes) == 1 else UNCLASSIFIED_BUCKET
        counts[bucket]["exact_agreements"] += 1
    for index in sorted(aligned_indices):
        classes = classes_for(
            committed_llm[index],
            lambda det, llm: api.aligned_match(det, llm, canonical_self=canonical_self),
        )
        bucket = next(iter(classes)) if len(classes) == 1 else UNCLASSIFIED_BUCKET
        counts[bucket]["aligned_agreements"] += 1

    for index, llm in enumerate(committed_llm):
        if llm.episode_uuid not in eligible or index in aligned_indices:
            continue
        same_source_classes = {
            class_by_id.get(id(det), UNCLASSIFIED_BUCKET)
            for det in det_proposals
            if det.source_key == llm.source_key
        }
        bucket = next(iter(same_source_classes)) if len(same_source_classes) == 1 else UNCLASSIFIED_BUCKET
        counts[bucket]["router_missed_committed_llm_claims"] += 1

    for proposal in det_proposals:
        bucket = class_by_id.get(id(proposal), UNCLASSIFIED_BUCKET)
        counts[bucket]["deterministic_proposals"] += 1
        if proposal.episode_uuid in eligible:
            counts[bucket]["deterministic_proposals_router_eligible"] += 1

    expected = {
        "deterministic_proposals": len(det_proposals),
        "deterministic_proposals_router_eligible": sum(
            proposal.episode_uuid in eligible for proposal in det_proposals
        ),
        "exact_agreements": int(comparison["exact_agreements"]),
        "aligned_agreements": int(comparison["aligned_agreements"]),
        "router_missed_committed_llm_claims": int(comparison["router_missed_llm_claims"]),
    }
    for field, expected_total in expected.items():
        actual_total = sum(item[field] for item in counts.values())
        if actual_total != expected_total:
            raise CaptureError(
                f"canonical per-class attribution mismatch for {field}: {actual_total} != {expected_total}"
            )
    return {
        bucket: {field: int(values.get(field, 0)) for field in (
            "deterministic_proposals",
            "deterministic_proposals_router_eligible",
            "exact_agreements",
            "aligned_agreements",
            "router_missed_committed_llm_claims",
        )}
        for bucket, values in sorted(counts.items())
    }


def _label_metrics(
    namespace: str,
    deterministic: Any,
    labels: Iterable[LabelTarget],
) -> dict[str, Any]:
    selected = [label for label in labels if label.namespace == namespace]
    proposals = {
        (proposal.episode_uuid, proposal.span_start, proposal.span_end)
        for proposal in deterministic.proposals
    }
    output: dict[str, Any] = {}
    for label_value in sorted(_LABEL_VALUES):
        targets = {
            (label.episode_uuid, label.span_start, label.span_end)
            for label in selected
            if label.label == label_value
        }
        if not targets:
            output[label_value] = {
                "status": "not_measured",
                "semantics": LABEL_METRIC_SEMANTICS,
                "hit_count": None,
                "labeled_negative_targets": None,
                "hit_rate": None,
            }
            continue
        hits = targets & proposals
        output[label_value] = {
            "status": "measured",
            "semantics": LABEL_METRIC_SEMANTICS,
            "hit_count": len(hits),
            "labeled_negative_targets": len(targets),
            "hit_rate": _ratio(len(hits), len(targets)),
        }
    return output


def _empty_label_metrics() -> dict[str, Any]:
    return {
        label: {
            "status": "not_measured",
            "semantics": LABEL_METRIC_SEMANTICS,
            "hit_count": None,
            "labeled_negative_targets": None,
            "hit_rate": None,
        }
        for label in sorted(_LABEL_VALUES)
    }


def _validated_compositional_section(
    comparison: Mapping[str, Any], namespace: str
) -> dict[str, Any]:
    context = f"namespace {namespace!r}: Menhir comparator"
    if comparison.get("schema_version") != MENHIR_SHADOW_SCHEMA_VERSION:
        raise _error(
            context,
            f"schema_version must be {MENHIR_SHADOW_SCHEMA_VERSION}",
        )
    compositional = comparison.get("compositional")
    if not isinstance(compositional, dict):
        raise _error(context, "compositional must be an object")
    if compositional.get("schema_version") != MENHIR_COMPOSITIONAL_SCHEMA_VERSION:
        raise _error(
            context,
            f"compositional.schema_version must be {MENHIR_COMPOSITIONAL_SCHEMA_VERSION}",
        )
    if compositional.get("evaluation_status") != "ok":
        raise _error(context, "compositional.evaluation_status must be 'ok'")
    if compositional.get("promotion_status") != COMPOSITIONAL_PROMOTION_STATUS:
        raise _error(
            context,
            f"compositional.promotion_status must be {COMPOSITIONAL_PROMOTION_STATUS!r}",
        )
    if not isinstance(compositional.get("composer_version"), str) or not compositional[
        "composer_version"
    ].strip():
        raise _error(context, "compositional.composer_version must be a non-blank string")

    for field in (
        "deterministic_composed",
        "llm_composed",
        "deterministic_unresolved",
        "llm_unresolved",
    ):
        value = compositional.get(field)
        if not _is_int(value) or value < 0:
            raise _error(context, f"compositional.{field} must be a non-negative integer")
    for field in (
        "deterministic_unresolved_reason_counts",
        "llm_unresolved_reason_counts",
        "status_counts",
    ):
        if not isinstance(compositional.get(field), dict):
            raise _error(context, f"compositional.{field} must be an object")

    diagnostic = compositional.get("diagnostic_vs_llm")
    if not isinstance(diagnostic, dict):
        raise _error(context, "compositional.diagnostic_vs_llm must be an object")
    for field in (
        "comparison_pairs",
        "compositional_exact_agreements",
        "compositional_aligned_agreements",
        "compositional_unresolved_pairs",
        "identity_disagreements",
        "unjoinable_deterministic_claims",
        "unjoinable_llm_claims",
        "diagnostic_llm_router_misses",
    ):
        value = diagnostic.get(field)
        if not _is_int(value) or value < 0:
            raise _error(
                context,
                f"compositional.diagnostic_vs_llm.{field} must be a non-negative integer",
            )
    return compositional


def _namespace_report(
    namespace: LoadedNamespace,
    *,
    api: MenhirApi,
    threshold: float,
    align_spans: bool,
    reconcile_attribute: bool,
    reconcile_scope: bool,
    reconcile_subject: bool,
    canonical_self: bool,
    labels: Iterable[LabelTarget],
) -> dict[str, Any]:
    episodes = [FrozenEpisode(episode.uuid, episode.content) for episode in namespace.episodes]
    samples = [
        [api.proposal_type(**raw_proposal) for raw_proposal in sample]
        for sample in namespace.samples
    ]
    deterministic = api.extractor_type().extract(episodes)
    decisions = api.gate_typed_scalars(
        samples,
        threshold=threshold,
        reconcile_attribute=reconcile_attribute,
        reconcile_scope=reconcile_scope,
        reconcile_subject=reconcile_subject,
        canonical_self=canonical_self,
        align_spans=align_spans,
    )
    committed_llm = []
    for decision in decisions:
        if decision.committed:
            if decision.proposal is None:
                raise CaptureError(
                    f"namespace {namespace.name!r}: Menhir gate returned a committed decision without a proposal"
                )
            committed_llm.append(decision.proposal)

    comparison = api.canonical_compare(
        deterministic,
        committed_llm,
        canonical_self=canonical_self,
        source_by_episode={episode.uuid: episode.content for episode in namespace.episodes},
    )
    compositional = _validated_compositional_section(comparison, namespace.name)
    expected_counts = {
        "episodes_total": len(deterministic.episode_receipts),
        "episodes_fully_eligible": len(deterministic.fully_eligible_episode_uuids),
        "proposals_all": len(deterministic.proposals),
        "proposals_router_eligible": sum(
            proposal.episode_uuid in set(deterministic.fully_eligible_episode_uuids)
            for proposal in deterministic.proposals
        ),
        "committed_llm": len(committed_llm),
    }
    for key, expected in expected_counts.items():
        if int(comparison[key]) != expected:
            raise CaptureError(
                f"namespace {namespace.name!r}: canonical comparator {key}={comparison[key]} "
                f"does not match measured input {expected}"
            )

    eligible = set(deterministic.fully_eligible_episode_uuids)
    fully_eligible = len(eligible)
    baseline_calls = namespace.settings["k"]
    future_calls = 0 if fully_eligible == len(namespace.episodes) else baseline_calls
    saved_calls = baseline_calls - future_calls
    det_outcomes = _counter_dict(comparison["deterministic_outcome_counts"])
    det_reasons = _counter_dict(comparison["deterministic_drop_reason_counts"])
    det_reason_counts = _counter_dict(dict(deterministic.reason_counts))
    det_classes = _counter_dict(comparison["deterministic_class_counts"])
    labels_report = _label_metrics(namespace.name, deterministic, labels)
    attribution = _class_attribution(
        deterministic,
        committed_llm,
        comparison,
        api,
        canonical_self=canonical_self,
    )

    return {
        "namespace": namespace.name,
        "capture": {"path": str(namespace.capture_path), "sha256": namespace.capture_sha256},
        "capture_settings": dict(namespace.settings),
        "episodes": {
            "total": len(namespace.episodes),
            "fully_eligible": fully_eligible,
            "fallback_required": len(namespace.episodes) - fully_eligible,
        },
        "deterministic_proposals": {
            "all": len(deterministic.proposals),
            "router_eligible": expected_counts["proposals_router_eligible"],
        },
        "committed_llm_claims": len(committed_llm),
        "agreement": {
            "exact_one_to_one": {
                **_ratio_record(int(comparison["exact_agreements"]), len(committed_llm), "committed_llm_claims"),
                "matching": "Menhir canonical comparator one-to-one",
            },
            "aligned_one_to_one": {
                **_ratio_record(int(comparison["aligned_agreements"]), len(committed_llm), "committed_llm_claims"),
                "matching": "Menhir canonical comparator one-to-one",
            },
        },
        "router_missed_committed_llm_claims": int(comparison["router_missed_llm_claims"]),
        "deterministic_counts": {
            "outcomes": det_outcomes,
            "drop_reasons": det_reasons,
            "reason_counts": det_reason_counts,
            "admitted_classes": det_classes,
        },
        "coverage": {
            "eligible_episode_ratio": _ratio_record(
                fully_eligible, len(namespace.episodes), "episodes_total"
            ),
            "deterministic_proposal_ratio_of_committed_llm": _ratio_record(
                len(deterministic.proposals), len(committed_llm), "committed_llm_claims"
            ),
            "router_eligible_proposal_ratio_of_committed_llm": _ratio_record(
                expected_counts["proposals_router_eligible"], len(committed_llm), "committed_llm_claims"
            ),
            "router_miss_ratio": _ratio_record(
                int(comparison["router_missed_llm_claims"]), len(committed_llm), "committed_llm_claims"
            ),
        },
        "per_class_agreement": attribution,
        "compositional": compositional,
        "labels": labels_report,
        "call_savings": {
            "boundary": "namespace_batch",
            "k_sample_batch_covers_all_namespace_episodes": True,
            "baseline_scalar_llm_calls": baseline_calls,
            "conservative_future_scalar_llm_calls": future_calls,
            "conservative_future_calls_saved": saved_calls,
            "saved_namespace_batch": saved_calls > 0,
        },
        "comparison_detail": {
            "canonical_schema_version": comparison.get("schema_version"),
            "extractor_version": comparison.get("extractor_version"),
            "template_version": comparison.get("template_version"),
            "compositional_schema_version": compositional.get("schema_version"),
            "composer_version": compositional.get("composer_version"),
        },
    }


def _aggregate_compositional(namespace_reports: list[dict[str, Any]]) -> dict[str, Any]:
    rows = [report["compositional"] for report in namespace_reports]
    diagnostic_fields = (
        "comparison_pairs",
        "compositional_exact_agreements",
        "compositional_aligned_agreements",
        "compositional_unresolved_pairs",
        "identity_disagreements",
        "unjoinable_deterministic_claims",
        "unjoinable_llm_claims",
        "diagnostic_llm_router_misses",
    )
    diagnostic = {
        field: sum(int(row["diagnostic_vs_llm"][field]) for row in rows)
        for field in diagnostic_fields
    }
    det_reasons: Counter[str] = Counter()
    llm_reasons: Counter[str] = Counter()
    statuses: Counter[str] = Counter()
    for row in rows:
        det_reasons.update(row["deterministic_unresolved_reason_counts"])
        llm_reasons.update(row["llm_unresolved_reason_counts"])
        statuses.update(row["status_counts"])
    comparison_pairs = diagnostic["comparison_pairs"]
    return {
        "schema_versions": sorted({int(row["schema_version"]) for row in rows}),
        "composer_versions": sorted({str(row["composer_version"]) for row in rows}),
        "promotion_status": COMPOSITIONAL_PROMOTION_STATUS,
        "deterministic_composed": sum(int(row["deterministic_composed"]) for row in rows),
        "llm_composed": sum(int(row["llm_composed"]) for row in rows),
        "deterministic_unresolved": sum(int(row["deterministic_unresolved"]) for row in rows),
        "llm_unresolved": sum(int(row["llm_unresolved"]) for row in rows),
        "deterministic_unresolved_reason_counts": _counter_dict(det_reasons),
        "llm_unresolved_reason_counts": _counter_dict(llm_reasons),
        "status_counts": _counter_dict(statuses),
        "diagnostic_vs_llm": {
            **diagnostic,
            "exact_ratio": _ratio(
                diagnostic["compositional_exact_agreements"], comparison_pairs),
            "aligned_ratio": _ratio(
                diagnostic["compositional_aligned_agreements"], comparison_pairs),
            "unresolved_ratio": _ratio(
                diagnostic["compositional_unresolved_pairs"], comparison_pairs),
            "identity_disagreement_ratio": _ratio(
                diagnostic["identity_disagreements"], comparison_pairs),
        },
    }


def _aggregate_reports(namespace_reports: list[dict[str, Any]]) -> dict[str, Any]:
    episodes_total = sum(report["episodes"]["total"] for report in namespace_reports)
    fully_eligible = sum(report["episodes"]["fully_eligible"] for report in namespace_reports)
    det_all = sum(report["deterministic_proposals"]["all"] for report in namespace_reports)
    det_router = sum(report["deterministic_proposals"]["router_eligible"] for report in namespace_reports)
    committed = sum(report["committed_llm_claims"] for report in namespace_reports)
    exact = sum(report["agreement"]["exact_one_to_one"]["numerator"] for report in namespace_reports)
    aligned = sum(report["agreement"]["aligned_one_to_one"]["numerator"] for report in namespace_reports)
    router_missed = sum(report["router_missed_committed_llm_claims"] for report in namespace_reports)
    outcome_counts: Counter[str] = Counter()
    reason_counts: Counter[str] = Counter()
    all_reason_counts: Counter[str] = Counter()
    class_counts: Counter[str] = Counter()
    per_class: dict[str, Counter[str]] = defaultdict(Counter)
    for report in namespace_reports:
        outcome_counts.update(report["deterministic_counts"]["outcomes"])
        reason_counts.update(report["deterministic_counts"]["drop_reasons"])
        all_reason_counts.update(report["deterministic_counts"]["reason_counts"])
        class_counts.update(report["deterministic_counts"]["admitted_classes"])
        for bucket, values in report["per_class_agreement"].items():
            per_class[bucket].update(values)

    def aggregate_label(label: str) -> dict[str, Any]:
        metrics = [report["labels"][label] for report in namespace_reports]
        measured = any(metric["status"] == "measured" for metric in metrics)
        if not measured:
            return {
                "status": "not_measured",
                "semantics": LABEL_METRIC_SEMANTICS,
                "hit_count": None,
                "labeled_negative_targets": None,
                "hit_rate": None,
            }
        hit_count = sum(metric["hit_count"] or 0 for metric in metrics)
        labeled_negative_targets = sum(metric["labeled_negative_targets"] or 0 for metric in metrics)
        return {
            "status": "measured",
            "semantics": LABEL_METRIC_SEMANTICS,
            "hit_count": hit_count,
            "labeled_negative_targets": labeled_negative_targets,
            "hit_rate": _ratio(hit_count, labeled_negative_targets),
        }

    baseline_calls = sum(report["call_savings"]["baseline_scalar_llm_calls"] for report in namespace_reports)
    future_calls = sum(report["call_savings"]["conservative_future_scalar_llm_calls"] for report in namespace_reports)
    saved_calls = sum(report["call_savings"]["conservative_future_calls_saved"] for report in namespace_reports)
    return {
        "namespaces_total": len(namespace_reports),
        "episodes": {
            "total": episodes_total,
            "fully_eligible": fully_eligible,
            "fallback_required": episodes_total - fully_eligible,
        },
        "deterministic_proposals": {"all": det_all, "router_eligible": det_router},
        "committed_llm_claims": committed,
        "agreement": {
            "exact_one_to_one": {
                **_ratio_record(exact, committed, "committed_llm_claims"),
                "matching": "Menhir canonical comparator one-to-one",
            },
            "aligned_one_to_one": {
                **_ratio_record(aligned, committed, "committed_llm_claims"),
                "matching": "Menhir canonical comparator one-to-one",
            },
        },
        "router_missed_committed_llm_claims": router_missed,
        "deterministic_counts": {
            "outcomes": _counter_dict(outcome_counts),
            "drop_reasons": _counter_dict(reason_counts),
            "reason_counts": _counter_dict(all_reason_counts),
            "admitted_classes": _counter_dict(class_counts),
        },
        "coverage": {
            "eligible_episode_ratio": _ratio_record(fully_eligible, episodes_total, "episodes_total"),
            "deterministic_proposal_ratio_of_committed_llm": _ratio_record(
                det_all, committed, "committed_llm_claims"
            ),
            "router_eligible_proposal_ratio_of_committed_llm": _ratio_record(
                det_router, committed, "committed_llm_claims"
            ),
            "router_miss_ratio": _ratio_record(router_missed, committed, "committed_llm_claims"),
        },
        "per_class_agreement": {
            bucket: {field: int(values.get(field, 0)) for field in (
                "deterministic_proposals",
                "deterministic_proposals_router_eligible",
                "exact_agreements",
                "aligned_agreements",
                "router_missed_committed_llm_claims",
            )}
            for bucket, values in sorted(per_class.items())
        },
        "labels": {label: aggregate_label(label) for label in sorted(_LABEL_VALUES)},
        "compositional": _aggregate_compositional(namespace_reports),
        "call_savings": {
            "boundary": "namespace_batch",
            "k_sample_batch_covers_all_namespace_episodes": True,
            "baseline_scalar_llm_calls": baseline_calls,
            "conservative_future_scalar_llm_calls": future_calls,
            "conservative_future_calls_saved": saved_calls,
            "saved_namespace_batches": sum(
                report["call_savings"]["saved_namespace_batch"] for report in namespace_reports
            ),
        },
    }


def analyze_captures(
    capture_paths: Iterable[str | Path],
    *,
    menhir_root: str | Path | None = None,
    labels_path: str | Path | None = None,
    threshold: float = DEFAULT_THRESHOLD,
    align_spans: bool = DEFAULT_ALIGN_SPANS,
    reconcile_attribute: bool = False,
    reconcile_scope: bool = False,
    reconcile_subject: bool = False,
    canonical_self: bool = False,
    expected_menhir_commit: str | None = None,
    api: MenhirApi | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Validate, measure, and return a deterministic report without external calls."""
    if not _is_number(threshold) or not 0 < float(threshold) <= 1:
        raise CaptureError("effective threshold must be a number in (0, 1]")
    paths = [Path(path) for path in capture_paths]
    if not paths:
        raise CaptureError("at least one capture path is required")
    resolved_paths = [path.expanduser().resolve() for path in paths]
    if len(set(resolved_paths)) != len(resolved_paths):
        raise CaptureError("capture paths must be unique")

    root = resolve_menhir_root(menhir_root)
    loaded_api = api or load_menhir_api(root)
    captures = tuple(_load_capture(path, loaded_api) for path in resolved_paths)
    _validate_capture_sampling_policy(captures)
    namespaces = [namespace for capture in captures for namespace in capture.namespaces]
    namespace_names = [namespace.name for namespace in namespaces]
    if len(set(namespace_names)) != len(namespace_names):
        duplicates = sorted(name for name, count in Counter(namespace_names).items() if count > 1)
        raise CaptureError("namespace names must be unique across captures: " + ", ".join(duplicates))
    sidecar = _load_labels(labels_path, captures) if labels_path is not None else None
    label_rows = sidecar.labels if sidecar is not None else ()
    sidecar_provenance = (
        {
            "path": str(sidecar.path),
            "sha256": _sha256(sidecar.path),
            "schema_version": LABEL_SCHEMA_VERSION,
            "capture_sha256": list(sidecar.capture_sha256),
        }
        if sidecar is not None
        else None
    )

    reports = [
        _namespace_report(
            namespace,
            api=loaded_api,
            threshold=float(threshold),
            align_spans=bool(align_spans),
            reconcile_attribute=bool(reconcile_attribute),
            reconcile_scope=bool(reconcile_scope),
            reconcile_subject=bool(reconcile_subject),
            canonical_self=bool(canonical_self),
            labels=label_rows,
        )
        for namespace in sorted(namespaces, key=lambda item: item.name)
    ]
    extractor_versions = sorted({report["comparison_detail"]["extractor_version"] for report in reports})
    template_versions = sorted({report["comparison_detail"]["template_version"] for report in reports})
    if generated_at is None:
        generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    provenance = {
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "generated_at": generated_at,
        "captures": [
            {"path": str(capture.path), "sha256": capture.sha256, "settings": dict(capture.settings)}
            for capture in sorted(captures, key=lambda item: str(item.path))
        ],
        "label_sidecar": sidecar_provenance,
        "menhir": _git_metadata(root, expected_menhir_commit),
        "extractor_versions": extractor_versions,
        "template_versions": template_versions,
    }
    effective_gate_settings = {
        "threshold": float(threshold),
        "align_spans": bool(align_spans),
        "reconcile_attribute": bool(reconcile_attribute),
        "reconcile_scope": bool(reconcile_scope),
        "reconcile_subject": bool(reconcile_subject),
        "canonical_self": bool(canonical_self),
        "source": "explicit instrument arguments/defaults; not inferred from freeze capture",
        "k_source": "settings.k recorded by each capture; samples validated against it",
    }
    report = {
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "provenance": provenance,
        "effective_gate_settings": effective_gate_settings,
        "capture_sampling_policy": {
            "shared_fields": list(_CAPTURE_SAMPLING_POLICY_FIELDS),
            "llm_calls": "per_capture",
            "truncated_completions": "must_be_zero_per_capture",
        },
        "capture_settings": [
            {"path": str(capture.path), "settings": dict(capture.settings)}
            for capture in sorted(captures, key=lambda item: str(item.path))
        ],
        "aggregate": _aggregate_reports(reports),
        "namespaces": reports,
        "measurements": {
            "token_savings": None,
            "dollar_savings": None,
            "status": "not_measured; captures contain no measured token or cost fields",
        },
        "labels": {
            "status": "provided" if sidecar is not None else "absent",
            "semantics": LABEL_METRIC_SEMANTICS,
            "schema_version": LABEL_SCHEMA_VERSION if sidecar is not None else None,
            "path": sidecar_provenance["path"] if sidecar_provenance is not None else None,
            "sha256": sidecar_provenance["sha256"] if sidecar_provenance is not None else None,
            "capture_sha256": (
                sidecar_provenance["capture_sha256"] if sidecar_provenance is not None else None
            ),
        },
    }
    return report


def _format_ratio(record: Mapping[str, Any]) -> str:
    ratio = record.get("ratio")
    return "n/a" if ratio is None else f"{float(ratio):.1%}"


def render_markdown(report: Mapping[str, Any]) -> str:
    """Render a concise, deterministic Markdown summary from the machine report."""
    aggregate = report["aggregate"]
    compositional = aggregate["compositional"]["diagnostic_vs_llm"]
    lines = [
        "# Deterministic scalar shadow measurement",
        "",
        f"Generated: {report['provenance']['generated_at']}",
        f"Report schema: v{report['report_schema_version']}",
        f"Menhir: `{report['provenance']['menhir'].get('commit') or 'unavailable'}` "
        f"({report['provenance']['menhir'].get('state', 'unavailable')})",
        "",
        "Effective gate settings: "
        f"threshold={report['effective_gate_settings']['threshold']:.6g}, "
        f"align_spans={str(report['effective_gate_settings']['align_spans']).lower()}, "
        f"reconcile_attribute={str(report['effective_gate_settings']['reconcile_attribute']).lower()}, "
        f"reconcile_scope={str(report['effective_gate_settings']['reconcile_scope']).lower()}, "
        f"reconcile_subject={str(report['effective_gate_settings']['reconcile_subject']).lower()}, "
        f"canonical_self={str(report['effective_gate_settings']['canonical_self']).lower()}",
        "",
        "## Aggregate",
        "",
        "| Measure | Value |",
        "|---|---:|",
        f"| Namespaces | {aggregate['namespaces_total']} |",
        f"| Episodes fully eligible / total | {aggregate['episodes']['fully_eligible']} / "
        f"{aggregate['episodes']['total']} "
        f"({_format_ratio(aggregate['coverage']['eligible_episode_ratio'])}) |",
        f"| Deterministic proposals all / router-eligible | {aggregate['deterministic_proposals']['all']} / "
        f"{aggregate['deterministic_proposals']['router_eligible']} |",
        f"| Committed LLM claims | {aggregate['committed_llm_claims']} |",
        f"| Exact one-to-one agreement | {aggregate['agreement']['exact_one_to_one']['numerator']} / "
        f"{aggregate['agreement']['exact_one_to_one']['denominator']} "
        f"({_format_ratio(aggregate['agreement']['exact_one_to_one'])}) |",
        f"| Aligned one-to-one agreement | {aggregate['agreement']['aligned_one_to_one']['numerator']} / "
        f"{aggregate['agreement']['aligned_one_to_one']['denominator']} "
        f"({_format_ratio(aggregate['agreement']['aligned_one_to_one'])}) |",
        f"| Router-missed committed LLM claims | {aggregate['router_missed_committed_llm_claims']} |",
        f"| Compositional exact / compared pairs | "
        f"{compositional['compositional_exact_agreements']} / {compositional['comparison_pairs']} |",
        f"| Compositional aligned / compared pairs | "
        f"{compositional['compositional_aligned_agreements']} / {compositional['comparison_pairs']} |",
        f"| Compositional unresolved / identity disagreement | "
        f"{compositional['compositional_unresolved_pairs']} / "
        f"{compositional['identity_disagreements']} |",
        f"| Baseline / conservative future calls | {aggregate['call_savings']['baseline_scalar_llm_calls']} / "
        f"{aggregate['call_savings']['conservative_future_scalar_llm_calls']} "
        f"(saved {aggregate['call_savings']['conservative_future_calls_saved']}) |",
        "",
        "## Namespaces",
        "",
        "| Namespace | Eligible / episodes | Det all / router | LLM committed | Exact | Aligned | "
        "Router misses | Calls saved |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for item in report["namespaces"]:
        name = str(item["namespace"]).replace("|", "\\|")
        lines.append(
            f"| {name} | {item['episodes']['fully_eligible']} / {item['episodes']['total']} | "
            f"{item['deterministic_proposals']['all']} / {item['deterministic_proposals']['router_eligible']} | "
            f"{item['committed_llm_claims']} | {item['agreement']['exact_one_to_one']['numerator']} | "
            f"{item['agreement']['aligned_one_to_one']['numerator']} | "
            f"{item['router_missed_committed_llm_claims']} | "
            f"{item['call_savings']['conservative_future_calls_saved']} |"
        )
    label_note = (
        "provided by the versioned sidecar"
        if report["labels"]["status"] == "provided"
        else "not measured (no label sidecar supplied)"
    )
    lines.extend([
        "",
        "## Per-class attribution",
        "",
        "Counts use Menhir's canonical one-to-one matching; unmatched or ambiguous router misses stay in "
        f"`{UNCLASSIFIED_BUCKET}`.",
        "",
        "| Class / bucket | Deterministic | Exact | Aligned | Router misses |",
        "|---|---:|---:|---:|---:|",
    ])
    for bucket, values in aggregate["per_class_agreement"].items():
        lines.append(
            f"| `{bucket}` | {values['deterministic_proposals']} | {values['exact_agreements']} | "
            f"{values['aligned_agreements']} | {values['router_missed_committed_llm_claims']} |"
        )
    lines.extend([
        "",
        "## Known-negative target hit metrics",
        "",
        "Each `false_positive` or `false_current` sidecar row is a human-labeled known-negative target.",
        "These are target-hit metrics, not overall or population false-positive/current rates, and they do "
        "not satisfy the plan's population precision or confidence-interval gate.",
        "",
        "| Category | Status | Hit count | Labeled negative targets | Hit rate |",
        "|---|---|---:|---:|---:|",
    ])
    for label in sorted(_LABEL_VALUES):
        metric = aggregate["labels"][label]
        hit_count = metric["hit_count"] if metric["hit_count"] is not None else "n/a"
        labeled_targets = (
            metric["labeled_negative_targets"]
            if metric["labeled_negative_targets"] is not None
            else "n/a"
        )
        hit_rate = _format_ratio({"ratio": metric["hit_rate"]})
        lines.append(
            f"| `{label}` | {metric['status']} | {hit_count} | {labeled_targets} | {hit_rate} |"
        )
    lines.extend([
        "",
        "## Measurement limits",
        "",
        "- Calls saved are conservative namespace-batch savings: one k-sample batch covers every "
        "episode in a namespace, so any fallback episode preserves all k calls.",
        "- Token and dollar savings are not measured; the capture has no measured token/cost fields.",
        f"- Known-negative target labels are {label_note}.",
    ])
    return "\n".join(lines) + "\n"


def write_reports(report: Mapping[str, Any], json_path: str | Path, markdown_path: str | Path) -> None:
    json_target = Path(json_path)
    markdown_target = Path(markdown_path)
    json_target.parent.mkdir(parents=True, exist_ok=True)
    markdown_target.parent.mkdir(parents=True, exist_ok=True)
    with json_target.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, ensure_ascii=False, sort_keys=True)
        handle.write("\n")
    markdown_target.write_text(render_markdown(report), encoding="utf-8")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Measure Menhir deterministic typed-scalar shadow behavior from frozen captures offline."
    )
    parser.add_argument("captures", nargs="+", help="JSON files produced by freeze_scalar_samples.py")
    parser.add_argument(
        "--menhir-root",
        help="Menhir source checkout (required unless one local sibling is unambiguous)",
    )
    parser.add_argument("--labels", help="optional v1 capture-local label sidecar JSON")
    parser.add_argument("--json-out", required=True, help="machine-readable report path")
    parser.add_argument("--markdown-out", required=True, help="concise Markdown report path")
    parser.add_argument(
        "--threshold",
        type=float,
        default=DEFAULT_THRESHOLD,
        help="gate threshold (default: exactly 2/3)",
    )
    parser.add_argument(
        "--align-spans",
        action=argparse.BooleanOptionalAction,
        default=DEFAULT_ALIGN_SPANS,
        help="use Menhir's canonical common-span alignment (default: on)",
    )
    parser.add_argument("--reconcile-attribute", action="store_true", help="enable Menhir attribute reconciliation")
    parser.add_argument("--reconcile-scope", action="store_true", help="enable Menhir scope reconciliation")
    parser.add_argument("--reconcile-subject", action="store_true", help="enable Menhir subject reconciliation")
    parser.add_argument("--canonical-self", action="store_true", help="enable Menhir canonical-self interpretation")
    parser.add_argument("--expected-menhir-commit", help="fail only if Menhir HEAD differs from this explicit commit")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    try:
        report = analyze_captures(
            args.captures,
            menhir_root=args.menhir_root,
            labels_path=args.labels,
            threshold=args.threshold,
            align_spans=args.align_spans,
            reconcile_attribute=args.reconcile_attribute,
            reconcile_scope=args.reconcile_scope,
            reconcile_subject=args.reconcile_subject,
            canonical_self=args.canonical_self,
            expected_menhir_commit=args.expected_menhir_commit,
        )
        write_reports(report, args.json_out, args.markdown_out)
    except CaptureError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
