"""Compact offline probe of Menhir's real event-history perception -> selection path.

This is a NONCANONICAL, no-persistence Bench probe.  For each sample it runs Menhir's real
``extract_events_once`` (with a caller-supplied ``llm_complete``), overrides each proposal's
domain to the case lane domain so that query/domain routing is isolated (recorded as NOT
MEASURED), builds typed event assertions, projects them through the real
``EventHistoryService.rebuild_lane`` using an in-memory source/sink, and selects the latest or
predecessor assertion through the real ``select_event_assertion``.

Query routing, production authority, repository persistence, and public recall are explicitly
unmeasured and disabled in this slice.  No benchmark IDs or source answers are embedded here; the
core consumes generic synthetic episodes and canned LLM output only.
"""

from __future__ import annotations

import importlib
import json
import sys
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

from archolith_bench.deterministic_scalar_shadow import (
    CaptureError,
    _validate_menhir_import_identity,
    resolve_menhir_root,
)

REPORT_SCHEMA_VERSION = 1
PROMOTION_STATUS = "not_evaluable"
PERCEIVER_VERSION = "v1"
EVENT_HISTORY_PREDICATE = "acquired"
LLM_COMPLETE = Callable[..., str]

_INTENTS = frozenset({"latest", "predecessor"})
_STATUSES = frozenset({"unique", "none", "ambiguous"})


class EventHistoryProbeError(RuntimeError):
    """Raised when the event-history probe cannot run safely."""


@dataclass(frozen=True)
class ExperimentEpisode:
    uuid: str
    content: str
    reference_time: str | None
    turn_evidence_uuid: str


@dataclass(frozen=True)
class ExperimentCase:
    case_id: str
    namespace: str
    subject_uuid: str
    episodes: tuple[ExperimentEpisode, ...]
    intent: str
    expected_status: str
    expected_object_key: str | None = None
    anchor_object_key: str | None = None
    lane_domain: str | None = None
    safety_control: bool = False


@dataclass(frozen=True)
class ProbeEventHistoryApi:
    extract_events_once: Callable[..., list[Any]]
    build_event_assertion: Callable[..., Any]
    select_event_assertion: Callable[..., Any]
    event_lane_type: type
    selection_intent_type: type
    event_history_service_type: type
    perceiver_version: str = PERCEIVER_VERSION


def _error(context: str, message: str) -> EventHistoryProbeError:
    return EventHistoryProbeError(f"{context}: {message}")


