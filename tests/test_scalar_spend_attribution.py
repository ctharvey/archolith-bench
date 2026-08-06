from __future__ import annotations

import hashlib
import json
import sqlite3
from copy import deepcopy
from pathlib import Path

import pytest

from archolith_bench.scalar_spend_attribution import AttributionError, measure, render_markdown, write_outputs


def _manifest_rows() -> list[dict[str, object]]:
    def row(task_id: str, *, calls: int, assertions: int, views: int, history: int) -> dict[str, object]:
        return {
            "namespace": f"ns-{task_id}",
            "question_id": task_id,
            "question": f"Question {task_id}?",
            "answer": "three",
            "episodes": 1,
            "enrichment_llm_tasks": 2,
            "failed_remaining": 0,
            "failed_requeued": 0,
            "processing_attempts": 1,
            "ready": 1,
            "scalar_consolidated": True,
            "scalar_history_views": history,
            "scalar_llm_calls": calls,
            "scalar_states_written": views,
            "scalar_views": views,
            "typed_assertions": assertions,
            "turn_evidence": 1,
            "turns": 1,
            "user_founded_scalar_views": views,
            "drain_timed_out": False,
        }

    return [
        row("task-a", calls=3, assertions=1, views=1, history=1),
        row("task-b", calls=3, assertions=0, views=0, history=0),
        row("task-c", calls=0, assertions=0, views=0, history=0),
    ]


def _provenance(*, noncanonical: bool = False, attempts: int = 1) -> dict[str, object]:
    attempt_rows = []
    phases = []
    for index in range(1, attempts + 1):
        attempt_rows.append(
            {
                "attempt": index,
                "resumed": index > 1,
                "menhir_commit": f"menhir-{index}",
                "bench_commit": f"bench-{index}",
                "menhir_dirty": index == attempts and attempts > 1,
                "bench_dirty": False,
                "phases_interrupted": 1 if index < attempts else 0,
                "started_at": f"2026-08-05T0{index}:00:00Z",
            }
        )
        phases.append(
            {
                "phase": f"phase-{index}",
                "status": "interrupted" if index < attempts else "completed",
                "started_at": f"2026-08-05T0{index}:00:00Z",
                **({"interrupted_at": f"2026-08-05T0{index}:30:00Z"} if index < attempts else {}),
            }
        )
    return {
        "run_id": "synthetic-run",
        "attempt_count": attempts,
        "attempts": attempt_rows,
        "phases": phases,
        "noncanonical": noncanonical,
        "resumed": attempts > 1,
        "menhir_commit": attempt_rows[0]["menhir_commit"],
        "bench_commit": attempt_rows[0]["bench_commit"],
        "menhir_dirty": False,
        "bench_dirty": False,
    }


def _checkpoint_rows() -> list[dict[str, object]]:
    recalled = {
        ("task-a", "memory"): "[AUTHORITATIVE CURRENT MEMORY]\ncurrent fact: user — count = 3",
        ("task-a", "no_memory"): "ordinary content only",
        ("task-b", "memory"): "attribute history: advisory scalar history — not an absolute current total",
        ("task-b", "no_memory"): "ordinary content only",
        ("task-c", "memory"): "ordinary content only",
        ("task-c", "no_memory"): "ordinary content only",
    }
    rows = []
    for index, ((task_id, arm), payload) in enumerate(recalled.items(), start=1):
        input_tokens = 10 + index
        output_tokens = 2
        rows.append(
            {
                "arm": arm,
                "task_id": task_id,
                "ts": float(index),
                "result": {
                    "task_id": task_id,
                    "correct": (task_id == "task-a" and arm == "memory") or (task_id == "task-b" and arm == "memory"),
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "latency_ms": 20.5 + index,
                    "recalled": payload,
                    "raw_usage": {
                        "prompt_tokens": input_tokens,
                        "completion_tokens": output_tokens,
                        "total_tokens": input_tokens + output_tokens,
                    },
                },
            }
        )
    return rows


