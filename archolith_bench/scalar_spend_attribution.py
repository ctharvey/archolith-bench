"""Offline historical scalar-spend attribution measurement.

The instrument reads a LongMemEval-style run directory, its manifest and provenance JSON,
the run-local SQLite telemetry sidecar, and a recall JSON/JSONL checkpoint.  It does not
call a service, open a writable database, infer causal lift, or estimate scalar spend from
unpersisted token usage.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sqlite3
import sys
import tempfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


REPORT_SCHEMA_VERSION = 1
REPORT_SCHEMA = "scalar-spend-attribution/v1"
GRAPHITI_PARENT_TASK = "memory: graphiti add_episode"
GRAPHITI_PHASE = "completed"
GRAPHITI_KIND = "chat"

_MANIFEST_REQUIRED = {
    "namespace",
    "question_id",
    "question",
    "answer",
    "scalar_llm_calls",
    "typed_assertions",
    "scalar_states_written",
    "scalar_views",
    "scalar_history_views",
    "user_founded_scalar_views",
    "failed_remaining",
    "failed_requeued",
    "drain_timed_out",
    "scalar_consolidated",
}
_MANIFEST_NONNEGATIVE_FIELDS = {
    "episodes",
    "enrichment_llm_tasks",
    "failed_remaining",
    "failed_requeued",
    "processing_attempts",
    "ready",
    "scalar_history_views",
    "scalar_llm_calls",
    "scalar_states_written",
    "scalar_views",
    "typed_assertions",
    "turn_evidence",
    "turns",
    "user_founded_scalar_views",
    "namespace_window",
}
_TELEMETRY_COLUMNS = {
    "id": "INTEGER",
    "recorded_at": "TEXT",
    "episode_uuid": "TEXT",
    "parent_task": "TEXT",
    "child_task": "TEXT",
    "phase": "TEXT",
    "kind": "TEXT",
    "model": "TEXT",
    "endpoint": "TEXT",
    "scheduler_task": "TEXT",
    "details_json": "TEXT",
}
_CHECKPOINT_RE = re.compile(r"\.(?:jsonl?|ndjson)$", re.IGNORECASE)
_MODEL_RE = re.compile(r"(?:gpt-[A-Za-z0-9._-]+|o\d+(?:-[A-Za-z0-9._-]+)?|claude-[A-Za-z0-9._-]+|gemini-[A-Za-z0-9._-]+)$", re.IGNORECASE)
_STATE_CURRENT_FACT_RE = re.compile(r"\bcurrent\s+fact:\s*[^\n=]{1,240}\s*=\s*[^\n]+", re.IGNORECASE)
_STATE_LEGACY_RE = re.compile(r"\bcurrent\s+[A-Za-z][^\n=]{0,120}\s*=\s*[^\n.]+", re.IGNORECASE)
_HISTORY_RE = re.compile(r"\badvisory\s+(?:scalar\s+)?history\b", re.IGNORECASE)


class AttributionError(ValueError):
    """Raised when historical evidence cannot be measured safely."""


def _fail(context: str, message: str) -> AttributionError:
    return AttributionError(f"{context}: {message}")


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_nonnegative_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _validate_json_numbers(value: Any, context: str) -> None:
    """Reject JSON NaN/Infinity and negative numeric values anywhere in an input record."""

    if isinstance(value, bool) or value is None or isinstance(value, str):
        return
    if isinstance(value, int) and value < 0:
        raise _fail(context, "contains a negative numeric value")
    if isinstance(value, float) and (not math.isfinite(value) or value < 0):
        raise _fail(context, "contains an invalid or negative numeric value")
    if isinstance(value, dict):
        for key, child in value.items():
            _validate_json_numbers(child, f"{context}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _validate_json_numbers(child, f"{context}[{index}]")


def _validate_number(value: object, context: str, *, integer: bool = False) -> int | float:
    if integer:
        if not _is_nonnegative_int(value):
            raise _fail(context, "must be a non-negative integer")
        return value
    if not _is_number(value) or not math.isfinite(float(value)) or float(value) < 0:
        raise _fail(context, "must be a finite non-negative number")
    return value


def _validate_timestamp(value: object, context: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise _fail(context, "must be a non-blank ISO-8601 timestamp")
    try:
        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise _fail(context, "must be a valid ISO-8601 timestamp") from exc
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise _fail(context, "must be timezone-aware")
    return timestamp


def _read_json(path: Path, context: str) -> Any:
    try:
        with path.open(encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError as exc:
        raise _fail(context, "file does not exist") from exc
    except OSError as exc:
        raise _fail(context, f"could not read file: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise _fail(context, f"invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}") from exc


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        with path.open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    raise _fail(str(path), f"blank JSONL line at {line_number}")
                try:
                    value = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise _fail(str(path), f"invalid JSONL at line {line_number}: {exc.msg}") from exc
                if not isinstance(value, dict):
                    raise _fail(str(path), f"line {line_number} must contain an object")
                rows.append(value)
    except FileNotFoundError as exc:
        raise _fail(str(path), "file does not exist") from exc
    except OSError as exc:
        raise _fail(str(path), f"could not read file: {exc}") from exc
    if not rows:
        raise _fail(str(path), "checkpoint is empty")
    return rows


def _read_checkpoint(path: Path) -> list[dict[str, Any]]:
    """Read either the normal JSONL checkpoint or an explicit JSON array checkpoint."""

    if path.suffix.lower() == ".json":
        value = _read_json(path, "recall checkpoint")
        if not isinstance(value, list) or not value:
            raise _fail(str(path), "JSON checkpoint must be a non-empty array")
        if not all(isinstance(row, dict) for row in value):
            raise _fail(str(path), "JSON checkpoint rows must be objects")
        return value
    return _read_jsonl(path)


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise _fail(str(path), f"could not hash file: {exc}") from exc
    return digest.hexdigest()


def _required_file(run_dir: Path, name: str) -> Path:
    path = run_dir / name
    if not path.is_file():
        raise _fail(str(path), "required input artifact is missing")
    return path


def discover_checkpoint(run_dir: Path) -> Path:
    """Find exactly one conventional recall checkpoint below ``run_dir``."""

    candidates = sorted(
        {
            path.resolve()
            for path in run_dir.rglob(".checkpoint_*")
            if path.is_file() and _CHECKPOINT_RE.search(path.name)
        }
    )
    if not candidates:
        raise _fail(str(run_dir), "no .checkpoint_*.json/.jsonl recall checkpoint found")
    if len(candidates) != 1:
        names = ", ".join(str(path) for path in candidates)
        raise _fail(str(run_dir), f"ambiguous recall checkpoint discovery; found {len(candidates)}: {names}")
    return candidates[0]


def _resolve_checkpoint(run_dir: Path, checkpoint_path: Path | None) -> Path:
    if checkpoint_path is None:
        return discover_checkpoint(run_dir)
    candidates = [checkpoint_path]
    if not checkpoint_path.is_absolute():
        candidates.append(run_dir / checkpoint_path)
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise _fail(str(checkpoint_path), "explicit recall checkpoint does not exist")


def _validate_manifest(value: Any) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    if not isinstance(value, list) or not value:
        raise _fail("manifest.json", "top level must be a non-empty array")
    by_task: dict[str, dict[str, Any]] = {}
    by_namespace: dict[str, str] = {}
    for index, row in enumerate(value):
        context = f"manifest.json row {index}"
        if not isinstance(row, dict):
            raise _fail(context, "must be an object")
        missing = sorted(_MANIFEST_REQUIRED - row.keys())
        if missing:
            raise _fail(context, f"missing required fields: {', '.join(missing)}")
        for field in ("namespace", "question_id", "question", "answer"):
            if not isinstance(row[field], str) or not row[field].strip():
                raise _fail(context, f"{field} must be a non-blank string")
        namespace = row["namespace"]
        task_id = row["question_id"]
        if namespace in by_namespace:
            raise _fail(context, f"duplicate namespace {namespace!r}")
        if task_id in by_task:
            raise _fail(context, f"duplicate question_id {task_id!r}")
        for field in _MANIFEST_NONNEGATIVE_FIELDS:
            if field in row:
                _validate_number(row[field], f"{context}.{field}", integer=True)
        for field in ("drain_timed_out", "scalar_consolidated"):
            if not isinstance(row[field], bool):
                raise _fail(context, f"{field} must be a boolean")
        by_namespace[namespace] = task_id
        by_task[task_id] = row
    return value, by_task


def _validate_attempt(attempt: Any, index: int) -> dict[str, Any]:
    context = f"run_provenance.json attempts[{index}]"
    if not isinstance(attempt, dict):
        raise _fail(context, "must be an object")
    required = {
        "attempt",
        "resumed",
        "menhir_commit",
        "bench_commit",
        "menhir_dirty",
        "bench_dirty",
        "phases_interrupted",
        "started_at",
    }
    missing = sorted(required - attempt.keys())
    if missing:
        raise _fail(context, f"missing required fields: {', '.join(missing)}")
    _validate_number(attempt["attempt"], f"{context}.attempt", integer=True)
    if attempt["attempt"] <= 0:
        raise _fail(context, "attempt must be positive")
    _validate_number(attempt["phases_interrupted"], f"{context}.phases_interrupted", integer=True)
    if not isinstance(attempt["resumed"], bool):
        raise _fail(context, "resumed must be a boolean")
    for field in ("menhir_dirty", "bench_dirty"):
        if not isinstance(attempt[field], bool):
            raise _fail(context, f"{field} must be a boolean")
    for field in ("menhir_commit", "bench_commit", "started_at"):
        if not isinstance(attempt[field], str) or not attempt[field].strip():
            raise _fail(context, f"{field} must be a non-blank string")
    return attempt


def _validate_provenance(value: Any) -> dict[str, Any]:
    context = "run_provenance.json"
    if not isinstance(value, dict):
        raise _fail(context, "top level must be an object")
    required = {
        "run_id",
        "attempt_count",
        "attempts",
        "phases",
        "noncanonical",
        "resumed",
        "menhir_commit",
        "bench_commit",
        "menhir_dirty",
        "bench_dirty",
    }
    missing = sorted(required - value.keys())
    if missing:
        raise _fail(context, f"missing required fields: {', '.join(missing)}")
    if not isinstance(value["run_id"], str) or not value["run_id"].strip():
        raise _fail(context, "run_id must be a non-blank string")
    _validate_number(value["attempt_count"], f"{context}.attempt_count", integer=True)
    if value["attempt_count"] <= 0:
        raise _fail(context, "attempt_count must be positive")
    if not isinstance(value["attempts"], list) or len(value["attempts"]) != value["attempt_count"]:
        raise _fail(context, "attempts must be a list whose length equals attempt_count")
    attempts = [_validate_attempt(attempt, index) for index, attempt in enumerate(value["attempts"])]
    attempt_ids = [attempt["attempt"] for attempt in attempts]
    if len(set(attempt_ids)) != len(attempt_ids):
        raise _fail(context, "duplicate attempt numbers")
    if not isinstance(value["phases"], list) or not value["phases"]:
        raise _fail(context, "phases must be a non-empty list")
    for index, phase in enumerate(value["phases"]):
        phase_context = f"{context} phases[{index}]"
        if not isinstance(phase, dict):
            raise _fail(phase_context, "must be an object")
        for field in ("phase", "status"):
            if not isinstance(phase.get(field), str) or not phase[field].strip():
                raise _fail(phase_context, f"{field} must be a non-blank string")
    if not isinstance(value["noncanonical"], bool) or not isinstance(value["resumed"], bool):
        raise _fail(context, "noncanonical and resumed must be booleans")
    for field in ("menhir_dirty", "bench_dirty"):
        if not isinstance(value[field], bool):
            raise _fail(context, f"{field} must be a boolean")
    for field in ("menhir_commit", "bench_commit"):
        if not isinstance(value[field], str) or not value[field].strip():
            raise _fail(context, f"{field} must be a non-blank string")
    return value


def _validate_raw_usage(raw_usage: Any, context: str) -> tuple[int, int, int]:
    if not isinstance(raw_usage, dict):
        raise _fail(context, "raw_usage must be an object")
    required = ("prompt_tokens", "completion_tokens", "total_tokens")
    missing = [field for field in required if field not in raw_usage]
    if missing:
        raise _fail(context, f"raw_usage missing required fields: {', '.join(missing)}")
    values = tuple(_validate_number(raw_usage[field], f"{context}.{field}", integer=True) for field in required)
    if values[0] + values[1] != values[2]:
        raise _fail(context, "raw_usage.total_tokens must equal prompt_tokens + completion_tokens")
    return values


def _validate_checkpoint(
    rows: Sequence[Mapping[str, Any]],
    manifest_by_task: Mapping[str, Mapping[str, Any]],
) -> tuple[dict[str, dict[str, dict[str, Any]]], set[str]]:
    by_task_arm: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for index, row in enumerate(rows):
        context = f"recall checkpoint row {index}"
        _validate_json_numbers(row, context)
        for field in ("arm", "task_id", "result"):
            if field not in row:
                raise _fail(context, f"missing required field {field}")
        if not isinstance(row["arm"], str) or not row["arm"].strip():
            raise _fail(context, "arm must be a non-blank string")
        if not isinstance(row["task_id"], str) or not row["task_id"].strip():
            raise _fail(context, "task_id must be a non-blank string")
        task_id = row["task_id"]
        if task_id not in manifest_by_task:
            raise _fail(context, f"task_id {task_id!r} is not present in manifest.json")
        if not isinstance(row["result"], dict):
            raise _fail(context, "result must be an object")
        result = row["result"]
        for field in ("task_id", "correct", "input_tokens", "output_tokens", "latency_ms", "recalled"):
            if field not in result:
                raise _fail(context, f"result missing required field {field}")
        if result["task_id"] != task_id:
            raise _fail(context, "result.task_id does not match row.task_id")
        if not isinstance(result["correct"], bool):
            raise _fail(context, "result.correct must be a boolean")
        _validate_number(result["input_tokens"], f"{context}.result.input_tokens", integer=True)
        _validate_number(result["output_tokens"], f"{context}.result.output_tokens", integer=True)
        _validate_number(result["latency_ms"], f"{context}.result.latency_ms")
        if not isinstance(result["recalled"], str):
            raise _fail(context, "result.recalled must be a string")
        if "raw_usage" in result:
            prompt_tokens, completion_tokens, total_tokens = _validate_raw_usage(result["raw_usage"], f"{context}.result.raw_usage")
            if prompt_tokens != result["input_tokens"] or completion_tokens != result["output_tokens"]:
                raise _fail(context, "raw_usage token counts do not match result token counts")
        elif "total_tokens" in result:
            total_tokens = _validate_number(result["total_tokens"], f"{context}.result.total_tokens", integer=True)
            if total_tokens != result["input_tokens"] + result["output_tokens"]:
                raise _fail(context, "result.total_tokens must equal input_tokens + output_tokens")
        else:
            total_tokens = result["input_tokens"] + result["output_tokens"]
        if "ts" in row:
            _validate_number(row["ts"], f"{context}.ts")
        arm = row["arm"]
        if arm in by_task_arm[task_id]:
            raise _fail(context, f"duplicate arm-task row ({arm!r}, {task_id!r})")
        by_task_arm[task_id][arm] = {
            "arm": arm,
            "task_id": task_id,
            "correct": result["correct"],
            "input_tokens": result["input_tokens"],
            "output_tokens": result["output_tokens"],
            "total_tokens": total_tokens,
            "latency_ms": result["latency_ms"],
            "recalled": result["recalled"],
        }
    expected_tasks = set(manifest_by_task)
    observed_tasks = set(by_task_arm)
    if observed_tasks != expected_tasks:
        missing = sorted(expected_tasks - observed_tasks)
        extra = sorted(observed_tasks - expected_tasks)
        raise _fail("recall checkpoint", f"task coverage mismatch; missing={missing}, extra={extra}")
    arm_sets = {task_id: set(arms) for task_id, arms in by_task_arm.items()}
    all_arms = set().union(*arm_sets.values())
    for task_id, arms in arm_sets.items():
        if arms != all_arms:
            raise _fail("recall checkpoint", f"incomplete arm coverage for task {task_id!r}: {sorted(arms)}")
    if not all_arms:
        raise _fail("recall checkpoint", "no arms found")
    return dict(by_task_arm), all_arms


def _validate_telemetry_schema(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    table = connection.execute(
        "select name from sqlite_master where type = 'table' and name = 'episode_task_events'"
    ).fetchone()
    if table is None:
        raise _fail("mcp_telemetry.db", "telemetry schema mismatch: episode_task_events table is missing")
    rows = connection.execute('pragma table_info("episode_task_events")').fetchall()
    observed = {row[1]: str(row[2]).upper() for row in rows}
    missing = sorted(set(_TELEMETRY_COLUMNS) - set(observed))
    if missing:
        raise _fail("mcp_telemetry.db", f"telemetry schema mismatch; missing columns: {', '.join(missing)}")
    wrong_types = [
        f"{name}={observed[name]!r} (expected {_TELEMETRY_COLUMNS[name]!r})"
        for name in _TELEMETRY_COLUMNS
        if observed[name] != _TELEMETRY_COLUMNS[name]
    ]
    if wrong_types:
        raise _fail("mcp_telemetry.db", f"telemetry schema mismatch; wrong column types: {', '.join(wrong_types)}")
    return [
        {"name": name, "type": observed[name]}
        for name in sorted(observed)
    ]


def _read_telemetry(path: Path) -> dict[str, Any]:
    try:
        connection = sqlite3.connect(f"file:{path.resolve().as_posix()}?mode=ro", uri=True)
    except sqlite3.Error as exc:
        raise _fail(str(path), f"could not open SQLite in read-only mode: {exc}") from exc
    try:
        schema = _validate_telemetry_schema(connection)
        where = "parent_task = ? and phase = ? and kind = ?"
        parameters = (GRAPHITI_PARENT_TASK, GRAPHITI_PHASE, GRAPHITI_KIND)
        selected_timestamps = [
            row[0]
            for row in connection.execute(
                f"select recorded_at from episode_task_events where {where}",
                parameters,
            ).fetchall()
        ]
        parsed_timestamps = [
            (
                recorded_at,
                _validate_timestamp(recorded_at, f"mcp_telemetry.db episode_task_events row {index}.recorded_at"),
            )
            for index, recorded_at in enumerate(selected_timestamps)
        ]
        count = len(selected_timestamps)
        minimum = min(parsed_timestamps, key=lambda item: item[1])[0] if parsed_timestamps else None
        maximum = max(parsed_timestamps, key=lambda item: item[1])[0] if parsed_timestamps else None
        distributions: dict[str, dict[str, int]] = {}
        for field in ("model", "endpoint"):
            rows = connection.execute(
                f"select {field}, count(*) from episode_task_events where {where} group by {field} order by count(*) desc, {field}",
                parameters,
            ).fetchall()
            distributions[field] = {str(value if value is not None else "<null>"): int(row_count) for value, row_count in rows}
        if count < 0:
            raise _fail(str(path), "telemetry returned an invalid negative row count")
        return {
            "schema": schema,
            "completed_graphiti_ingest_chat_calls": int(count),
            "timestamp_boundary": {"first_recorded_at": minimum, "last_recorded_at": maximum},
            "model_distribution": distributions["model"],
            "endpoint_distribution": distributions["endpoint"],
            "selection": {
                "parent_task": GRAPHITI_PARENT_TASK,
                "phase": GRAPHITI_PHASE,
                "kind": GRAPHITI_KIND,
            },
        }
    except sqlite3.Error as exc:
        raise _fail(str(path), f"could not query telemetry schema/data: {exc}") from exc
    finally:
        connection.close()


def _infer_model(checkpoint_path: Path, explicit_model: str | None) -> dict[str, str | None]:
    if explicit_model is not None:
        if not explicit_model.strip():
            raise _fail("--model", "must not be blank")
        return {"value": explicit_model, "source": "explicit_cli", "filename_candidate": None}
    stem = checkpoint_path.name
    if stem.lower().endswith(".jsonl"):
        stem = stem[:-6]
    elif stem.lower().endswith(".json"):
        stem = stem[:-5]
    candidate = stem.rsplit("_", 1)[-1]
    match = _MODEL_RE.fullmatch(candidate)
    return {
        "value": candidate if match else None,
        "source": "checkpoint_filename" if match else None,
        "filename_candidate": candidate if match else None,
    }


def _presentation(recalled: str) -> dict[str, Any]:
    state_signatures: list[str] = []
    if _STATE_CURRENT_FACT_RE.search(recalled):
        state_signatures.append("current_fact_equals_line")
    if _STATE_LEGACY_RE.search(recalled):
        state_signatures.append("legacy_current_attribute_equals_line")
    history_signatures = ["advisory_scalar_history"] if _HISTORY_RE.search(recalled) else []
    return {
        "state_presented": bool(state_signatures),
        "history_presented": bool(history_signatures),
        "state_signatures": state_signatures,
        "history_signatures": history_signatures,
        "method": (
            "conservative documented serialization signatures only; presence does not show that the answer model used the evidence"
        ),
    }


def _decimal_rate(value: str | Decimal | None, flag: str) -> Decimal | None:
    if value is None:
        return None
    try:
        rate = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise _fail(flag, "must be a valid decimal number") from exc
    if not rate.is_finite() or rate < 0:
        raise _fail(flag, "must be a finite non-negative decimal")
    return rate


def _decimal_text(value: Decimal) -> str:
    return format(value, "f")


def _answer_costs(
    *,
    input_tokens: int,
    output_tokens: int,
    input_rate: Decimal | None,
    output_rate: Decimal | None,
) -> dict[str, str | None]:
    if input_rate is None or output_rate is None:
        return {"input_cost_usd": None, "output_cost_usd": None, "answer_cost_usd": None}
    divisor = Decimal(1_000_000)
    input_cost = Decimal(input_tokens) * input_rate / divisor
    output_cost = Decimal(output_tokens) * output_rate / divisor
    return {
        "input_cost_usd": _decimal_text(input_cost),
        "output_cost_usd": _decimal_text(output_cost),
        "answer_cost_usd": _decimal_text(input_cost + output_cost),
    }


def _arm_summary(
    rows: Iterable[Mapping[str, Any]],
    *,
    input_rate: Decimal | None,
    output_rate: Decimal | None,
) -> dict[str, Any]:
    rows = list(rows)
    input_tokens = sum(int(row["input_tokens"]) for row in rows)
    output_tokens = sum(int(row["output_tokens"]) for row in rows)
    total_tokens = sum(int(row["total_tokens"]) for row in rows)
    latency_total = sum(float(row["latency_ms"]) for row in rows)
    cost = _answer_costs(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        input_rate=input_rate,
        output_rate=output_rate,
    )
    return {
        "row_count": len(rows),
        "correct_count": sum(bool(row["correct"]) for row in rows),
        "correctness": {"correct": sum(bool(row["correct"]) for row in rows), "total": len(rows)},
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "latency_ms_total": latency_total,
        "latency_ms_mean": latency_total / len(rows) if rows else None,
        **cost,
    }


def _provenance_report(raw: Mapping[str, Any]) -> dict[str, Any]:
    attempts = list(raw["attempts"])
    commit_identities = {
        "menhir": sorted({str(raw["menhir_commit"]), *(str(attempt["menhir_commit"]) for attempt in attempts)}),
        "bench": sorted({str(raw["bench_commit"]), *(str(attempt["bench_commit"]) for attempt in attempts)}),
    }
    interrupted = [
        {
            "phase": phase.get("phase"),
            "status": phase.get("status"),
            "started_at": phase.get("started_at"),
            "interrupted_at": phase.get("interrupted_at"),
        }
        for phase in raw["phases"]
        if phase.get("status") == "interrupted"
    ]
    resumed_observed = bool(raw["resumed"] or any(attempt["resumed"] for attempt in attempts) or len(attempts) > 1)
    dirty_attempts = [
        {
            "attempt": attempt["attempt"],
            "menhir_dirty": attempt["menhir_dirty"],
            "bench_dirty": attempt["bench_dirty"],
        }
        for attempt in attempts
        if attempt["menhir_dirty"] or attempt["bench_dirty"]
    ]
    reasons: list[str] = []
    if raw["noncanonical"]:
        reasons.append("run_provenance.json declares noncanonical=true")
    if resumed_observed:
        reasons.append("the run was resumed across multiple attempts")
    if len(commit_identities["menhir"]) > 1 or len(commit_identities["bench"]) > 1:
        reasons.append("Menhir and/or Bench commit identities changed across attempts (mixed-code run)")
    if raw["menhir_dirty"] or raw["bench_dirty"] or dirty_attempts:
        reasons.append("at least one recorded attempt had a dirty source tree")
    if interrupted:
        reasons.append("one or more recorded phases were interrupted")
    return {
        "run_id": raw["run_id"],
        "declared_noncanonical": raw["noncanonical"],
        "declared_resumed": raw["resumed"],
        "resumed_observed": resumed_observed,
        "attempt_count": raw["attempt_count"],
        "top_level_commit_identities": {"menhir": raw["menhir_commit"], "bench": raw["bench_commit"]},
        "commit_identities_across_attempts": commit_identities,
        "top_level_dirty_flags": {"menhir": raw["menhir_dirty"], "bench": raw["bench_dirty"]},
        "dirty_attempts": dirty_attempts,
        "attempts": [
            {
                "attempt": attempt["attempt"],
                "resumed": attempt["resumed"],
                "menhir_commit": attempt["menhir_commit"],
                "bench_commit": attempt["bench_commit"],
                "menhir_dirty": attempt["menhir_dirty"],
                "bench_dirty": attempt["bench_dirty"],
                "phases_interrupted": attempt["phases_interrupted"],
                "started_at": attempt["started_at"],
            }
            for attempt in attempts
        ],
        "interrupted_phases": interrupted,
        "canonicality_observation": "concerns_observed" if reasons else "no_observed_concerns",
        "observed_canonicality_concerns": reasons,
        "full_canonical_acceptance_evaluated": False,
        "source_record": dict(raw),
    }


def measure(
    run_dir: Path | str,
    *,
    checkpoint_path: Path | str | None = None,
    model: str | None = None,
    input_usd_per_million: str | Decimal | None = None,
    output_usd_per_million: str | Decimal | None = None,
    negative_controls: Sequence[str] = (),
) -> dict[str, Any]:
    """Measure one historical run without mutating any input artifact."""

    run_dir = Path(run_dir).resolve()
    if not run_dir.is_dir():
        raise _fail(str(run_dir), "run directory does not exist or is not a directory")
    manifest_path = _required_file(run_dir, "manifest.json")
    provenance_path = _required_file(run_dir, "run_provenance.json")
    telemetry_path = _required_file(run_dir, "mcp_telemetry.db")
    checkpoint = _resolve_checkpoint(run_dir, Path(checkpoint_path) if checkpoint_path is not None else None)
    manifest_value = _read_json(manifest_path, "manifest.json")
    _validate_json_numbers(manifest_value, "manifest.json")
    manifest, manifest_by_task = _validate_manifest(manifest_value)
    provenance_value = _read_json(provenance_path, "run_provenance.json")
    _validate_json_numbers(provenance_value, "run_provenance.json")
    provenance = _validate_provenance(provenance_value)
    checkpoint_rows = _read_checkpoint(checkpoint)
    checkpoint_by_task, arms = _validate_checkpoint(checkpoint_rows, manifest_by_task)
    telemetry = _read_telemetry(telemetry_path)
    input_rate = _decimal_rate(input_usd_per_million, "--input-usd-per-million")
    output_rate = _decimal_rate(output_usd_per_million, "--output-usd-per-million")
    if (input_rate is None) != (output_rate is None):
        raise _fail("pricing", "input and output USD-per-million rates must be supplied together")

    manifest_aggregate: dict[str, Any] = {"namespace_count": len(manifest)}
    for field in (
        "scalar_llm_calls",
        "typed_assertions",
        "scalar_states_written",
        "scalar_views",
        "scalar_history_views",
        "user_founded_scalar_views",
        "failed_remaining",
        "failed_requeued",
    ):
        manifest_aggregate[field] = sum(int(row[field]) for row in manifest)
    manifest_aggregate.update(
        {
            "namespaces_with_failures": sum(row["failed_remaining"] > 0 for row in manifest),
            "drain_timeout_count": sum(row["drain_timed_out"] for row in manifest),
            "scalar_consolidated_count": sum(row["scalar_consolidated"] for row in manifest),
            "scalar_consolidation_status_counts": dict(
                Counter("completed" if row["scalar_consolidated"] else "not_completed" for row in manifest)
            ),
            "paid_namespaces_zero_typed_assertions": sum(
                row["scalar_llm_calls"] > 0 and row["typed_assertions"] == 0 for row in manifest
            ),
            "paid_namespaces_zero_state_or_history_views": sum(
                row["scalar_llm_calls"] > 0 and row["scalar_views"] == 0 and row["scalar_history_views"] == 0
                for row in manifest
            ),
        }
    )

    recall_arms: dict[str, dict[str, Any]] = {}
    for arm in sorted(arms):
        recall_arms[arm] = _arm_summary(
            (checkpoint_by_task[task_id][arm] for task_id in sorted(checkpoint_by_task)),
            input_rate=input_rate,
            output_rate=output_rate,
        )

    joins: list[dict[str, Any]] = []
    for row in manifest:
        task_id = row["question_id"]
        recall = {}
        for arm in sorted(arms):
            score = checkpoint_by_task[task_id][arm]
            recall[arm] = {
                "correct": score["correct"],
                "input_tokens": score["input_tokens"],
                "output_tokens": score["output_tokens"],
                "total_tokens": score["total_tokens"],
                "latency_ms": score["latency_ms"],
                "presentation": _presentation(score["recalled"]),
            }
        joins.append(
            {
                "namespace": row["namespace"],
                "task_id": task_id,
                "question": row["question"],
                "scalar": {
                    field: row[field]
                    for field in (
                        "scalar_llm_calls",
                        "typed_assertions",
                        "scalar_states_written",
                        "scalar_views",
                        "scalar_history_views",
                        "user_founded_scalar_views",
                        "failed_remaining",
                        "failed_requeued",
                        "drain_timed_out",
                        "scalar_consolidated",
                    )
                },
                "recall": recall,
            }
        )

    attribution: dict[str, Any] = {
        "scalar_attributable_corrected_answers": None,
        "scalar_cost_per_scalar_corrected_answer_usd": None,
        "status": "not_measured",
        "reason": (
            "There is no scalar-disabled memory counterfactual. A presented scalar signature and a correct answer "
            "are only candidate/intersection evidence; they do not prove that scalar processing caused a correction."
        ),
        "candidate_and_intersection_counts": {
            "tasks_with_scalar_state_views": sum(row["scalar_views"] > 0 for row in manifest),
            "tasks_with_scalar_history_views": sum(row["scalar_history_views"] > 0 for row in manifest),
            "by_arm": {},
        },
    }
    for arm in sorted(arms):
        arm_rows = [join["recall"][arm] for join in joins]
        attribution["candidate_and_intersection_counts"]["by_arm"][arm] = {
            "rows": len(arm_rows),
            "rows_with_state_evidence_presented": sum(row["presentation"]["state_presented"] for row in arm_rows),
            "rows_with_history_evidence_presented": sum(row["presentation"]["history_presented"] for row in arm_rows),
            "correct_and_state_evidence_presented": sum(
                row["correct"] and row["presentation"]["state_presented"] for row in arm_rows
            ),
            "correct_and_history_evidence_presented": sum(
                row["correct"] and row["presentation"]["history_presented"] for row in arm_rows
            ),
        }

    requested_controls: list[dict[str, Any]] = []
    for requested in negative_controls:
        if not isinstance(requested, str) or not requested.strip():
            raise _fail("--negative-control", "task IDs must be non-blank strings")
        task_id = requested
        if task_id not in manifest_by_task:
            namespace_match = next((row["question_id"] for row in manifest if row["namespace"] == requested), None)
            if namespace_match is None:
                raise _fail("--negative-control", f"task ID or namespace {requested!r} is not present in manifest.json")
            task_id = namespace_match
        matching = next(join for join in joins if join["task_id"] == task_id)
        requested_controls.append({"requested": requested, "resolved_task_id": task_id, **matching})

    artifacts = []
    for role, path in (
        ("manifest", manifest_path),
        ("run_provenance", provenance_path),
        ("telemetry", telemetry_path),
        ("recall_checkpoint", checkpoint),
    ):
        artifacts.append(
            {
                "role": role,
                "path": str(path),
                "sha256": _hash_file(path),
                "size_bytes": path.stat().st_size,
            }
        )

    generated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    report = {
        "report_schema": REPORT_SCHEMA,
        "schema_version": REPORT_SCHEMA_VERSION,
        "generated_at": generated_at,
        "measurement": {
            "mode": "offline_read_only",
            "network_calls": False,
            "llm_calls": False,
            "neo4j_calls": False,
            "docker_calls": False,
            "input_mutations": False,
            "output_paths_are_explicit": True,
        },
        "input_artifacts": artifacts,
        "provenance": _provenance_report(provenance),
        "manifest": {"aggregate": manifest_aggregate, "namespaces": joins},
        "telemetry": telemetry,
        "observed_call_count_comparison": {
            "scalar_manifest_calls": manifest_aggregate["scalar_llm_calls"],
            "completed_graphiti_ingest_chat_calls": telemetry["completed_graphiti_ingest_chat_calls"],
            "denominator": "completed episode_task_events where parent_task='memory: graphiti add_episode', phase='completed', kind='chat'",
            "warning": "These are observed call counts from different stages and are not token- or dollar-equivalent.",
            "scalar_consolidation_calls_are_manifest_counted": True,
            "scalar_consolidation_calls_are_graphiti_task_events": False,
            "token_usage_claimed": False,
        },
        "recall_checkpoint": {
            "path": str(checkpoint),
            "sha256": next(artifact["sha256"] for artifact in artifacts if artifact["role"] == "recall_checkpoint"),
            "task_count": len(manifest),
            "arms": sorted(arms),
            "model_identity": _infer_model(checkpoint, model),
            "arm_summaries": recall_arms,
            "evaluator_judge": {
                "input_tokens": None,
                "output_tokens": None,
                "total_tokens": None,
                "cost_usd": None,
                "status": "not_measured",
                "reason": "Evaluator/judge token usage and cost were not persisted in the recall checkpoint.",
            },
        },
        "pricing": {
            "input_usd_per_million": _decimal_text(input_rate) if input_rate is not None else None,
            "output_usd_per_million": _decimal_text(output_rate) if output_rate is not None else None,
            "status": "explicit_rates" if input_rate is not None else "not_measured",
            "source": "explicit_cli_rates_only",
            "current_web_pricing_used": False,
            "scalar_spend_included": False,
        },
        "attribution": attribution,
        "negative_controls": requested_controls,
        "limitations": [
            "This historical run is descriptive evidence only, not canonical acceptance evidence.",
            "Full canonical acceptance is not evaluated by this instrument; no observed concerns are not a certification.",
            "Scalar consolidation calls are counted from the manifest; they are not Graphiti episode task events and their token usage is not persisted here.",
            "Recall correctness plus presented scalar formatting is an intersection/candidate count, not a scalar-caused correction.",
            "Answer cost covers only persisted recall input/output tokens and explicit rates; it excludes scalar spend and evaluator/judge spend.",
            "Presented signatures show only that formatted state/history text was in the recalled payload; they do not show that the answer model used it.",
        ],
    }
    return report


def render_markdown(report: Mapping[str, Any]) -> str:
    """Render the report with the conclusion and limitations first."""

    aggregate = report["manifest"]["aggregate"]
    telemetry = report["telemetry"]
    comparison = report["observed_call_count_comparison"]
    provenance = report["provenance"]
    recall = report["recall_checkpoint"]
    pricing = report["pricing"]
    lines = [
        "# Historical Scalar Spend Attribution",
        "",
        "## Conclusion",
        "",
        (
            f"This offline instrument observed {aggregate['scalar_llm_calls']} manifest scalar calls across "
            f"{aggregate['namespace_count']} namespaces and {telemetry['completed_graphiti_ingest_chat_calls']} "
            "completed Graphiti ingest chat calls. The result is descriptive evidence only: it does not measure "
            "scalar-caused answer corrections or scalar spend."
        ),
        "",
        (
            f"The recall checkpoint contains {recall['task_count']} tasks per arm. Answer costs are "
            f"{pricing['status']}; scalar and evaluator/judge spend are excluded."
        ),
        "",
        "## Limitations",
        "",
    ]
    lines.extend(f"- {item}" for item in report["limitations"])
    lines.extend(
        [
            "",
            "## Provenance posture",
            "",
            (
                "Full canonical acceptance: **not evaluated by this instrument**. "
                f"Observed canonicality concerns: {len(provenance['observed_canonicality_concerns'])}. "
                f"Attempts: {provenance['attempt_count']}; resumed observed: {provenance['resumed_observed']}; "
                f"declared noncanonical: {provenance['declared_noncanonical']}."
            ),
            "",
            "Observed concerns:",
            "",
        ]
    )
    lines.extend(
        f"- {reason}"
        for reason in provenance["observed_canonicality_concerns"]
        or ["none observed (this is not a canonical acceptance certification)"]
    )
    lines.extend(
        [
            "",
            "Commit identities across attempts:",
            "",
            f"- Menhir: `{', '.join(provenance['commit_identities_across_attempts']['menhir'])}`",
            f"- Bench: `{', '.join(provenance['commit_identities_across_attempts']['bench'])}`",
            "",
            "## Aggregate manifest accounting",
            "",
            "| Metric | Value |",
            "|---|---:|",
        ]
    )
    aggregate_rows = [
        ("Namespaces", aggregate["namespace_count"]),
        ("Scalar LLM calls", aggregate["scalar_llm_calls"]),
        ("Typed assertions", aggregate["typed_assertions"]),
        ("Scalar states written", aggregate["scalar_states_written"]),
        ("Scalar state Views (`scalar_views`)", aggregate["scalar_views"]),
        ("Scalar history Views", aggregate["scalar_history_views"]),
        ("User-founded scalar Views", aggregate["user_founded_scalar_views"]),
        ("Failed remaining total", aggregate["failed_remaining"]),
        ("Failed requeued total", aggregate["failed_requeued"]),
        ("Namespaces with failures", aggregate["namespaces_with_failures"]),
        ("Drain timeouts", aggregate["drain_timeout_count"]),
        ("Scalar consolidated namespaces", aggregate["scalar_consolidated_count"]),
        ("Paid namespaces with zero typed assertions", aggregate["paid_namespaces_zero_typed_assertions"]),
        ("Paid namespaces with zero state/history Views", aggregate["paid_namespaces_zero_state_or_history_views"]),
    ]
    lines.extend(f"| {label} | {value} |" for label, value in aggregate_rows)
    lines.extend(
        [
            "",
            "## Observed call-count comparison",
            "",
            "| Source | Exact count |",
            "|---|---:|",
            f"| Manifest scalar calls | {comparison['scalar_manifest_calls']} |",
            f"| Completed Graphiti ingest chat calls | {comparison['completed_graphiti_ingest_chat_calls']} |",
            "",
            f"Denominator: `{comparison['denominator']}`.",
            "Scalar consolidation calls are counted separately from the manifest and are not represented as Graphiti task events; these counts are not token- or dollar-equivalent.",
            "",
            "Graphiti timestamp boundary:",
            "",
            f"`{telemetry['timestamp_boundary']['first_recorded_at']}` through `{telemetry['timestamp_boundary']['last_recorded_at']}`.",
            "",
            f"Model distribution: `{json.dumps(telemetry['model_distribution'], sort_keys=True)}`",
            f"Endpoint distribution: `{json.dumps(telemetry['endpoint_distribution'], sort_keys=True)}`",
            "",
            "## Recall arms",
            "",
            "| Arm | Rows/calls | Correct | Input tokens | Output tokens | Total tokens | Latency ms total | Answer cost USD |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for arm, summary in recall["arm_summaries"].items():
        lines.append(
            f"| {arm} | {summary['row_count']} | {summary['correct_count']} | {summary['input_tokens']} | "
            f"{summary['output_tokens']} | {summary['total_tokens']} | {summary['latency_ms_total']:.3f} | "
            f"{summary['answer_cost_usd'] if summary['answer_cost_usd'] is not None else 'not_measured'} |"
        )
    lines.extend(
        [
            "",
            "Model identity: "
            + str(recall["model_identity"]["value"] or "not_inferable")
            + f" (source: {recall['model_identity']['source'] or 'none'}).",
            "Evaluator/judge tokens and cost: `null` / `not_measured`.",
            "",
            "## Candidate/intersection counts (not causal attribution)",
            "",
            f"Tasks with scalar state Views: {report['attribution']['candidate_and_intersection_counts']['tasks_with_scalar_state_views']}; "
            f"tasks with scalar history Views: {report['attribution']['candidate_and_intersection_counts']['tasks_with_scalar_history_views']}.",
            "",
            "| Arm | State presented | History presented | Correct + state presented | Correct + history presented |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for arm, counts in report["attribution"]["candidate_and_intersection_counts"]["by_arm"].items():
        lines.append(
            f"| {arm} | {counts['rows_with_state_evidence_presented']} | {counts['rows_with_history_evidence_presented']} | "
            f"{counts['correct_and_state_evidence_presented']} | {counts['correct_and_history_evidence_presented']} |"
        )
    lines.extend(
        [
            "",
            "Scalar-attributable corrected answers: `null` / `not_measured`; cost per scalar-corrected answer: `null` / `not_measured`.",
            "",
            "## Per-namespace scalar accounting",
            "",
            "| Namespace | Task | Scalar calls | Assertions | States written | State Views | History Views | User-founded Views | Failed | Requeued | Timeout | Consolidated |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|",
        ]
    )
    for row in report["manifest"]["namespaces"]:
        scalar = row["scalar"]
        lines.append(
            f"| {row['namespace']} | {row['task_id']} | {scalar['scalar_llm_calls']} | {scalar['typed_assertions']} | "
            f"{scalar['scalar_states_written']} | {scalar['scalar_views']} | {scalar['scalar_history_views']} | "
            f"{scalar['user_founded_scalar_views']} | {scalar['failed_remaining']} | {scalar['failed_requeued']} | "
            f"{scalar['drain_timed_out']} | "
            f"{scalar['scalar_consolidated']} |"
        )
    lines.extend(
        [
            "",
            "## Per-task recall/presentation join",
            "",
            "State/history presentation is detected only from conservative serialized signatures; it does not establish answer-model use.",
            "",
            "| Namespace | Task | Arm | Correct | State presented | History presented | Input | Output | Latency ms |",
            "|---|---|---|---|---|---|---:|---:|---:|",
        ]
    )
    for row in report["manifest"]["namespaces"]:
        for arm, score in row["recall"].items():
            presentation = score["presentation"]
            lines.append(
                f"| {row['namespace']} | {row['task_id']} | {arm} | {score['correct']} | "
                f"{presentation['state_presented']} | {presentation['history_presented']} | "
                f"{score['input_tokens']} | {score['output_tokens']} | {float(score['latency_ms']):.3f} |"
            )
    if report["negative_controls"]:
        lines.extend(["", "## Negative controls", "", "| Requested | Resolved task | Namespace |", "|---|---|---|"])
        lines.extend(
            f"| {row['requested']} | {row['resolved_task_id']} | {row['namespace']} |"
            for row in report["negative_controls"]
        )
    lines.extend(
        [
            "",
            "## Input artifact hashes",
            "",
            "| Role | Path | SHA-256 | Bytes |",
            "|---|---|---|---:|",
        ]
    )
    lines.extend(
        f"| {artifact['role']} | `{artifact['path']}` | `{artifact['sha256']}` | {artifact['size_bytes']} |"
        for artifact in report["input_artifacts"]
    )
    lines.extend(["", f"Report schema: `{report['report_schema']}`; generated at `{report['generated_at']}`.", ""])
    return "\n".join(lines)


def _canonical_filesystem_path(path: Path | str, context: str) -> str:
    try:
        return os.path.normcase(os.path.realpath(os.path.abspath(os.fspath(path))))
    except (OSError, TypeError) as exc:
        raise _fail(context, f"could not resolve path: {exc}") from exc


def _validate_output_paths(report: Mapping[str, Any], json_path: Path, markdown_path: Path) -> None:
    """Reject output collisions before creating directories or files."""

    json_resolved = _canonical_filesystem_path(json_path, "JSON output")
    markdown_resolved = _canonical_filesystem_path(markdown_path, "Markdown output")
    if json_resolved == markdown_resolved:
        raise _fail("outputs", "JSON and Markdown output paths must differ")

    artifacts = report.get("input_artifacts")
    if not isinstance(artifacts, list):
        raise _fail("outputs", "report.input_artifacts must be a list before writing outputs")
    input_paths: dict[str, str] = {}
    for index, artifact in enumerate(artifacts):
        if not isinstance(artifact, dict) or not isinstance(artifact.get("path"), str) or not artifact["path"].strip():
            raise _fail("outputs", f"report.input_artifacts[{index}].path must be a non-blank string")
        resolved = _canonical_filesystem_path(artifact["path"], f"input artifact {index}")
        input_paths[resolved] = str(artifact.get("role") or f"artifact[{index}]")

    collisions = []
    for label, resolved in (("JSON output", json_resolved), ("Markdown output", markdown_resolved)):
        if resolved in input_paths:
            collisions.append(f"{label} collides with {input_paths[resolved]} ({resolved})")
    if collisions:
        raise _fail("outputs", "refusing to write colliding output path(s): " + "; ".join(collisions))


def _write_atomic_temp(path: Path, content: str, temp_paths: list[Path]) -> Path:
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_path = Path(handle.name)
            temp_paths.append(temp_path)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
    except OSError as exc:
        raise _fail(str(path), f"could not stage atomic output: {exc}") from exc
    return temp_path


def write_outputs(report: Mapping[str, Any], json_path: Path | str, markdown_path: Path | str) -> None:
    """Write requested JSON and Markdown outputs atomically after collision preflight."""

    json_path = Path(json_path)
    markdown_path = Path(markdown_path)
    _validate_output_paths(report, json_path, markdown_path)
    json_text = json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    markdown_text = render_markdown(report)
    temp_paths: list[Path] = []
    try:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        json_temp = _write_atomic_temp(json_path, json_text, temp_paths)
        markdown_temp = _write_atomic_temp(markdown_path, markdown_text, temp_paths)
        os.replace(json_temp, json_path)
        os.replace(markdown_temp, markdown_path)
    except AttributionError:
        raise
    except OSError as exc:
        raise _fail("outputs", f"could not publish atomic outputs: {exc}") from exc
    finally:
        for temp_path in temp_paths:
            try:
                temp_path.unlink()
            except FileNotFoundError:
                pass
            except OSError:
                pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Measure historical scalar spend attribution offline and read-only")
    parser.add_argument("run_dir", type=Path, help="historical run directory")
    parser.add_argument("--checkpoint", type=Path, help="explicit recall checkpoint JSON/JSONL path")
    parser.add_argument("--json-out", type=Path, required=True, help="explicit JSON report output path")
    parser.add_argument("--markdown-out", type=Path, required=True, help="explicit Markdown report output path")
    parser.add_argument("--model", help="answer model identity; overrides filename inference")
    parser.add_argument("--input-usd-per-million", help="explicit answer input price in USD per million tokens")
    parser.add_argument("--output-usd-per-million", help="explicit answer output price in USD per million tokens")
    parser.add_argument(
        "--negative-control",
        action="append",
        default=[],
        metavar="TASK_ID",
        help="repeatable task ID or manifest namespace to call out as a negative control",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        report = measure(
            args.run_dir,
            checkpoint_path=args.checkpoint,
            model=args.model,
            input_usd_per_million=args.input_usd_per_million,
            output_usd_per_million=args.output_usd_per_million,
            negative_controls=args.negative_control,
        )
        write_outputs(report, args.json_out, args.markdown_out)
    except AttributionError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


__all__ = [
    "AttributionError",
    "REPORT_SCHEMA",
    "REPORT_SCHEMA_VERSION",
    "discover_checkpoint",
    "main",
    "measure",
    "render_markdown",
    "write_outputs",
]