def _normalize_object_key(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip().lower()
    return value


def _status_value(result: Any) -> str:
    status = getattr(result, "status", None)
    if status is None:
        return "not_measured"
    if isinstance(status, str):
        return status
    value = getattr(status, "value", None)
    return value if isinstance(value, str) else str(status).lower()


def _field_value(record: Any, *names: str, default: Any = None) -> Any:
    if isinstance(record, dict):
        for name in names:
            if name in record:
                return record[name]
        return default
    for name in names:
        if hasattr(record, name):
            return getattr(record, name)
    return default


def _normalize_blank(value: Any) -> Any:
    if value is None or (isinstance(value, str) and not value.strip()):
        return ""
    if isinstance(value, str):
        return value.strip()
    return value


def _assertion_fields(assertion: Any) -> dict[str, Any]:
    return {
        "assertion_key": _field_value(assertion, "assertion_key", "key", "assertion_id"),
        "object_key": _field_value(assertion, "object_key", "target", "object"),
        "quote": _field_value(assertion, "quote", "stated_span", "display", "text"),
        "when": _field_value(assertion, "when", "valid_at", "effective_time", "reference_time"),
        "time_basis": _field_value(assertion, "time_basis", "time_basis_kind"),
        "materializable": _field_value(assertion, "materializable", default=True),
    }


def load_menhir_event_history_api(menhir_root: str | Path) -> ProbeEventHistoryApi:
    """Load the selected Menhir checkout's real event-history contracts, failing loudly."""
    try:
        root = resolve_menhir_root(menhir_root)
    except CaptureError as exc:
        raise EventHistoryProbeError(str(exc)) from exc
    source_root = str(root / "src")
    if source_root not in sys.path:
        sys.path.insert(0, source_root)
    try:
        perception = importlib.import_module("menhir.services.event_history_perception")
        domain = importlib.import_module("menhir.domain.event_history")
        service = importlib.import_module("menhir.services.event_history_service")
        _validate_menhir_import_identity(root, (perception, domain, service))
        return ProbeEventHistoryApi(
            extract_events_once=perception.extract_events_once,
            build_event_assertion=perception.build_event_assertion,
            select_event_assertion=domain.select_event_assertion,
            event_lane_type=domain.EventLane,
            selection_intent_type=domain.EventSelectionIntent,
            event_history_service_type=service.EventHistoryService,
        )
    except (ImportError, AttributeError) as exc:
        raise EventHistoryProbeError(
            f"could not load the required Menhir event-history APIs from {root}: {exc}"
        ) from exc


class _InMemorySource:
    """In-memory assertion source that satisfies Menhir's source contract."""

    def __init__(self, assertions: list[Any]) -> None:
        self._assertions = list(assertions)

    def assertions_for_lane(
        self,
        lane: Any,
        *,
        include_superseded: bool = False,
        materializable_only: bool = True,
    ) -> list[Any]:
        subject = _normalize_blank(_field_value(lane, "subject_uuid"))
        namespace = _normalize_blank(_field_value(lane, "namespace"))
        predicate = _normalize_blank(_field_value(lane, "predicate"))
        domain = _normalize_blank(_field_value(lane, "domain"))
        matches = []
        for assertion in self._assertions:
            if subject and _normalize_blank(_field_value(assertion, "subject_uuid")) != subject:
                continue
            if namespace and _normalize_blank(_field_value(assertion, "namespace")) != namespace:
                continue
            if predicate and _normalize_blank(_field_value(assertion, "predicate")) != predicate:
                continue
            if domain and _normalize_blank(_field_value(assertion, "domain")) != domain:
                continue
            if materializable_only and not _field_value(assertion, "materializable", default=True):
                continue
            matches.append(assertion)
        return matches


class _InMemorySink:
    """In-memory event-timeline sink that captures drawn entries for the probe."""

    def __init__(self) -> None:
        self._views: dict[str, dict[str, Any]] = {}
        self._drawn: dict[str, list[Any]] = {}
        self._next_view = 0

    def record_event_timeline(self, **kwargs: Any) -> dict[str, str]:
        self._next_view += 1
        view_uuid = f"view-{self._next_view}"
        view_key = str(kwargs.get("view_key") or view_uuid)
        self._views[view_uuid] = {"uuid": view_uuid, "view_key": view_key, **kwargs}
        return {"uuid": view_uuid, "view_key": view_key}

    def draw_event_timeline_entries(self, view_uuid: str, entries: list[Any]) -> dict[str, int]:
        self._drawn[view_uuid] = list(entries)
        return {"drawn": len(entries), "expected": len(entries)}

    def list_event_timeline_views(self, subject_uuid: str, namespace: str) -> list[dict[str, Any]]:
        return [
            view
            for view in self._views.values()
            if view.get("subject_uuid") == subject_uuid and view.get("namespace") == namespace
        ]

    def retire_event_timeline(self, view_key: str) -> bool:
        for view_uuid, view in list(self._views.items()):
            if view.get("view_key") == view_key:
                self._views.pop(view_uuid, None)
                self._drawn.pop(view_uuid, None)
                return True
        return False

    def latest_drawn(self) -> list[Any]:
        if not self._drawn:
            return []
        latest_uuid = max(self._drawn)
        return self._drawn.get(latest_uuid, [])


def _entry_record(entry: Any) -> dict[str, Any]:
    return {
        "object_key": _field_value(entry, "object_key", "target", "object"),
        "quote": _field_value(entry, "quote", "stated_span", "display", "text"),
        "when": _field_value(entry, "when", "valid_at", "effective_time"),
        "time_basis": _field_value(entry, "time_basis"),
    }


def _build_assertions(
    api: ProbeEventHistoryApi,
    case: ExperimentCase,
    proposals: list[Any],
    learned_at: str,
) -> tuple[list[Any], list[dict[str, Any]]]:
    episodes_by_uuid = {episode.uuid: episode for episode in case.episodes}
    assertions: list[Any] = []
    receipts: list[dict[str, Any]] = []
    for proposal in proposals:
        episode_uuid = _field_value(proposal, "episode_uuid", "episode_id")
        episode = episodes_by_uuid.get(episode_uuid)
        if episode is None:
            receipts.append({"built": False, "reason": "unknown_episode", "object_key": None})
            continue
        overridden = replace(proposal, domain=case.lane_domain)
        try:
            result = api.build_event_assertion(
                overridden,
                subject_uuid=case.subject_uuid,
                namespace=case.namespace,
                learned_at=learned_at,
                episode_reference_time=episode.reference_time,
                turn_evidence_uuid=episode.turn_evidence_uuid,
                perceiver_version=api.perceiver_version,
            )
        except Exception as exc:  # noqa: BLE001 - surface build failures as drops
            receipts.append({"built": False, "reason": f"build_error:{type(exc).__name__}", "object_key": None})
            continue
        built = bool(getattr(result, "built", False))
        reason = getattr(result, "reason", None)
        assertion = getattr(result, "assertion", None)
        if not built or assertion is None:
            receipts.append({"built": False, "reason": reason or "not_built", "object_key": None})
            continue
        assertions.append(assertion)
        fields = _assertion_fields(assertion)
        receipts.append(
            {
                "built": True,
                "reason": reason,
                "object_key": fields["object_key"],
                "quote": fields["quote"],
                "when": fields["when"],
                "time_basis": fields["time_basis"],
            }
        )
    return assertions, receipts


def _resolve_predecessor_anchor(
    assertions: list[Any], anchor_object_key: Any
) -> dict[str, Any]:
    """Resolve the predecessor anchor by exact normalized object key; fail closed otherwise."""
    if anchor_object_key is None:
        return {"status": "not_applicable", "anchor_assertion_key": None, "reason": None}
    normalized = _normalize_object_key(anchor_object_key)
    matches: list[str] = []
    for assertion in assertions:
        if _normalize_object_key(_field_value(assertion, "object_key")) == normalized:
            key = _field_value(assertion, "assertion_key") or str(
                _field_value(assertion, "object_key")
            )
            if key not in matches:
                matches.append(key)
    if len(matches) == 1:
        return {"status": "resolved", "anchor_assertion_key": matches[0], "reason": None}
    if not matches:
        return {"status": "no_anchor", "anchor_assertion_key": None, "reason": "no_matching_anchor"}
    return {
        "status": "ambiguous_anchor",
        "anchor_assertion_key": None,
        "reason": "multiple_distinct_anchor_keys",
    }


def _projection_complete(projection: Any, sink: _InMemorySink) -> bool:
    """Return True only when the projection finished; a complete empty lane is valid."""
    return bool(_field_value(projection, "complete", default=False))


def _selection_record(
    api: ProbeEventHistoryApi,
    lane: Any,
    case: ExperimentCase,
    assertions: list[Any],
) -> dict[str, Any]:
    intent_attr = "LATEST" if case.intent == "latest" else "PREDECESSOR"
    intent = getattr(api.selection_intent_type, intent_attr)
    anchor = _resolve_predecessor_anchor(assertions, case.anchor_object_key)
    if case.intent == "predecessor" and anchor["status"] != "resolved":
        return {
            "status": "none",
            "gate": "predecessor_anchor",
            "reason": anchor["reason"] or anchor["status"],
            "has_unique_selection": False,
            "selected": None,
            "anchor": anchor,
        }
    try:
        result = api.select_event_assertion(
            assertions,
            lane=lane,
            intent=intent,
            as_of=None,
            anchor_time=None,
            anchor_assertion_key=anchor.get("anchor_assertion_key"),
        )
    except Exception as exc:  # noqa: BLE001 - fail closed on selection errors
        return {
            "status": "selection_error",
            "gate": None,
            "reason": f"select_error:{type(exc).__name__}",
            "has_unique_selection": False,
            "selected": None,
            "anchor": anchor,
        }
    selected = getattr(result, "selected", None)
    selected_record = None
    if selected is not None:
        fields = _assertion_fields(selected)
        selected_record = {
            "object_key": fields["object_key"],
            "quote": fields["quote"],
            "when": fields["when"],
            "time_basis": fields["time_basis"],
        }
    return {
        "status": _status_value(result),
        "gate": getattr(result, "gate", None),
        "reason": getattr(result, "reason", None),
        "has_unique_selection": bool(getattr(result, "has_unique_selection", False)),
        "selected": selected_record,
        "anchor": anchor,
    }


def _sample_correct(
    case: ExperimentCase, selection: dict[str, Any]
) -> bool:
    expected = case.expected_status
    status = selection["status"]
    if expected == "unique":
        if status != "unique" or selection["selected"] is None:
            return False
        actual = selection["selected"]["object_key"]
        return _normalize_object_key(actual) == _normalize_object_key(case.expected_object_key)
    if expected == "none":
        return status == "none"
    if expected == "ambiguous":
        return status == "ambiguous"
    return False


def _default_learned_at(generated_at: str | None) -> str:
    if generated_at:
        return generated_at
    return datetime.now(timezone.utc).isoformat()


def analyze_case(
    case: ExperimentCase,
    menhir_root: str | Path,
    llm_complete: LLM_COMPLETE,
    samples: int = 3,
    required_votes: int = 2,
    generated_at: str | None = None,
    api: ProbeEventHistoryApi | None = None,
) -> dict[str, Any]:
    if case.intent not in _INTENTS:
        raise _error(f"case {case.case_id}.intent", f"must be one of {sorted(_INTENTS)}")
    if case.expected_status not in _STATUSES:
        raise _error(f"case {case.case_id}.expected_status", f"must be one of {sorted(_STATUSES)}")
    if case.expected_status == "unique" and not case.expected_object_key:
        raise _error(f"case {case.case_id}", "unique cases require expected_object_key")
    if case.intent == "predecessor" and not case.anchor_object_key:
        raise _error(f"case {case.case_id}", "predecessor cases require anchor_object_key")
    if samples < 1 or required_votes < 1 or required_votes > samples:
        raise _error(f"case {case.case_id}", "required votes must be within [1, samples]")

    loaded_api = api or load_menhir_event_history_api(menhir_root)
    learned_at = _default_learned_at(generated_at)
    lane = loaded_api.event_lane_type(
        subject_uuid=case.subject_uuid,
        predicate=EVENT_HISTORY_PREDICATE,
        namespace=case.namespace,
        domain=case.lane_domain,
    )
    episode_objects = [
        SimpleNamespace(
            uuid=episode.uuid,
            content=episode.content,
            reference_time=episode.reference_time,
            turn_evidence_uuid=episode.turn_evidence_uuid,
        )
        for episode in case.episodes
    ]

    sample_rows: list[dict[str, Any]] = []
    correct_votes = 0
    wrong_unique: list[int] = []
    abstentions = 0
    for sample_index in range(samples):
        parser_drops: list[str] = []
        try:
            proposals = list(
                loaded_api.extract_events_once(
                    episode_objects, llm_complete, on_drop=parser_drops.append
                )
            )
        except Exception as exc:  # noqa: BLE001 - surface extraction failures as drops
            proposal_rows: list[dict[str, Any]] = []
            build_receipts: list[dict[str, Any]] = []
            drop_reasons = [f"extract_error:{type(exc).__name__}"]
            assertions: list[Any] = []
        else:
            proposal_rows = [
                {
                    "domain_override_applied": True,
                    "domain": case.lane_domain,
                    "episode_uuid": _field_value(proposal, "episode_uuid", "episode_id"),
                    "object_key": _field_value(proposal, "object_key", "target"),
                    "display": _field_value(proposal, "display", "stated_span"),
                }
                for proposal in proposals
            ]
            assertions, build_receipts = _build_assertions(
                loaded_api, case, proposals, learned_at
            )
            build_drops = [
                receipt["reason"]
                for receipt in build_receipts
                if not receipt["built"] and receipt["reason"]
            ]
            drop_reasons = list(parser_drops) + build_drops

        source = _InMemorySource(assertions)
        sink = _InMemorySink()
        service = loaded_api.event_history_service_type(source, sink)
        try:
            projection = service.rebuild_lane(lane)
        except Exception as exc:  # noqa: BLE001 - fail closed on projection errors
            projection = None
            projection_error = f"rebuild_error:{type(exc).__name__}"
        else:
            projection_error = None
        timeline = [_entry_record(entry) for entry in sink.latest_drawn()]
        projection_complete = projection_error is None and _projection_complete(projection, sink)
        selection = _selection_record(loaded_api, lane, case, assertions)
        if not projection_complete:
            selection = {
                **selection,
                "status": "none",
                "has_unique_selection": False,
                "gate": "projection",
                "reason": projection_error or "projection_incomplete",
                "selected": None,
            }
        correct = _sample_correct(case, selection) and projection_complete
        correct_votes += int(correct)
        if selection["has_unique_selection"] and not correct:
            wrong_unique.append(sample_index)
        if not selection["has_unique_selection"]:
            abstentions += 1
        sample_rows.append(
            {
                "sample_index": sample_index,
                "proposals": proposal_rows,
                "build_receipts": build_receipts,
                "drop_reasons": drop_reasons,
                "projection": {
                    "result": _jsonable(projection),
                    "complete": projection_complete,
                    "error": projection_error,
                    "timeline_entries": timeline,
                },
                "selection": selection,
                "correct": correct,
            }
        )

    safety_violation = False
    if case.safety_control and case.expected_status in {"none", "ambiguous"}:
        safety_violation = any(not row["correct"] and row["selection"]["has_unique_selection"] for row in sample_rows)
    passed = correct_votes >= required_votes and not safety_violation

    return {
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "promotion_status": PROMOTION_STATUS,
        "canonical": False,
        "production_authority_enabled": False,
        "persistence_used": False,
        "query_routing_measured": False,
        "llm_used": True,
        "case_id": case.case_id,
        "generated_at": generated_at,
        "learned_at": learned_at,
        "perceiver_version": loaded_api.perceiver_version,
        "samples": sample_rows,
        "aggregate": {
            "total_samples": samples,
            "correct_votes": correct_votes,
            "required_votes": required_votes,
            "passed": passed,
            "safety_control": case.safety_control,
            "safety_violation": safety_violation,
            "wrong_unique_samples": wrong_unique,
            "abstentions": abstentions,
            "domain_override": {"applied": True, "lane_domain": case.lane_domain},
        },
    }


def _jsonable(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    value = getattr(value, "value", None)
    return value if isinstance(value, (str, int, float, bool)) or value is None else str(value)


def summarize_report(report: dict[str, Any]) -> str:
    """Render a compact source-free textual summary of one probe case."""
    aggregate = report["aggregate"]
    lines = [
        f"Case: {report['case_id']}",
        f"Promotion: {report['promotion_status']}",
        f"Pass: {aggregate['passed']} (votes {aggregate['correct_votes']}/{aggregate['required_votes']})",
        f"Abstentions: {aggregate['abstentions']}",
        f"Wrong unique samples: {aggregate['wrong_unique_samples']}",
        f"Safety: control={aggregate['safety_control']} violation={aggregate['safety_violation']}",
        "Flags: "
        + ", ".join(
            f"{flag}={report[flag]}"
            for flag in (
                "canonical",
                "production_authority_enabled",
                "persistence_used",
                "query_routing_measured",
                "llm_used",
            )
        ),
    ]
    return "\n".join(lines) + "\n"


def encode_case(case: ExperimentCase) -> str:
    return json.dumps(
        {
            "case_id": case.case_id,
            "namespace": case.namespace,
            "subject_uuid": case.subject_uuid,
            "episodes": [
                {
                    "uuid": episode.uuid,
                    "content": episode.content,
                    "reference_time": episode.reference_time,
                    "turn_evidence_uuid": episode.turn_evidence_uuid,
                }
                for episode in case.episodes
            ],
            "intent": case.intent,
            "expected_status": case.expected_status,
            "expected_object_key": case.expected_object_key,
            "anchor_object_key": case.anchor_object_key,
            "lane_domain": case.lane_domain,
            "safety_control": case.safety_control,
        },
        sort_keys=True,
        ensure_ascii=False,
    )


__all__ = [
    "ExperimentCase",
    "ExperimentEpisode",
    "EventHistoryProbeError",
    "ProbeEventHistoryApi",
    "analyze_case",
    "encode_case",
    "load_menhir_event_history_api",
    "summarize_report",
]