def _write_db(
    path: Path,
    *,
    schema_ok: bool = True,
    timestamps: tuple[str, str, str] = (
        "2026-08-05T00:00:00Z",
        "2026-08-05T00:01:00Z",
        "2026-08-05T00:02:00Z",
    ),
) -> None:
    connection = sqlite3.connect(path)
    if schema_ok:
        connection.execute(
            """create table episode_task_events (
                id INTEGER PRIMARY KEY,
                recorded_at TEXT NOT NULL,
                episode_uuid TEXT NOT NULL,
                parent_task TEXT,
                child_task TEXT,
                phase TEXT NOT NULL,
                kind TEXT,
                model TEXT,
                endpoint TEXT,
                scheduler_task TEXT,
                details_json TEXT
            )"""
        )
    else:
        connection.execute("create table episode_task_events (id INTEGER PRIMARY KEY, recorded_at TEXT NOT NULL)")
    if schema_ok:
        connection.executemany(
            """insert into episode_task_events
                (recorded_at, episode_uuid, parent_task, child_task, phase, kind, model, endpoint, scheduler_task, details_json)
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (
                    timestamps[0],
                    "episode-1",
                    "memory: graphiti add_episode",
                    "chat",
                    "completed",
                    "chat",
                    "test-model",
                    "chat.completions.create",
                    "scheduler",
                    "{}",
                ),
                (
                    timestamps[1],
                    "episode-2",
                    "memory: graphiti add_episode",
                    "chat",
                    "completed",
                    "chat",
                    "test-model",
                    "chat.completions.create",
                    "scheduler",
                    "{}",
                ),
                (
                    timestamps[2],
                    "episode-3",
                    "memory: graphiti add_episode",
                    "chat",
                    "started",
                    "chat",
                    "test-model",
                    "chat.completions.create",
                    "scheduler",
                    "{}",
                ),
            ],
        )
    connection.commit()
    connection.close()


def _fixture(tmp_path: Path, *, checkpoint_suffix: str = ".jsonl") -> tuple[Path, Path]:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "manifest.json").write_text(json.dumps(_manifest_rows()), encoding="utf-8")
    (run_dir / "run_provenance.json").write_text(json.dumps(_provenance()), encoding="utf-8")
    _write_db(run_dir / "mcp_telemetry.db")
    checkpoint = run_dir / f"harness_recall/.checkpoint_synthetic_gpt-4o{checkpoint_suffix}"
    checkpoint.parent.mkdir()
    rows = _checkpoint_rows()
    if checkpoint_suffix == ".json":
        checkpoint.write_text(json.dumps(rows), encoding="utf-8")
    else:
        checkpoint.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    return run_dir, checkpoint


def test_happy_path_hashes_provenance_join_and_decimal_pricing(tmp_path: Path) -> None:
    run_dir, _ = _fixture(tmp_path)
    report = measure(
        run_dir,
        input_usd_per_million="2.5",
        output_usd_per_million="10",
        negative_controls=["task-b"],
    )

    assert report["report_schema"] == "scalar-spend-attribution/v1"
    assert report["manifest"]["aggregate"]["namespace_count"] == 3
    assert report["manifest"]["aggregate"]["scalar_llm_calls"] == 6
    assert report["manifest"]["aggregate"]["typed_assertions"] == 1
    assert report["manifest"]["aggregate"]["paid_namespaces_zero_typed_assertions"] == 1
    assert report["manifest"]["aggregate"]["paid_namespaces_zero_state_or_history_views"] == 1
    assert report["telemetry"]["completed_graphiti_ingest_chat_calls"] == 2
    assert report["observed_call_count_comparison"]["denominator"].startswith("completed episode_task_events")
    assert report["recall_checkpoint"]["arm_summaries"]["memory"]["row_count"] == 3
    assert report["recall_checkpoint"]["arm_summaries"]["memory"]["correct_count"] == 2
    assert report["recall_checkpoint"]["arm_summaries"]["memory"]["answer_cost_usd"] == "0.0001575"
    assert report["recall_checkpoint"]["model_identity"]["value"] == "gpt-4o"
    assert report["negative_controls"][0]["resolved_task_id"] == "task-b"
    assert report["attribution"]["scalar_attributable_corrected_answers"] is None
    assert report["attribution"]["scalar_cost_per_scalar_corrected_answer_usd"] is None
    assert all(len(artifact["sha256"]) == 64 for artifact in report["input_artifacts"])
    assert report["provenance"]["canonicality_observation"] == "no_observed_concerns"
    assert report["provenance"]["observed_canonicality_concerns"] == []
    assert report["provenance"]["full_canonical_acceptance_evaluated"] is False


def test_clean_provenance_is_not_flagged_and_hash_is_stable(tmp_path: Path) -> None:
    run_dir, _ = _fixture(tmp_path)
    report = measure(run_dir)
    assert report["provenance"]["canonicality_observation"] == "no_observed_concerns"
    assert report["provenance"]["full_canonical_acceptance_evaluated"] is False
    assert report["provenance"]["attempt_count"] == 1
    manifest_hash = next(item["sha256"] for item in report["input_artifacts"] if item["role"] == "manifest")
    expected_hash = hashlib.sha256((run_dir / "manifest.json").read_bytes()).hexdigest()
    assert manifest_hash == expected_hash


def test_noncanonical_mixed_code_dirty_and_interrupted_flags(tmp_path: Path) -> None:
    run_dir, _ = _fixture(tmp_path)
    (run_dir / "run_provenance.json").write_text(json.dumps(_provenance(noncanonical=True, attempts=2)), encoding="utf-8")
    report = measure(run_dir)
    reasons = report["provenance"]["observed_canonicality_concerns"]
    assert report["provenance"]["canonicality_observation"] == "concerns_observed"
    assert report["provenance"]["full_canonical_acceptance_evaluated"] is False
    assert any("noncanonical" in reason for reason in reasons)
    assert any("mixed-code" in reason for reason in reasons)
    assert any("dirty" in reason for reason in reasons)
    assert report["provenance"]["interrupted_phases"]


def test_presentation_signatures_are_presence_only(tmp_path: Path) -> None:
    run_dir, _ = _fixture(tmp_path)
    report = measure(run_dir)
    rows = {row["task_id"]: row for row in report["manifest"]["namespaces"]}
    assert rows["task-a"]["recall"]["memory"]["presentation"]["state_presented"] is True
    assert rows["task-a"]["recall"]["memory"]["presentation"]["history_presented"] is False
    assert rows["task-b"]["recall"]["memory"]["presentation"]["history_presented"] is True
    assert "does not show that the answer model used" in rows["task-b"]["recall"]["memory"]["presentation"]["method"]


def test_missing_pricing_is_null_and_markdown_leads_with_limits(tmp_path: Path) -> None:
    run_dir, _ = _fixture(tmp_path)
    report = measure(run_dir)
    assert report["pricing"]["status"] == "not_measured"
    assert report["recall_checkpoint"]["arm_summaries"]["memory"]["answer_cost_usd"] is None
    markdown = render_markdown(report)
    assert markdown.index("## Conclusion") < markdown.index("## Aggregate manifest accounting")
    assert "full canonical acceptance: **not evaluated" in markdown.lower()


def test_output_collision_preflight_preserves_inputs_and_creates_no_sibling(tmp_path: Path) -> None:
    run_dir, _ = _fixture(tmp_path)
    report = measure(run_dir)
    manifest = run_dir / "manifest.json"
    original_bytes = manifest.read_bytes()
    original_hash = hashlib.sha256(original_bytes).hexdigest()
    sibling = tmp_path / "collision-output" / "report.md"

    with pytest.raises(AttributionError, match="collides with manifest"):
        write_outputs(report, manifest, sibling)

    assert manifest.read_bytes() == original_bytes
    assert hashlib.sha256(manifest.read_bytes()).hexdigest() == original_hash
    assert not sibling.exists()
    assert not sibling.parent.exists()

    mutual_collision = tmp_path / "mutual-collision" / "report.json"
    with pytest.raises(AttributionError, match="must differ"):
        write_outputs(report, mutual_collision, mutual_collision)
    assert not mutual_collision.exists()
    assert not mutual_collision.parent.exists()


def test_telemetry_boundaries_are_chronological_and_timezone_aware(tmp_path: Path) -> None:
    run_dir, _ = _fixture(tmp_path)
    telemetry = run_dir / "mcp_telemetry.db"
    telemetry.unlink()
    _write_db(
        telemetry,
        timestamps=(
            "2026-08-05T01:00:00+02:00",
            "2026-08-05T00:30:00+00:00",
            "2026-08-05T02:00:00+00:00",
        ),
    )
    report = measure(run_dir)
    assert report["telemetry"]["timestamp_boundary"] == {
        "first_recorded_at": "2026-08-05T01:00:00+02:00",
        "last_recorded_at": "2026-08-05T00:30:00+00:00",
    }

    telemetry.unlink()
    _write_db(telemetry, timestamps=("2026-08-05T00:00:00", "2026-08-05T00:01:00Z", "2026-08-05T00:02:00Z"))
    with pytest.raises(AttributionError, match="timezone-aware"):
        measure(run_dir)


def test_json_checkpoint_and_read_only_sqlite_schema(tmp_path: Path) -> None:
    run_dir, checkpoint = _fixture(tmp_path, checkpoint_suffix=".json")
    report = measure(run_dir, checkpoint_path=checkpoint)
    assert report["recall_checkpoint"]["task_count"] == 3
    connection = sqlite3.connect(f"file:{(run_dir / 'mcp_telemetry.db').as_posix()}?mode=ro", uri=True)
    with pytest.raises(sqlite3.OperationalError):
        connection.execute("insert into episode_task_events (recorded_at, episode_uuid, phase) values ('x', 'x', 'x')")
    connection.close()


def test_malformed_duplicate_incomplete_and_schema_inputs_fail_closed(tmp_path: Path) -> None:
    run_dir, checkpoint = _fixture(tmp_path)
    original_manifest = json.loads((run_dir / "manifest.json").read_text())

    (run_dir / "manifest.json").write_text("{", encoding="utf-8")
    with pytest.raises(AttributionError, match="invalid JSON"):
        measure(run_dir, checkpoint_path=checkpoint)
    (run_dir / "manifest.json").write_text(json.dumps(original_manifest), encoding="utf-8")

    duplicate_manifest = deepcopy(original_manifest)
    duplicate_manifest[1]["namespace"] = duplicate_manifest[0]["namespace"]
    (run_dir / "manifest.json").write_text(json.dumps(duplicate_manifest), encoding="utf-8")
    with pytest.raises(AttributionError, match="duplicate namespace"):
        measure(run_dir, checkpoint_path=checkpoint)
    (run_dir / "manifest.json").write_text(json.dumps(original_manifest), encoding="utf-8")

    duplicate_task_manifest = deepcopy(original_manifest)
    duplicate_task_manifest[1]["question_id"] = duplicate_task_manifest[0]["question_id"]
    (run_dir / "manifest.json").write_text(json.dumps(duplicate_task_manifest), encoding="utf-8")
    with pytest.raises(AttributionError, match="duplicate question_id"):
        measure(run_dir, checkpoint_path=checkpoint)
    invalid_numeric_manifest = deepcopy(original_manifest)
    invalid_numeric_manifest[0]["scalar_llm_calls"] = -1
    (run_dir / "manifest.json").write_text(json.dumps(invalid_numeric_manifest), encoding="utf-8")
    with pytest.raises(AttributionError, match="negative numeric|non-negative integer"):
        measure(run_dir, checkpoint_path=checkpoint)
    (run_dir / "manifest.json").write_text(json.dumps(original_manifest), encoding="utf-8")

    checkpoint.write_text(checkpoint.read_text(encoding="utf-8") + "not-json\n", encoding="utf-8")
    with pytest.raises(AttributionError, match="invalid JSONL"):
        measure(run_dir, checkpoint_path=checkpoint)
    (tmp_path / "second").mkdir()
    _, checkpoint = _fixture(tmp_path / "second")
    run_dir = checkpoint.parents[1]
    rows = checkpoint.read_text(encoding="utf-8").splitlines()
    checkpoint.write_text("\n".join(rows[:-1]) + "\n", encoding="utf-8")
    with pytest.raises(AttributionError, match="incomplete arm coverage|task coverage"):
        measure(run_dir, checkpoint_path=checkpoint)

    checkpoint.write_text("\n".join(json.dumps(row) for row in _checkpoint_rows()) + "\n", encoding="utf-8")
    (run_dir / "mcp_telemetry.db").unlink()
    _write_db(run_dir / "mcp_telemetry.db", schema_ok=False)
    with pytest.raises(AttributionError, match="schema mismatch"):
        measure(run_dir, checkpoint_path=checkpoint)


def test_duplicate_arm_task_and_ambiguous_discovery_fail(tmp_path: Path) -> None:
    run_dir, checkpoint = _fixture(tmp_path)
    checkpoint.write_text(checkpoint.read_text(encoding="utf-8") + checkpoint.read_text(encoding="utf-8").splitlines()[0] + "\n", encoding="utf-8")
    with pytest.raises(AttributionError, match="duplicate arm-task"):
        measure(run_dir, checkpoint_path=checkpoint)

    other = run_dir / "harness_recall/.checkpoint_other_gpt-4o.jsonl"
    other.write_text("{}\n", encoding="utf-8")
    with pytest.raises(AttributionError, match="ambiguous recall checkpoint"):
        measure(run_dir)
