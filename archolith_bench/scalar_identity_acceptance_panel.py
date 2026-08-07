"""Offline acceptance panel for the research-candidate → Menhir identity boundary.

Each source-labeled case supplies a raw research candidate and an exact claimed locator.  Bench
calls Menhir's real ``adapt_research_candidate`` adapter, then scores parse status and structural
composition independently.  No LLM, network, database, graph, or service call is made.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from archolith_bench.compositional_scalar_panel import PanelError, load_panel_menhir_api
from archolith_bench.deterministic_scalar_shadow import resolve_menhir_root


PANEL_SCHEMA_VERSION = 1
REPORT_SCHEMA_VERSION = 1
PROMOTION_STATUS = "not_evaluable"
_TOP_LEVEL_FIELDS = frozenset({"schema_version", "panel_id", "non_lme", "source_sha256", "episodes", "cases"})
_EPISODE_FIELDS = frozenset({"namespace", "uuid", "content"})
_CASE_FIELDS = frozenset({
    "case_id", "namespace", "episode_uuid", "span_start", "span_end", "span_sha256", "group_id",
    "perturbation_id", "split", "candidate", "expected",
})
_CANDIDATE_FIELDS = frozenset({
    "candidate_id", "subject", "attribute", "scope", "value_kind", "unit", "operation", "value",
    "stated_span", "episode_uuid", "span_start", "span_end",
})
_EXPECTED_FIELDS = frozenset({
    "role", "parse_status", "parse_reason", "composition_status", "composition_reason",
    "relation_type", "target",
})
_ID_CHARS = set("abcdefghijklmnopqrstuvwxyz0123456789._-")
_STATUSES = frozenset({"admitted", "rejected"})
_COMPOSITION_STATUSES = frozenset({"composed", "abstained", None})


@dataclass(frozen=True)
class PanelEpisode:
    namespace: str
    uuid: str
    content: str


@dataclass(frozen=True)
class PanelCase:
    case_id: str
    namespace: str
    episode_uuid: str
    span_start: int
    span_end: int
    span_sha256: str
    group_id: str
    perturbation_id: str
    split: str
    candidate: dict[str, Any]
    expected: dict[str, Any]


@dataclass(frozen=True)
class ScalarAcceptancePanel:
    path: Path
    file_sha256: str
    panel_id: str
    source_sha256: str
    episodes: tuple[PanelEpisode, ...]
    cases: tuple[PanelCase, ...]


def _error(context: str, message: str) -> PanelError:
    return PanelError(f"{context}: {message}")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _identifier(value: object, context: str) -> str:
    if not isinstance(value, str) or not value or value != value.lower():
        raise _error(context, "must be a canonical lowercase identifier")
    if any(char not in _ID_CHARS for char in value):
        raise _error(context, "must contain only lowercase identifier characters")
    if value.startswith("lme-") or "longmemeval" in value:
        raise _error(context, "must not contain benchmark-specific identifiers")
    return value


def _exact_fields(raw: object, expected: frozenset[str], context: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise _error(context, "must be an object")
    actual = set(raw)
    if actual != expected:
        raise _error(context, f"field mismatch; missing={sorted(expected - actual)}, unknown={sorted(actual - expected)}")
    return raw


def source_sha256(episodes: list[dict[str, str]]) -> str:
    canonical = sorted(episodes, key=lambda row: (row["namespace"], row["uuid"]))
    encoded = json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return _sha256_bytes(encoded)


def _validate_candidate(raw: object, case_context: str, episode: PanelEpisode, start: int, end: int) -> dict[str, Any]:
    candidate = _exact_fields(raw, _CANDIDATE_FIELDS, f"{case_context}.candidate")
    if candidate["candidate_id"] != case_context.rsplit(".", 1)[-1]:
        raise _error(f"{case_context}.candidate_id", "must equal case_id")
    for field in ("subject", "attribute", "scope", "value_kind", "unit", "operation", "stated_span", "episode_uuid"):
        if not isinstance(candidate[field], str):
            raise _error(f"{case_context}.candidate.{field}", "must be a string")
    if candidate["episode_uuid"] != episode.uuid:
        raise _error(f"{case_context}.candidate.episode_uuid", "must match case episode_uuid")
    if candidate["span_start"] != start or candidate["span_end"] != end:
        raise _error(f"{case_context}.candidate", "claimed locator must match case span")
    if candidate["stated_span"] != episode.content[start:end]:
        raise _error(f"{case_context}.candidate.stated_span", "must equal the case source span")
    return candidate


def _validate_expected(raw: object, context: str) -> dict[str, Any]:
    expected = _exact_fields(raw, _EXPECTED_FIELDS, context)
    if not isinstance(expected["role"], str) or not expected["role"] or expected["role"] != expected["role"].lower():
        raise _error(f"{context}.role", "must be a lowercase role identifier")
    if expected["parse_status"] not in _STATUSES:
        raise _error(f"{context}.parse_status", f"must be one of {sorted(_STATUSES)}")
    if expected["parse_reason"] is not None and not isinstance(expected["parse_reason"], str):
        raise _error(f"{context}.parse_reason", "must be null or a string")
    if expected["composition_status"] not in _COMPOSITION_STATUSES:
        raise _error(f"{context}.composition_status", "must be composed, abstained, or null")
    for field in ("composition_reason", "relation_type", "target"):
        if expected[field] is not None and not isinstance(expected[field], str):
            raise _error(f"{context}.{field}", "must be null or a string")
    if expected["composition_status"] == "composed":
        if expected["parse_status"] != "admitted" or expected["relation_type"] is None or expected["target"] is None:
            raise _error(context, "composed expectations require admitted parse, relation_type, and target")
    else:
        if expected["relation_type"] is not None or expected["target"] is not None:
            raise _error(context, "non-composed expectations must not claim relation_type or target")
    return expected


def load_panel(path: str | Path, *, api: Any) -> ScalarAcceptancePanel:
    resolved = Path(path).expanduser().resolve()
    context = f"panel {resolved}"
    if not resolved.is_file():
        raise _error(context, "file does not exist")
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise _error(context, f"could not read JSON: {exc}") from exc
    top = _exact_fields(payload, _TOP_LEVEL_FIELDS, context)
    if top["schema_version"] != PANEL_SCHEMA_VERSION:
        raise _error(context, f"schema_version must be {PANEL_SCHEMA_VERSION}")
    panel_id = _identifier(top["panel_id"], f"{context}.panel_id")
    if top["non_lme"] is not True:
        raise _error(context, "non_lme must be true")
    if not isinstance(top["source_sha256"], str) or len(top["source_sha256"]) != 64:
        raise _error(context, "source_sha256 must be a SHA-256")
    episodes: list[PanelEpisode] = []
    source_rows: list[dict[str, str]] = []
    by_key: dict[tuple[str, str], PanelEpisode] = {}
    uuids: set[str] = set()
    for index, raw in enumerate(top["episodes"]):
        item_context = f"{context}.episodes[{index}]"
        episode = _exact_fields(raw, _EPISODE_FIELDS, item_context)
        namespace = _identifier(episode["namespace"], f"{item_context}.namespace")
        uuid = _identifier(episode["uuid"], f"{item_context}.uuid")
        content = episode["content"]
        if not isinstance(content, str) or not content:
            raise _error(f"{item_context}.content", "must be a non-empty string")
        if uuid in uuids:
            raise _error(item_context, "episode uuid must be globally unique")
        value = PanelEpisode(namespace, uuid, content)
        episodes.append(value)
        source_rows.append({"namespace": namespace, "uuid": uuid, "content": content})
        by_key[(namespace, uuid)] = value
        uuids.add(uuid)
    actual_source_hash = source_sha256(source_rows)
    if top["source_sha256"] != actual_source_hash:
        raise _error(context, f"source_sha256 mismatch; expected {actual_source_hash}")

    cases: list[PanelCase] = []
    case_ids: set[str] = set()
    locators: set[tuple[str, str, int, int]] = set()
    group_splits: dict[str, str] = {}
    for index, raw in enumerate(top["cases"]):
        item_context = f"{context}.cases[{index}]"
        case = _exact_fields(raw, _CASE_FIELDS, item_context)
        case_id = _identifier(case["case_id"], f"{item_context}.case_id")
        namespace = _identifier(case["namespace"], f"{item_context}.namespace")
        episode_uuid = _identifier(case["episode_uuid"], f"{item_context}.episode_uuid")
        group_id = _identifier(case["group_id"], f"{item_context}.group_id")
        perturbation_id = _identifier(case["perturbation_id"], f"{item_context}.perturbation_id")
        split = case["split"]
        if split not in {"train", "holdout"}:
            raise _error(f"{item_context}.split", "must be train or holdout")
        if case_id in case_ids:
            raise _error(item_context, "duplicates case_id")
        case_ids.add(case_id)
        episode = by_key.get((namespace, episode_uuid))
        if episode is None:
            raise _error(item_context, "references unknown episode")
        start, end = case["span_start"], case["span_end"]
        if not isinstance(start, int) or isinstance(start, bool) or not isinstance(end, int) or isinstance(end, bool) or not 0 <= start < end <= len(episode.content):
            raise _error(item_context, "span_start/span_end must locate a non-empty source substring")
        locator = (namespace, episode_uuid, start, end)
        if locator in locators:
            raise _error(item_context, "duplicates a source locator")
        locators.add(locator)
        span = episode.content[start:end]
        if case["span_sha256"] != _sha256_bytes(span.encode("utf-8")):
            raise _error(item_context, "span_sha256 mismatch")
        previous_split = group_splits.setdefault(group_id, split)
        if previous_split != split:
            raise _error(item_context, "group_id leaks across splits")
        cases.append(
            PanelCase(
                case_id=case_id,
                namespace=namespace,
                episode_uuid=episode_uuid,
                span_start=start,
                span_end=end,
                span_sha256=case["span_sha256"],
                group_id=group_id,
                perturbation_id=perturbation_id,
                split=split,
                candidate=_validate_candidate(case["candidate"], case_id, episode, start, end),
                expected=_validate_expected(case["expected"], f"{item_context}.expected"),
            )
        )
    return ScalarAcceptancePanel(
        path=resolved,
        file_sha256=_sha256_bytes(resolved.read_bytes()),
        panel_id=panel_id,
        source_sha256=actual_source_hash,
        episodes=tuple(episodes),
        cases=tuple(cases),
    )


def _load_adapter(menhir_root: str | Path):
    root = resolve_menhir_root(menhir_root)
    source_root = str(root / "src")
    if source_root not in sys.path:
        sys.path.insert(0, source_root)
    try:
        module = importlib.import_module("menhir.services.research_scalar_adapter")
        return module.adapt_research_candidate, module.RESEARCH_ADAPTER_VERSION
    except (ImportError, AttributeError) as exc:
        raise PanelError(f"could not load Menhir research scalar adapter from {root}: {exc}") from exc


def analyze_panel(path: str | Path, *, menhir_root: str | Path, generated_at: str | None = None, api: Any | None = None) -> dict[str, Any]:
    loaded_api = api or load_panel_menhir_api(menhir_root)
    adapter, adapter_version = _load_adapter(menhir_root)
    panel = load_panel(path, api=loaded_api)
    episode_objects = [type("Episode", (), {"uuid": episode.uuid, "content": episode.content})() for episode in panel.episodes]
    rows: list[dict[str, Any]] = []
    counters: Counter[str] = Counter()
    role_counts: dict[str, Counter[str]] = defaultdict(Counter)
    for case in panel.cases:
        result = adapter(case.candidate, episode_objects, candidate_id=case.case_id)
        receipt = result.receipt
        actual_relation = actual_target = None
        if result.composition is not None and result.composition.identity is not None:
            actual_relation = result.composition.identity.relation_type
            actual_target = result.composition.identity.target_or_scope[0]
        actual = {
            "parse_status": receipt.parse_status,
            "parse_reason": receipt.parse_reason,
            "composition_status": receipt.composition_status,
            "composition_reason": receipt.composition_reason,
            "relation_type": actual_relation,
            "target": actual_target,
        }
        expected = case.expected
        dimensions = [field for field in _EXPECTED_FIELDS if field != "role" and actual[field] != expected[field]]
        correct = not dimensions
        row = {
            "case_id": case.case_id,
            "group_id": case.group_id,
            "perturbation_id": case.perturbation_id,
            "split": case.split,
            "role": expected["role"],
            "expected": {field: expected[field] for field in _EXPECTED_FIELDS if field != "role"},
            "actual": actual,
            "mismatch_dimensions": sorted(dimensions),
            "correct": correct,
        }
        rows.append(row)
        counters["total"] += 1
        counters["correct"] += int(correct)
        for field in ("parse_status", "composition_status", "composition_reason", "relation_type", "target"):
            counters[f"{field}_correct"] += int(actual[field] == expected[field])
        role_counts[expected["role"]]["total"] += 1
        role_counts[expected["role"]]["correct"] += int(correct)
    return {
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "promotion_status": PROMOTION_STATUS,
        "provenance": {
            "panel_id": panel.panel_id,
            "panel_sha256": panel.file_sha256,
            "source_sha256": panel.source_sha256,
            "generated_at": generated_at or datetime.now(timezone.utc).isoformat(),
            "llm_used": False,
            "research_adapter_version": adapter_version,
            "composer_version": loaded_api.composer_version,
        },
        "aggregate": {
            "total": counters["total"],
            "correct": counters["correct"],
            "all_correct": counters["correct"] == counters["total"],
            "parse_status_correct": counters["parse_status_correct"],
            "composition_status_correct": counters["composition_status_correct"],
            "composition_reason_correct": counters["composition_reason_correct"],
            "relation_type_correct": counters["relation_type_correct"],
            "target_correct": counters["target_correct"],
            "by_role": {role: dict(values) for role, values in sorted(role_counts.items())},
        },
        "cases": rows,
    }


def render_markdown(report: dict[str, Any]) -> str:
    aggregate = report["aggregate"]
    lines = [
        "# Scalar identity acceptance panel",
        "",
        "Offline, source-labeled research-adapter/composer evidence; promotion remains `not_evaluable`.",
        "",
        f"- Cases: {aggregate['total']}",
        f"- Correct: {aggregate['correct']}/{aggregate['total']}",
        "",
        "| Role | Correct | Total |",
        "| --- | ---: | ---: |",
    ]
    for role, values in aggregate["by_role"].items():
        lines.append(f"| `{role}` | {values['correct']} | {values['total']} |")
    lines.extend(["", "Source text and benchmark-task identifiers are not copied into the report.", ""])
    return "\n".join(lines)


def write_reports(report: dict[str, Any], json_out: str | Path, markdown_out: str | Path) -> None:
    json_path = Path(json_out).expanduser().resolve()
    markdown_path = Path(markdown_out).expanduser().resolve()
    if json_path == markdown_path:
        raise PanelError("JSON and Markdown outputs must use different paths")
    if json_path.exists() or markdown_path.exists():
        raise PanelError("refusing to overwrite existing report output")
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(render_markdown(report), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate the scalar identity acceptance panel.")
    parser.add_argument("panel")
    parser.add_argument("--menhir-root", required=True)
    parser.add_argument("--json-out", required=True)
    parser.add_argument("--markdown-out", required=True)
    args = parser.parse_args(argv)
    try:
        report = analyze_panel(args.panel, menhir_root=args.menhir_root)
        write_reports(report, args.json_out, args.markdown_out)
    except PanelError as exc:
        parser.error(str(exc))
    return 0


__all__ = ["ScalarAcceptancePanel", "analyze_panel", "load_panel", "main", "render_markdown", "source_sha256", "write_reports"]
