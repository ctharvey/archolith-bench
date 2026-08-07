"""Bench-only dependency evidence emitter and pinned offline spaCy adapter.

The emitter consumes a small, parser-neutral parsed-document protocol and emits the serialized
shape of Menhir's immutable transport envelope, never a proposal or semantic identity. The
optional adapter loads only the pinned research parser/model and parses one caller-grounded
candidate slice at a time; it remains syntax-only and fail-closed.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import re
from dataclasses import dataclass
from collections.abc import Mapping, Sequence
from importlib.metadata import PackageNotFoundError, distribution
from typing import Any, Literal

SCHEMA_VERSION = "scalar-dependency-v1"
EVIDENCE_VERSION = "parser-evidence-v1"
MAX_SOURCE_LENGTH = 1_000_000
MAX_TOKENS = 512
MAX_EDGES = 1_024
MAX_MARKERS = 128
MAX_CUES = 64
MAX_DISCOVERED_CANDIDATES = 64
PINNED_SPACY_VERSION = "3.8.14"
PINNED_MODEL_NAME = "en_core_web_sm"
PINNED_MODEL_VERSION = "3.8.0"
PINNED_MODEL_HASH = "1932429db727d4bff3deed6b34cfc05df17794f4a52eeb26cf8928f7c1a0fb85"
PINNED_MODEL_URL = (
    "https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/"
    "en_core_web_sm-3.8.0-py3-none-any.whl"
)
_ALLOWED_SPACY_CONFIG = frozenset({"disable", "exclude"})
_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_METADATA_TOKEN_RE = re.compile(r"^[a-z0-9._-]{1,64}$")


class _EmitterError(ValueError):
    pass


def _text(value: object, name: str, maximum: int = 128) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip() or len(value) > maximum:
        raise _EmitterError(f"{name}_invalid")
    return value


def _hash(value: object, name: str) -> str:
    if not isinstance(value, str) or _HASH_RE.fullmatch(value) is None:
        raise _EmitterError(f"{name}_invalid")
    return value


def _metadata_token(value: object, name: str) -> str:
    if not isinstance(value, str) or _METADATA_TOKEN_RE.fullmatch(value) is None:
        raise _EmitterError(f"{name}_invalid")
    return value


def _int(value: object, name: str) -> int:
    if type(value) is not int:
        raise _EmitterError(f"{name}_invalid")
    return value


def _span_bounds(span: "ParsedSpan", source_length: int, name: str) -> None:
    start = _int(span.start, f"{name}_start")
    end = _int(span.end, f"{name}_end")
    if start < 0 or start >= end or end > source_length:
        raise _EmitterError(f"{name}_bounds_invalid")
    if (span.token_start is None) != (span.token_end is None):
        raise _EmitterError(f"{name}_token_bounds_invalid")
    if span.token_start is not None:
        token_start = _int(span.token_start, f"{name}_token_start")
        token_end = _int(span.token_end, f"{name}_token_end")
        if token_start < 0 or token_start >= token_end:
            raise _EmitterError(f"{name}_token_bounds_invalid")


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class ParsedSpan:
    start: int
    end: int
    token_start: int | None = None
    token_end: int | None = None


@dataclass(frozen=True, slots=True)
class ParsedToken:
    token_index: int
    span: ParsedSpan
    head_index: int
    dependency_label: str
    pos_tag: str
    lemma: str


@dataclass(frozen=True, slots=True)
class ParsedEdge:
    head_index: int
    dependent_index: int
    label: str


@dataclass(frozen=True, slots=True)
class ParsedCue:
    subject: ParsedSpan | None
    predicate: ParsedSpan | None
    numeric_value: ParsedSpan
    unit: ParsedSpan | None
    target: ParsedSpan | None
    modifiers: tuple[ParsedSpan, ...]
    scope: ParsedSpan | None
    clause_root_token: int


@dataclass(frozen=True, slots=True)
class ParsedMarker:
    category: str
    span: ParsedSpan
    token_indices: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class ParserMetadata:
    parser_id: str
    parser_version: str
    model_hash: str
    pipeline_hash: str


@dataclass(frozen=True, slots=True)
class ParsedDocument:
    source: str
    clause_span: ParsedSpan
    tokens: tuple[ParsedToken, ...]
    edges: tuple[ParsedEdge, ...]
    cues: ParsedCue
    markers: tuple[ParsedMarker, ...]
    metadata: ParserMetadata


@dataclass(frozen=True, slots=True)
class CandidateLocator:
    """Source span plus an externally supplied candidate hash.

    The emitter only checks the hash syntax and passes it through. It grants no candidate authority;
    Menhir must independently compare it with the expected hash, episode, and source key.
    """

    start: int
    end: int
    candidate_hash: str
    ordinal: int = 0


@dataclass(frozen=True, slots=True)
class EmissionResult:
    status: Literal["emitted", "abstained"]
    reason: str
    evidence: dict[str, object] | None = None
    fingerprint: str | None = None


@dataclass(frozen=True, slots=True)
class ParserOutcome:
    status: Literal["parsed", "unavailable", "error"]
    reason: str
    diagnostics: tuple[str, ...] = ()
    document: ParsedDocument | None = None


@dataclass(frozen=True, slots=True)
class CandidateSpan:
    """Gold-free syntax locator; contains offsets only and no source text."""

    clause_start: int
    clause_end: int
    numeric_start: int
    numeric_end: int
    subject_start: int
    subject_end: int
    predicate_start: int
    predicate_end: int
    target_start: int
    target_end: int


@dataclass(frozen=True, slots=True)
class DiscoveryOutcome:
    status: Literal["discovered", "unavailable", "error"]
    reason: str
    diagnostics: tuple[str, ...] = ()
    candidates: tuple[CandidateSpan, ...] = ()


def _span_payload(span: ParsedSpan, source: str) -> dict[str, object]:
    return {
        "end": span.end,
        "start": span.start,
        "surface_sha256": _sha256_text(source[span.start : span.end]),
        "token_end": span.token_end,
        "token_start": span.token_start,
    }


def _validate_span_alignment(span: ParsedSpan, tokens: tuple[ParsedToken, ...], source_length: int, name: str) -> None:
    _span_bounds(span, source_length, name)
    if span.token_start is None:
        return
    assert span.token_end is not None
    if span.token_end > len(tokens):
        raise _EmitterError(f"{name}_token_range_invalid")
    expected_start = tokens[span.token_start].span.start
    expected_end = tokens[span.token_end - 1].span.end
    if (span.start, span.end) != (expected_start, expected_end):
        raise _EmitterError(f"{name}_token_alignment_invalid")


def _validate_document(document: ParsedDocument) -> str:
    if not isinstance(document, ParsedDocument):
        raise _EmitterError("document_type_invalid")
    if type(document.source) is not str:
        raise _EmitterError("source_type_invalid")
    source_length = len(document.source)
    if source_length == 0 or source_length > MAX_SOURCE_LENGTH:
        raise _EmitterError("source_length_invalid")
    metadata = document.metadata
    if not isinstance(metadata, ParserMetadata):
        raise _EmitterError("metadata_type_invalid")
    _metadata_token(metadata.parser_id, "parser_id")
    _metadata_token(metadata.parser_version, "parser_version")
    _hash(metadata.model_hash, "model_hash")
    _hash(metadata.pipeline_hash, "pipeline_hash")

    tokens = document.tokens
    if not isinstance(tokens, tuple) or not tokens or len(tokens) > MAX_TOKENS:
        raise _EmitterError("tokens_invalid")
    for index, token in enumerate(tokens):
        if not isinstance(token, ParsedToken) or type(token.token_index) is not int or token.token_index != index:
            raise _EmitterError("token_indices_invalid")
    previous_end: int | None = None
    for index, token in enumerate(tokens):
        _span_bounds(token.span, source_length, f"token_{index}_span")
        if previous_end is not None and token.span.start < previous_end:
            raise _EmitterError("token_spans_overlap_or_out_of_order")
        previous_end = token.span.end
        _text(token.dependency_label, f"token_{index}_dependency_label", 64)
        _text(token.pos_tag, f"token_{index}_pos_tag", 32)
        _text(token.lemma, f"token_{index}_lemma", 256)
        if type(token.head_index) is not int or token.head_index < -1 or token.head_index >= len(tokens):
            raise _EmitterError("token_head_index_invalid")
        if token.span.token_start is not None and (
            token.span.token_start != index or token.span.token_end != index + 1
        ):
            raise _EmitterError("token_span_alignment_invalid")

    clause = document.clause_span
    _validate_span_alignment(clause, tokens, source_length, "clause_span")
    if clause.token_start is not None and (clause.token_start, clause.token_end) != (0, len(tokens)):
        raise _EmitterError("clause_span_token_bounds_invalid")
    for index, token in enumerate(tokens):
        if token.span.start < clause.start or token.span.end > clause.end:
            raise _EmitterError(f"token_{index}_outside_clause")

    roots = tuple(token.token_index for token in tokens if token.head_index == -1)
    if not isinstance(document.cues, ParsedCue):
        raise _EmitterError("cues_type_invalid")
    if len(roots) != 1 or roots[0] != document.cues.clause_root_token:
        raise _EmitterError("root_invariant_invalid")

    edges = document.edges
    if not isinstance(edges, tuple) or len(edges) > MAX_EDGES or len(edges) != len(tokens) - 1:
        raise _EmitterError("edges_invalid")
    for index, edge in enumerate(edges):
        if not isinstance(edge, ParsedEdge):
            raise _EmitterError(f"edge_{index}_type_invalid")
    if tuple(edge.dependent_index for edge in edges) != tuple(sorted(edge.dependent_index for edge in edges)):
        raise _EmitterError("edge_order_invalid")
    edge_by_dependent: dict[int, ParsedEdge] = {}
    for index, edge in enumerate(edges):
        if (
            type(edge.head_index) is not int
            or type(edge.dependent_index) is not int
            or edge.head_index < 0
            or edge.head_index >= len(tokens)
            or edge.dependent_index < 0
            or edge.dependent_index >= len(tokens)
        ):
            raise _EmitterError("edge_index_invalid")
        if edge.head_index == edge.dependent_index or edge.dependent_index in edge_by_dependent:
            raise _EmitterError("edge_tree_invalid")
        if edge.dependent_index == roots[0]:
            raise _EmitterError("root_edge_invalid")
        _text(edge.label, f"edge_{index}_label", 64)
        edge_by_dependent[edge.dependent_index] = edge
    for token in tokens:
        if token.token_index == roots[0]:
            continue
        edge = edge_by_dependent.get(token.token_index)
        if edge is None or (edge.head_index, edge.label) != (token.head_index, token.dependency_label):
            raise _EmitterError("edge_token_mismatch")
    for token in tokens:
        seen: set[int] = set()
        current = token.token_index
        while current != -1:
            if current in seen:
                raise _EmitterError("dependency_cycle")
            seen.add(current)
            current = tokens[current].head_index

    cues = document.cues
    if (
        type(cues.clause_root_token) is not int
        or cues.clause_root_token < 0
        or cues.clause_root_token >= len(tokens)
    ):
        raise _EmitterError("clause_root_token_invalid")
    cue_spans: list[tuple[str, ParsedSpan | None]] = [
        ("subject", cues.subject),
        ("predicate", cues.predicate),
        ("numeric_value", cues.numeric_value),
        ("unit", cues.unit),
        ("target", cues.target),
        ("scope", cues.scope),
    ]
    if not isinstance(cues.modifiers, tuple) or len(cues.modifiers) > MAX_CUES:
        raise _EmitterError("modifiers_invalid")
    cue_spans.extend((f"modifier_{index}", span) for index, span in enumerate(cues.modifiers))
    for name, span in cue_spans:
        if span is not None:
            if not isinstance(span, ParsedSpan):
                raise _EmitterError(f"{name}_type_invalid")
            _validate_span_alignment(span, tokens, source_length, name)
            if span.start < clause.start or span.end > clause.end:
                raise _EmitterError(f"{name}_outside_clause")
    if [(span.start, span.end) for span in cues.modifiers] != sorted((span.start, span.end) for span in cues.modifiers):
        raise _EmitterError("modifier_order_invalid")

    markers = document.markers
    if not isinstance(markers, tuple) or len(markers) > MAX_MARKERS:
        raise _EmitterError("markers_invalid")
    marker_keys: list[tuple[int, int, str, tuple[int, ...]]] = []
    for index, marker in enumerate(markers):
        if not isinstance(marker, ParsedMarker):
            raise _EmitterError(f"marker_{index}_type_invalid")
        _text(marker.category, f"marker_{index}_category", 64)
        _validate_span_alignment(marker.span, tokens, source_length, f"marker_{index}_span")
        if marker.span.start < clause.start or marker.span.end > clause.end:
            raise _EmitterError(f"marker_{index}_outside_clause")
        if tuple(sorted(set(marker.token_indices))) != marker.token_indices:
            raise _EmitterError("marker_indices_invalid")
        for token_index in marker.token_indices:
            if type(token_index) is not int or token_index < 0 or token_index >= len(tokens):
                raise _EmitterError("marker_token_index_invalid")
        if marker.token_indices:
            if marker.span.token_start is None or marker.span.token_end is None:
                raise _EmitterError("marker_token_bounds_missing")
            if marker.span.token_start > marker.token_indices[0] or marker.span.token_end < marker.token_indices[-1] + 1:
                raise _EmitterError("marker_token_bounds_invalid")
        marker_keys.append((marker.span.start, marker.span.end, marker.category, marker.token_indices))
    if marker_keys != sorted(marker_keys):
        raise _EmitterError("marker_order_invalid")
    return _sha256_text(document.source)


def _candidate_hash(source_hash: str, candidate: CandidateLocator) -> str:
    del source_hash
    return _hash(candidate.candidate_hash, "candidate_hash")


def _payload_without_hash(document: ParsedDocument, candidate: CandidateLocator, source_hash: str) -> dict[str, object]:
    cues = document.cues
    return {
        "candidate_hash": _candidate_hash(source_hash, candidate),
        "clause_span": _span_payload(document.clause_span, document.source),
        "cues": {
            "clause_root_token": cues.clause_root_token,
            "modifiers": [_span_payload(span, document.source) for span in cues.modifiers],
            "numeric_value": _span_payload(cues.numeric_value, document.source),
            "predicate": _span_payload(cues.predicate, document.source) if cues.predicate else None,
            "scope": _span_payload(cues.scope, document.source) if cues.scope else None,
            "subject": _span_payload(cues.subject, document.source) if cues.subject else None,
            "target": _span_payload(cues.target, document.source) if cues.target else None,
            "unit": _span_payload(cues.unit, document.source) if cues.unit else None,
        },
        "edges": [
            {"dependent_index": edge.dependent_index, "head_index": edge.head_index, "label": edge.label}
            for edge in document.edges
        ],
        "evidence_version": EVIDENCE_VERSION,
        "markers": [
            {"category": marker.category, "span": _span_payload(marker.span, document.source), "token_indices": list(marker.token_indices)}
            for marker in document.markers
        ],
        "model_hash": document.metadata.model_hash,
        "parser_id": document.metadata.parser_id,
        "parser_version": document.metadata.parser_version,
        "pipeline_hash": document.metadata.pipeline_hash,
        "schema_version": SCHEMA_VERSION,
        "source_hash": source_hash,
        "source_length": len(document.source),
        "tokens": [
            {
                "dependency_label": token.dependency_label,
                "head_index": token.head_index,
                "lemma_sha256": _sha256_text(token.lemma),
                "pos_tag": token.pos_tag,
                "span": _span_payload(token.span, document.source),
                "token_index": token.token_index,
            }
            for token in document.tokens
        ],
    }


def canonical_evidence_json(evidence: dict[str, object]) -> str:
    """Serialize transport fields deterministically, excluding ``evidence_sha256``."""

    payload = {key: value for key, value in evidence.items() if key != "evidence_sha256"}
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def emit_dependency_evidence(document: object, candidate: object) -> EmissionResult:
    """Convert a parsed-document observation into serialized Menhir evidence or abstain."""

    try:
        if not isinstance(document, ParsedDocument) or not isinstance(candidate, CandidateLocator):
            raise _EmitterError("input_type_invalid")
        source_hash = _validate_document(document)
        _span_bounds(ParsedSpan(candidate.start, candidate.end), len(document.source), "candidate")
        if type(candidate.ordinal) is not int or candidate.ordinal < 0:
            raise _EmitterError("candidate_ordinal_invalid")
        if candidate.start < document.clause_span.start or candidate.end > document.clause_span.end:
            raise _EmitterError("candidate_outside_clause")
        if document.cues.numeric_value.start < candidate.start or document.cues.numeric_value.end > candidate.end:
            raise _EmitterError("numeric_cue_outside_candidate")
        payload = _payload_without_hash(document, candidate, source_hash)
        fingerprint = _sha256_text(canonical_evidence_json(payload))
        payload["evidence_sha256"] = fingerprint
        return EmissionResult("emitted", "evidence_emitted", payload, fingerprint)
    except (AttributeError, IndexError, KeyError, TypeError, ValueError) as error:
        reason = error.args[0] if isinstance(error, _EmitterError) and error.args else "malformed_parser_document"
        return EmissionResult("abstained", str(reason))


def _jsonable(value: object) -> object:
    """Normalize spaCy's config objects into deterministic JSON-safe metadata."""

    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    raise _EmitterError("parser_metadata_invalid")


