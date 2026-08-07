"""Offline noisy conversational scalar acceptance panel.

The fixture pairs clean and noisy generic utterances.  Each row is still evaluated at Menhir's
research-adapter/composer boundary, but Bench reports clean/noisy slices, paired invariance, and
false-current-state admissions separately.  This is descriptive evidence only.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from archolith_bench.compositional_scalar_panel import PanelError, load_panel_menhir_api
from archolith_bench.scalar_identity_acceptance_panel import (
    _CANDIDATE_FIELDS,
    _load_adapter,
    _sha256_bytes,
)


PANEL_SCHEMA_VERSION = 1
REPORT_SCHEMA_VERSION = 1
PROMOTION_STATUS = "not_evaluable"
_TOP_FIELDS = frozenset({"schema_version", "panel_id", "non_lme", "source_sha256", "episodes", "cases"})
_EPISODE_FIELDS = frozenset({"namespace", "uuid", "content"})
_CASE_FIELDS = frozenset({
    "case_id", "namespace", "episode_uuid", "span_start", "span_end", "span_sha256", "group_id",
    "perturbation_id", "split", "slice", "pair_id", "candidate", "expected",
})
_EXPECTED_FIELDS = frozenset({
    "role", "parse_status", "parse_reason", "composition_status", "composition_reason", "relation_type",
    "target", "operation", "value", "paired_invariant", "false_current",
})
_ID_CHARS = set("abcdefghijklmnopqrstuvwxyz0123456789._-")


def _error(context: str, message: str) -> PanelError:
    return PanelError(f"{context}: {message}")


def _exact_fields(raw: object, expected: frozenset[str], context: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise _error(context, "must be an object")
    actual = set(raw)
    if actual != expected:
        raise _error(context, f"field mismatch; missing={sorted(expected - actual)}, unknown={sorted(actual - expected)}")
    return raw


def _identifier(value: object, context: str) -> str:
    if not isinstance(value, str) or not value or value != value.lower() or any(c not in _ID_CHARS for c in value):
        raise _error(context, "must be a canonical lowercase identifier")
    if value.startswith("lme-") or "longmemeval" in value:
        raise _error(context, "must not contain benchmark-specific identifiers")
    return value


def source_sha256(episodes: list[dict[str, str]]) -> str:
    canonical = sorted(episodes, key=lambda row: (row["namespace"], row["uuid"]))
    encoded = json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return _sha256_bytes(encoded)


def _parse_expected(raw: object, context: str) -> dict[str, Any]:
    expected = _exact_fields(raw, _EXPECTED_FIELDS, context)
    if not isinstance(expected["role"], str) or not expected["role"]:
        raise _error(f"{context}.role", "must be a non-empty role")
    if expected["parse_status"] not in {"admitted", "rejected"}:
        raise _error(f"{context}.parse_status", "must be admitted or rejected")
    if expected["composition_status"] not in {None, "composed", "abstained"}:
        raise _error(f"{context}.composition_status", "must be null, composed, or abstained")
    for field in ("parse_reason", "composition_reason", "relation_type", "target", "operation", "value"):
        if expected[field] is not None and not isinstance(expected[field], (str, int, float)):
            raise _error(f"{context}.{field}", "must be null, string, or number")
    if not isinstance(expected["paired_invariant"], bool) or not isinstance(expected["false_current"], bool):
        raise _error(context, "paired_invariant and false_current must be boolean")
    if expected["composition_status"] == "composed":
        if any(expected[field] is None for field in ("relation_type", "target", "operation", "value")):
            raise _error(context, "composed expectations require relation, target, operation, and value")
    elif any(expected[field] is not None for field in ("relation_type", "target", "operation", "value")):
        raise _error(context, "non-composed expectations must not claim identity fields")
    return expected


def load_panel(path: str | Path) -> dict[str, Any]:
    resolved = Path(path).expanduser().resolve()
    context = f"panel {resolved}"
    if not resolved.is_file():
        raise _error(context, "file does not exist")
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise _error(context, f"could not read JSON: {exc}") from exc
    top = _exact_fields(payload, _TOP_FIELDS, context)
    if top["schema_version"] != PANEL_SCHEMA_VERSION or top["non_lme"] is not True:
        raise _error(context, "invalid schema_version/non_lme")
    panel_id = _identifier(top["panel_id"], f"{context}.panel_id")
    episodes = []
    by_key: dict[tuple[str, str], dict[str, str]] = {}
    uuids: set[str] = set()
    for index, raw in enumerate(top["episodes"]):
        item = _exact_fields(raw, _EPISODE_FIELDS, f"{context}.episodes[{index}]")
        namespace = _identifier(item["namespace"], f"{context}.episodes[{index}].namespace")
        uuid = _identifier(item["uuid"], f"{context}.episodes[{index}].uuid")
        if uuid in uuids or not isinstance(item["content"], str) or not item["content"]:
            raise _error(context, "episode UUIDs must be unique and content non-empty")
        value = {"namespace": namespace, "uuid": uuid, "content": item["content"]}
        episodes.append(value)
        by_key[(namespace, uuid)] = value
        uuids.add(uuid)
    actual_source = source_sha256(episodes)
    if top["source_sha256"] != actual_source:
        raise _error(context, f"source_sha256 mismatch; expected {actual_source}")
    cases = []
    seen_cases: set[str] = set()
    seen_locators: set[tuple[str, str, int, int]] = set()
    pair_slices: dict[str, set[str]] = defaultdict(set)
    pair_invariance: dict[str, bool] = {}
    for index, raw in enumerate(top["cases"]):
        item_context = f"{context}.cases[{index}]"
        case = _exact_fields(raw, _CASE_FIELDS, item_context)
        case_id = _identifier(case["case_id"], f"{item_context}.case_id")
        namespace = _identifier(case["namespace"], f"{item_context}.namespace")
        episode_uuid = _identifier(case["episode_uuid"], f"{item_context}.episode_uuid")
        group_id = _identifier(case["group_id"], f"{item_context}.group_id")
        perturbation_id = _identifier(case["perturbation_id"], f"{item_context}.perturbation_id")
        pair_id = _identifier(case["pair_id"], f"{item_context}.pair_id")
        if case["slice"] not in {"clean", "noisy"} or case["split"] not in {"train", "holdout"}:
            raise _error(item_context, "slice must be clean/noisy and split train/holdout")
        if case_id in seen_cases:
            raise _error(item_context, "duplicate case_id")
        seen_cases.add(case_id)
        episode = by_key.get((namespace, episode_uuid))
        if episode is None:
            raise _error(item_context, "unknown episode")
        start, end = case["span_start"], case["span_end"]
        if not isinstance(start, int) or not isinstance(end, int) or not 0 <= start < end <= len(episode["content"]):
            raise _error(item_context, "invalid source offsets")
        locator = (namespace, episode_uuid, start, end)
        if locator in seen_locators:
            raise _error(item_context, "duplicate source locator")
        seen_locators.add(locator)
        span = episode["content"][start:end]
        if case["span_sha256"] != _sha256_bytes(span.encode("utf-8")):
            raise _error(item_context, "span_sha256 mismatch")
        candidate = _exact_fields(case["candidate"], _CANDIDATE_FIELDS, f"{item_context}.candidate")
        if candidate["candidate_id"] != case_id or candidate["episode_uuid"] != episode_uuid or candidate["span_start"] != start or candidate["span_end"] != end or candidate["stated_span"] != span:
            raise _error(item_context, "candidate locator/span does not match case")
        expected = _parse_expected(case["expected"], f"{item_context}.expected")
        pair_slices[pair_id].add(case["slice"])
        previous = pair_invariance.setdefault(pair_id, expected["paired_invariant"])
        if previous != expected["paired_invariant"]:
            raise _error(item_context, "paired_invariant must be consistent within pair")
        cases.append({**case, "case_id": case_id, "group_id": group_id, "perturbation_id": perturbation_id, "pair_id": pair_id, "candidate": candidate, "expected": expected})
    if any(slices != {"clean", "noisy"} for slices in pair_slices.values()):
        raise _error(context, "every pair_id must have one clean and one noisy case")
    return {"path": resolved, "file_sha256": _sha256_bytes(resolved.read_bytes()), "panel_id": panel_id, "source_sha256": actual_source, "episodes": episodes, "cases": cases}


def _actual(result: Any) -> dict[str, Any]:
    receipt = result.receipt
    relation = target = operation = value = None
    if result.composition is not None and result.composition.identity is not None:
        identity = result.composition.identity
        relation = identity.relation_type
        target = identity.target_or_scope[0]
        operation = identity.operation
        value = identity.value
        # Menhir's research adapter serializes scalar values as strings; the panel
        # schema stores numeric candidates, so normalize integer/decimal strings
        # before comparing expected identity fields.
        if isinstance(value, str):
            try:
                value = int(value)
            except ValueError:
                try:
                    value = float(value)
                except ValueError:
                    pass
    return {"parse_status": receipt.parse_status, "parse_reason": receipt.parse_reason, "composition_status": receipt.composition_status, "composition_reason": receipt.composition_reason, "relation_type": relation, "target": target, "operation": operation, "value": value}


def analyze_panel(path: str | Path, *, menhir_root: str | Path, generated_at: str | None = None) -> dict[str, Any]:
    panel = load_panel(path)
    api = load_panel_menhir_api(menhir_root)
    adapter, adapter_version = _load_adapter(menhir_root)
    episodes = [SimpleNamespace(uuid=row["uuid"], content=row["content"]) for row in panel["episodes"]]
    rows = []
    slices: dict[str, Counter[str]] = {"clean": Counter(), "noisy": Counter()}
    perturbations: dict[str, Counter[str]] = defaultdict(Counter)
    pair_actual: dict[str, dict[str, tuple[Any, ...]]] = defaultdict(dict)
    pair_expected_invariant: dict[str, bool] = {}
    for case in panel["cases"]:
        result = adapter(case["candidate"], episodes, candidate_id=case["case_id"])
        actual = _actual(result)
        expected = case["expected"]
        dimensions = sorted(field for field in ("parse_status", "parse_reason", "composition_status", "composition_reason", "relation_type", "target", "operation", "value") if actual[field] != expected[field])
        correct = not dimensions
        false_current = bool(expected["false_current"] and actual["composition_status"] == "composed")
        row = {"case_id": case["case_id"], "pair_id": case["pair_id"], "slice": case["slice"], "role": expected["role"], "expected": {k: expected[k] for k in expected if k not in {"role", "paired_invariant", "false_current"}}, "actual": actual, "mismatch_dimensions": dimensions, "false_current_state_error": false_current, "correct": correct}
        rows.append(row)
        counter = slices[case["slice"]]
        counter["total"] += 1
        counter["correct"] += int(correct)
        counter["parse_admitted"] += int(actual["parse_status"] == "admitted")
        counter["composed"] += int(actual["composition_status"] == "composed")
        counter["false_current_state_errors"] += int(false_current)
        perturbations[case["perturbation_id"]][case["slice"]] += 1
        pair_actual[case["pair_id"]][case["slice"]] = tuple(actual[field] for field in ("composition_status", "relation_type", "target", "operation", "value"))
        pair_expected_invariant[case["pair_id"]] = expected["paired_invariant"]
    invariant_pairs = [pair for pair, flag in pair_expected_invariant.items() if flag]
    actual_invariant = [pair for pair in invariant_pairs if len(pair_actual[pair]) == 2 and pair_actual[pair]["clean"] == pair_actual[pair]["noisy"]]
    coverage = {
        "perturbations_total": len(perturbations),
        "clean_cases": sum(counts["clean"] for counts in perturbations.values()),
        "noisy_cases": sum(counts["noisy"] for counts in perturbations.values()),
        "paired_perturbations": sum(int(counts == {"clean": 1, "noisy": 1}) for counts in perturbations.values()),
        "by_perturbation": {name: dict(sorted(counts.items())) for name, counts in sorted(perturbations.items())},
    }
    return {"report_schema_version": REPORT_SCHEMA_VERSION, "promotion_status": PROMOTION_STATUS, "provenance": {"panel_id": panel["panel_id"], "panel_sha256": panel["file_sha256"], "source_sha256": panel["source_sha256"], "generated_at": generated_at or datetime.now(timezone.utc).isoformat(), "llm_used": False, "research_adapter_version": adapter_version, "composer_version": api.composer_version}, "aggregate": {"cases_total": len(rows), "correct": sum(int(row["correct"]) for row in rows), "false_current_state_errors": sum(int(row["false_current_state_error"]) for row in rows), "coverage": coverage, "slices": {name: dict(counter) for name, counter in slices.items()}, "paired_invariance": {"pairs_total": len(pair_expected_invariant), "expected_invariant_pairs": len(invariant_pairs), "actual_invariant_pairs": len(actual_invariant), "invariance_correct": len(actual_invariant)}}, "cases": rows}


def render_markdown(report: dict[str, Any]) -> str:
    aggregate = report["aggregate"]
    lines = ["# Noisy scalar identity acceptance panel", "", "Offline paired clean/noisy evidence; promotion remains `not_evaluable`.", "", f"- Cases: {aggregate['cases_total']}", f"- False-current-state errors: {aggregate['false_current_state_errors']}", f"- Paired invariance: {aggregate['paired_invariance']['actual_invariant_pairs']}/{aggregate['paired_invariance']['expected_invariant_pairs']}", "", "| Slice | Correct | Total | Composed |", "| --- | ---: | ---: | ---: |"]
    for name, values in aggregate["slices"].items():
        lines.append(f"| `{name}` | {values['correct']} | {values['total']} | {values['composed']} |")
    return "\n".join(lines) + "\n"


def write_reports(report: dict[str, Any], json_out: str | Path, markdown_out: str | Path) -> None:
    json_path, markdown_path = Path(json_out).resolve(), Path(markdown_out).resolve()
    if json_path == markdown_path or json_path.exists() or markdown_path.exists():
        raise PanelError("output paths must be distinct and non-existing")
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(render_markdown(report), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate paired noisy scalar identity cases.")
    parser.add_argument("panel")
    parser.add_argument("--menhir-root", required=True)
    parser.add_argument("--json-out", required=True)
    parser.add_argument("--markdown-out", required=True)
    args = parser.parse_args(argv)
    try:
        write_reports(analyze_panel(args.panel, menhir_root=args.menhir_root), args.json_out, args.markdown_out)
    except PanelError as exc:
        parser.error(str(exc))
    return 0


__all__ = ["analyze_panel", "load_panel", "main", "render_markdown", "source_sha256", "write_reports"]
