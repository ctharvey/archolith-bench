from __future__ import annotations

import json
import sqlite3

from scripts.longmemeval.lib.summarize_llm_usage import (
    summarize_harness_usage,
    summarize_llm_usage,
)


def test_summarize_llm_usage_reports_provider_counts(tmp_path) -> None:
    db_path = tmp_path / "telemetry.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE llm_usage_events (
                call_id TEXT PRIMARY KEY, recorded_at TEXT NOT NULL, run_id TEXT,
                episode_uuid TEXT, operation TEXT, kind TEXT NOT NULL, model TEXT,
                endpoint TEXT, status TEXT NOT NULL, duration_ms INTEGER,
                input_tokens INTEGER, output_tokens INTEGER, total_tokens INTEGER,
                cached_input_tokens INTEGER, reasoning_output_tokens INTEGER,
                provider_usage_json TEXT, error TEXT
            )
            """
        )
        conn.executemany(
            """
            INSERT INTO llm_usage_events (
                call_id, recorded_at, run_id, kind, model, endpoint, status,
                input_tokens, output_tokens, total_tokens, cached_input_tokens,
                reasoning_output_tokens
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("a", "2026-08-07T00:00:00Z", "run-a", "chat", "gpt", "chat", "completed", 100, 20, 120, 40, 5),
                ("b", "2026-08-07T00:00:01Z", "run-a", "embedding", "embed", "embed", "completed", 10, 0, 10, 0, 0),
                ("c", "2026-08-07T00:00:02Z", "run-b", "chat", "gpt", "chat", "completed", 999, 1, 1000, 0, 0),
            ],
        )

    summary = summarize_llm_usage(db_path, run_id="run-a")

    assert summary["available"] is True
    assert summary["calls"] == 2
    assert summary["input_tokens"] == 110
    assert summary["output_tokens"] == 20
    assert summary["total_tokens"] == 130
    assert summary["cached_input_tokens"] == 40
    assert summary["reasoning_output_tokens"] == 5
    assert len(summary["by_model"]) == 2


def test_summarize_llm_usage_marks_legacy_database_unavailable(tmp_path) -> None:
    db_path = tmp_path / "legacy.db"
    with sqlite3.connect(db_path):
        pass

    summary = summarize_llm_usage(db_path, run_id="legacy")

    assert summary["available"] is False
    assert summary["reason"] == "llm_usage_events_missing"


def test_summarize_harness_usage_groups_exact_provider_counts(tmp_path) -> None:
    checkpoint = tmp_path / ".checkpoint.jsonl"
    rows = [
        {
            "arm": "no_memory",
            "result": {
                "raw_usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 2,
                    "total_tokens": 12,
                }
            },
        },
        {
            "arm": "menhir_recall",
            "result": {
                "raw_usage": {
                    "prompt_tokens": 20,
                    "completion_tokens": 3,
                    "total_tokens": 23,
                    "prompt_tokens_details": {"cached_tokens": 4},
                    "completion_tokens_details": {"reasoning_tokens": 1},
                },
                "scorer_raw_usage": {
                    "prompt_tokens": 7,
                    "completion_tokens": 1,
                    "total_tokens": 8,
                },
            },
        },
    ]
    checkpoint.write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n",
        encoding="utf-8",
    )

    summary = summarize_harness_usage(checkpoint)

    assert summary["available"] is True
    assert summary["calls"] == 3
    assert summary["input_tokens"] == 37
    assert summary["output_tokens"] == 6
    assert summary["total_tokens"] == 43
    assert summary["cached_input_tokens"] == 4
    assert summary["reasoning_output_tokens"] == 1
    assert [row["arm"] for row in summary["by_arm"]] == [
        "menhir_recall",
        "no_memory",
    ]
    assert [row["operation"] for row in summary["by_operation"]] == [
        "answer",
        "judge",
    ]


def test_summarize_harness_usage_marks_required_missing_judge_usage(tmp_path) -> None:
    checkpoint = tmp_path / ".checkpoint.jsonl"
    checkpoint.write_text(
        json.dumps(
            {
                "arm": "menhir_recall",
                "result": {
                    "raw_usage": {
                        "prompt_tokens": 10,
                        "completion_tokens": 2,
                        "total_tokens": 12,
                    }
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    summary = summarize_harness_usage(checkpoint, require_judge_usage=True)

    assert summary["calls"] == 2
    assert summary["missing_usage_calls"] == 1
    judge = next(row for row in summary["by_operation"] if row["operation"] == "judge")
    assert judge["calls"] == 1
    assert judge["missing_usage_calls"] == 1