def _config_options(config: object) -> tuple[dict[str, list[str]] | None, str | None]:
    if config is None:
        return {}, None
    if not isinstance(config, dict) or any(key not in _ALLOWED_SPACY_CONFIG for key in config):
        return None, "parser_config_invalid"
    normalized: dict[str, list[str]] = {}
    for key in _ALLOWED_SPACY_CONFIG:
        if key not in config:
            continue
        value = config[key]
        if not isinstance(value, (list, tuple)) or any(
            not isinstance(item, str) or not item.strip() or item != item.strip() for item in value
        ):
            return None, "parser_config_invalid"
        normalized[key] = list(value)
    return normalized, None


def _verify_model_artifact() -> tuple[bool, str]:
    """Require PEP 610 provenance for the exact official pinned model wheel."""

    try:
        model_distribution = distribution(PINNED_MODEL_NAME.replace("_", "-"))
    except PackageNotFoundError:
        return False, "spacy_model_unavailable"
    if model_distribution.version != PINNED_MODEL_VERSION:
        return False, "model_version_mismatch"
    try:
        direct_url_text = model_distribution.read_text("direct_url.json")
        if not isinstance(direct_url_text, str) or not direct_url_text:
            return False, "model_artifact_metadata_invalid"
        direct_url = json.loads(direct_url_text)
        archive_info = direct_url["archive_info"]
        hashes = archive_info["hashes"]
        if (
            direct_url["url"] != PINNED_MODEL_URL
            or archive_info["hash"] != f"sha256={PINNED_MODEL_HASH}"
            or hashes["sha256"] != PINNED_MODEL_HASH
        ):
            return False, "model_artifact_identity_mismatch"
    except (AttributeError, KeyError, OSError, TypeError, UnicodeError, ValueError, json.JSONDecodeError):
        return False, "model_artifact_metadata_invalid"
    return True, "model_artifact_verified"


def _pipeline_hash(
    spacy_version: str,
    model_name: str,
    model_version: str,
    model_hash: str,
    pipe_names: Sequence[str],
    config: Mapping[str, object],
    model_meta: Mapping[str, object],
) -> str:
    metadata = {
        "config": _jsonable(config),
        "model_hash": model_hash,
        "model_meta": _jsonable(model_meta),
        "model_name": model_name,
        "model_version": model_version,
        "pipeline": list(pipe_names),
        "spacy_version": spacy_version,
    }
    canonical = json.dumps(metadata, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return _sha256_text(canonical)


def _token_span(token: Any, source_offset: int, token_index: int) -> ParsedSpan:
    start = source_offset + int(token.idx)
    end = source_offset + int(token.idx + len(token.text))
    return ParsedSpan(start, end, token_index, token_index + 1)


def _nearest_predicate(token: Any) -> Any | None:
    current = token
    seen: set[int] = set()
    while current.i not in seen:
        seen.add(current.i)
        if current.pos_ in {"VERB", "AUX"}:
            return current
        head = current.head
        if head.i == current.i:
            break
        current = head
    return None


def _syntax_markers(doc: Any, source_offset: int, primary_numeric_index: int) -> tuple[ParsedMarker, ...]:
    markers: list[ParsedMarker] = []
    for token in doc:
        category: str | None = None
        if token.dep_ == "neg":
            category = "negation"
        elif token.tag_ == "MD":
            category = "modal_auxiliary"
        elif token.dep_ in {"cc", "conj"}:
            category = "coordination"
        elif token.pos_ == "NUM" and token.i != primary_numeric_index:
            category = "additional_numeric"
        elif token.dep_ in {"ccomp", "xcomp", "advcl", "acl", "relcl"}:
            category = "embedded_clause"
        elif token.morph.get("Tense") == ["Past"] or token.tag_ in {"VBD", "VBN"}:
            category = "past_morphology"
        if category is not None:
            span = _token_span(token, source_offset, token.i)
            markers.append(ParsedMarker(category, span, (token.i,)))
    markers.sort(key=lambda marker: (marker.span.start, marker.span.end, marker.category, marker.token_indices))
    return tuple(markers)


def _load_pinned_spacy(
    *, model_name: str, config: Mapping[str, object]
) -> tuple[Literal["ready", "unavailable", "error"], str, Any | None, str | None]:
    """Load exactly the pinned parser/model and return its verified pipeline hash."""

    try:
        import spacy  # type: ignore[import-not-found]
    except ImportError:
        return "unavailable", "spacy_not_installed", None, None
    if getattr(spacy, "__version__", None) != PINNED_SPACY_VERSION:
        return "unavailable", "spacy_version_mismatch", None, None
    if model_name != PINNED_MODEL_NAME:
        return "unavailable", "spacy_model_unavailable", None, None
    artifact_ok, artifact_reason = _verify_model_artifact()
    if not artifact_ok:
        return "unavailable", artifact_reason, None, None
    try:
        model_module = importlib.import_module(PINNED_MODEL_NAME)
    except ImportError:
        return "unavailable", "spacy_model_unavailable", None, None
    if getattr(model_module, "__version__", None) != PINNED_MODEL_VERSION:
        return "unavailable", "model_version_mismatch", None, None
    try:
        nlp = model_module.load(**dict(config))
    except (ImportError, OSError):
        return "unavailable", "spacy_model_unavailable", None, None
    except (AttributeError, KeyError, LookupError, RuntimeError, ValueError):
        return "error", "spacy_model_load_error", None, None
    try:
        model_meta = nlp.meta if isinstance(nlp.meta, Mapping) else {}
        if model_meta.get("version") != PINNED_MODEL_VERSION:
            return "unavailable", "model_version_mismatch", None, None
        if "parser" not in nlp.pipe_names or "tagger" not in nlp.pipe_names:
            return "error", "spacy_parser_component_missing", None, None
        actual_config = nlp.config.to_dict() if hasattr(nlp.config, "to_dict") else dict(nlp.config)
        pipeline_hash = _pipeline_hash(
            PINNED_SPACY_VERSION,
            PINNED_MODEL_NAME,
            PINNED_MODEL_VERSION,
            PINNED_MODEL_HASH,
            nlp.pipe_names,
            {"requested": dict(config), "loaded": actual_config},
            model_meta,
        )
    except (AttributeError, ImportError, KeyError, LookupError, TypeError, ValueError):
        return "error", "spacy_model_load_error", None, None
    return "ready", "model_loaded", nlp, pipeline_hash


def _parse_pinned_spacy(
    source: str,
    candidate: CandidateLocator,
    numeric_value: ParsedSpan,
    *,
    model_name: str,
    config: Mapping[str, object],
) -> ParserOutcome:
    """Load the pinned model and translate its syntax back to absolute source offsets."""

    load_status, load_reason, nlp, pipeline_hash = _load_pinned_spacy(model_name=model_name, config=config)
    if load_status != "ready" or nlp is None or pipeline_hash is None:
        return ParserOutcome(load_status if load_status != "ready" else "error", load_reason)
    try:
        parsed = nlp(source[candidate.start : candidate.end])
    except (AttributeError, ImportError, KeyError, LookupError, RuntimeError, TypeError, ValueError):
        return ParserOutcome("error", "spacy_parse_error")

    try:
        if not len(parsed):
            return ParserOutcome("error", "empty_candidate_parse")
        if len(parsed) > MAX_TOKENS:
            return ParserOutcome("error", "token_bound_exceeded")
        roots = [token for token in parsed if token.head.i == token.i]
        if len(roots) != 1:
            return ParserOutcome("error", "root_invariant_invalid")
        tokens: list[ParsedToken] = []
        for index, token in enumerate(parsed):
            if token.i != index or token.idx < 0 or token.idx + len(token.text) > candidate.end - candidate.start:
                return ParserOutcome("error", "token_offsets_invalid")
            span = _token_span(token, candidate.start, index)
            head_index = -1 if token.head.i == token.i else int(token.head.i)
            if head_index < -1 or head_index >= len(parsed):
                return ParserOutcome("error", "token_head_index_invalid")
            if not all(isinstance(value, str) and value.strip() for value in (token.dep_, token.pos_, token.lemma_)):
                return ParserOutcome("error", "token_metadata_invalid")
            tokens.append(ParsedToken(index, span, head_index, token.dep_, token.pos_, token.lemma_))
        token_tuple = tuple(tokens)
        edges = tuple(
            ParsedEdge(token.head.i, token.i, token.dep_)
            for token in parsed
            if token.head.i != token.i
        )
        if len(edges) > MAX_EDGES:
            return ParserOutcome("error", "edge_bound_exceeded")
        if tuple(edge.dependent_index for edge in edges) != tuple(range(len(parsed))):
            edges = tuple(sorted(edges, key=lambda edge: edge.dependent_index))
        numeric_matches = [
            token for token in parsed if candidate.start + token.idx == numeric_value.start and candidate.start + token.idx + len(token.text) == numeric_value.end
        ]
        if len(numeric_matches) != 1:
            return ParserOutcome("error", "numeric_span_token_alignment_invalid")
        numeric_token = numeric_matches[0]
        if numeric_token.pos_ != "NUM":
            return ParserOutcome("error", "numeric_span_not_numeric")
        numeric_span = _token_span(numeric_token, candidate.start, numeric_token.i)
        target_token = numeric_token.head if numeric_token.head.pos_ in {"NOUN", "PROPN"} else None
        target_span = _token_span(target_token, candidate.start, target_token.i) if target_token is not None else None
        predicate_token = _nearest_predicate(target_token or numeric_token)
        predicate_span = _token_span(predicate_token, candidate.start, predicate_token.i) if predicate_token is not None else None
        subject_token = None
        if predicate_token is not None:
            subjects = [child for child in predicate_token.children if child.dep_ in {"nsubj", "nsubjpass", "csubj"}]
            if subjects:
                subject_token = min(subjects, key=lambda child: child.i)
        subject_span = _token_span(subject_token, candidate.start, subject_token.i) if subject_token is not None else None
        markers = _syntax_markers(parsed, candidate.start, numeric_token.i)
        if len(markers) > MAX_MARKERS:
            return ParserOutcome("error", "marker_bound_exceeded")
        document = ParsedDocument(
            source=source,
            clause_span=ParsedSpan(candidate.start, candidate.end, 0, len(token_tuple)),
            tokens=token_tuple,
            edges=edges,
            cues=ParsedCue(
                subject=subject_span,
                predicate=predicate_span,
                numeric_value=numeric_span,
                unit=None,
                target=target_span,
                modifiers=(),
                scope=None,
                clause_root_token=roots[0].i,
            ),
            markers=markers,
            metadata=ParserMetadata("spacy", PINNED_SPACY_VERSION, PINNED_MODEL_HASH, pipeline_hash),
        )
        try:
            _validate_document(document)
        except (AttributeError, IndexError, KeyError, TypeError, ValueError) as error:
            reason = error.args[0] if isinstance(error, _EmitterError) and error.args else "parsed_document_invalid"
            return ParserOutcome("error", str(reason))
    except (AttributeError, IndexError, KeyError, TypeError, ValueError):
        return ParserOutcome("error", "spacy_protocol_conversion_error")
    return ParserOutcome("parsed", "document_parsed", document=document)


def parse_with_spacy(
    source: object,
    candidate: object = None,
    numeric_value: object = None,
    *,
    model_name: object = None,
    config: object = None,
) -> ParserOutcome:
    """Parse one caller-grounded candidate with the pinned offline spaCy model.

    The caller supplies absolute candidate and numeric spans; this function never searches the
    source for a candidate or decides whether the resulting syntax represents an operation.
    """

    if type(source) is not str:
        return ParserOutcome("error", "source_type_invalid")
    if not source or len(source) > MAX_SOURCE_LENGTH:
        return ParserOutcome("error", "source_length_invalid")
    if model_name is None or not isinstance(model_name, str) or not model_name.strip():
        return ParserOutcome("unavailable", "model_not_configured")
    config_options, config_error = _config_options(config)
    if config_error is not None or config_options is None:
        return ParserOutcome("error", config_error or "parser_config_invalid")
    # Preserve a typed unavailable result for unknown/uninstalled model names before requiring
    # candidate grounding; only the exact pinned model is eligible for the real adapter.
    if model_name != PINNED_MODEL_NAME:
        return ParserOutcome("unavailable", "spacy_model_unavailable")
    if not isinstance(candidate, CandidateLocator):
        return ParserOutcome("error", "candidate_not_configured")
    if not isinstance(numeric_value, ParsedSpan):
        return ParserOutcome("error", "numeric_value_not_configured")
    try:
        _span_bounds(numeric_value, len(source), "numeric_value")
        _span_bounds(ParsedSpan(candidate.start, candidate.end), len(source), "candidate")
        _hash(candidate.candidate_hash, "candidate_hash")
        if type(candidate.ordinal) is not int or candidate.ordinal < 0:
            raise _EmitterError("candidate_ordinal_invalid")
        if source[candidate.start : candidate.end].strip() != source[candidate.start : candidate.end]:
            raise _EmitterError("candidate_surface_invalid")
        if numeric_value.start < candidate.start or numeric_value.end > candidate.end:
            raise _EmitterError("numeric_value_outside_candidate")
    except (TypeError, ValueError, _EmitterError) as error:
        return ParserOutcome("error", error.args[0] if isinstance(error, _EmitterError) and error.args else "candidate_invalid")
    return _parse_pinned_spacy(source, candidate, numeric_value, model_name=model_name, config=config_options)


_EMBEDDED_DEPS = frozenset({"ccomp", "xcomp", "advcl", "acl", "relcl"})
_SUBJECT_DEPS = frozenset({"nsubj", "nsubjpass", "csubj"})


def _predicate_is_embedded(predicate: Any) -> bool:
    current = predicate
    seen: set[int] = set()
    while current.i not in seen:
        seen.add(current.i)
        if current is not predicate and current.dep_ in _EMBEDDED_DEPS:
            return True
        if current is not predicate and current.dep_ == "conj":
            current = current.head
            continue
        head = current.head
        if head.i == current.i:
            break
        if current is not predicate and current.dep_ in _EMBEDDED_DEPS:
            return True
        current = head
    return predicate.dep_ in _EMBEDDED_DEPS


def _discovery_clause_span(predicate: Any) -> tuple[int, int] | None:
    if predicate.dep_ == "conj":
        subtree = sorted(predicate.subtree, key=lambda token: token.i)
        while subtree and subtree[0].dep_ in {"cc", "punct"}:
            subtree.pop(0)
        if not subtree:
            return None
        return subtree[0].idx, subtree[-1].idx + len(subtree[-1].text)
    try:
        sentence = predicate.sent
        return sentence.start_char, sentence.end_char
    except (AttributeError, IndexError, TypeError, ValueError):
        return None


def discover_candidates_with_spacy(
    source: object,
    model_name: object = PINNED_MODEL_NAME,
    config: object = None,
) -> DiscoveryOutcome:
    """Discover bounded syntax locators without semantic admission or caller/gold spans."""

    if type(source) is not str:
        return DiscoveryOutcome("error", "source_type_invalid")
    if not source or len(source) > MAX_SOURCE_LENGTH:
        return DiscoveryOutcome("error", "source_length_invalid")
    if model_name is None or not isinstance(model_name, str) or not model_name.strip():
        return DiscoveryOutcome("unavailable", "model_not_configured")
    config_options, config_error = _config_options({} if config is None else config)
    if config_error is not None or config_options is None:
        return DiscoveryOutcome("error", config_error or "parser_config_invalid")
    if model_name != PINNED_MODEL_NAME:
        return DiscoveryOutcome("unavailable", "spacy_model_unavailable")
    load_status, load_reason, nlp, _pipeline_hash_value = _load_pinned_spacy(
        model_name=model_name, config=config_options
    )
    if load_status != "ready" or nlp is None:
        return DiscoveryOutcome(load_status if load_status != "ready" else "error", load_reason)
    try:
        doc = nlp(source)
        if len(doc) > MAX_TOKENS:
            return DiscoveryOutcome("error", "token_bound_exceeded")
    except (AttributeError, ImportError, KeyError, LookupError, RuntimeError, TypeError, ValueError):
        return DiscoveryOutcome("error", "spacy_parse_error")

    candidates: list[CandidateSpan] = []
    seen: set[tuple[int, ...]] = set()
    for numeric in doc:
        if numeric.pos_ != "NUM" or numeric.dep_ != "nummod":
            continue
        target = numeric.head
        if target.pos_ not in {"NOUN", "PROPN"}:
            continue
        predicate = _nearest_predicate(target)
        if predicate is None or _predicate_is_embedded(predicate):
            continue
        subjects = sorted((child for child in predicate.children if child.dep_ in _SUBJECT_DEPS), key=lambda token: token.i)
        if not subjects:
            continue
        if predicate.dep_ == "conj" and not any(child.dep_ in _SUBJECT_DEPS for child in predicate.children):
            continue
        clause = _discovery_clause_span(predicate)
        if clause is None:
            continue
        subject = subjects[0]
        item = CandidateSpan(
            clause_start=clause[0],
            clause_end=clause[1],
            numeric_start=numeric.idx,
            numeric_end=numeric.idx + len(numeric.text),
            subject_start=subject.idx,
            subject_end=subject.idx + len(subject.text),
            predicate_start=predicate.idx,
            predicate_end=predicate.idx + len(predicate.text),
            target_start=target.idx,
            target_end=target.idx + len(target.text),
        )
        key = (
            item.clause_start,
            item.clause_end,
            item.numeric_start,
            item.numeric_end,
            item.subject_start,
            item.subject_end,
            item.predicate_start,
            item.predicate_end,
            item.target_start,
            item.target_end,
        )
        if key not in seen:
            if len(candidates) >= MAX_DISCOVERED_CANDIDATES:
                return DiscoveryOutcome("error", "candidate_bound_exceeded")
            seen.add(key)
            candidates.append(item)
    candidates.sort(key=lambda item: (item.clause_start, item.numeric_start, item.predicate_start, item.target_start))
    return DiscoveryOutcome("discovered", "candidates_discovered", candidates=tuple(candidates))


__all__ = [
    "CandidateLocator",
    "CandidateSpan",
    "DiscoveryOutcome",
    "EmissionResult",
    "EVIDENCE_VERSION",
    "PINNED_MODEL_HASH",
    "PINNED_MODEL_NAME",
    "PINNED_MODEL_URL",
    "PINNED_MODEL_VERSION",
    "PINNED_SPACY_VERSION",
    "ParsedCue",
    "ParsedDocument",
    "ParsedEdge",
    "ParsedMarker",
    "ParsedSpan",
    "ParsedToken",
    "ParserMetadata",
    "ParserOutcome",
    "SCHEMA_VERSION",
    "canonical_evidence_json",
    "emit_dependency_evidence",
    "discover_candidates_with_spacy",
    "parse_with_spacy",
]
