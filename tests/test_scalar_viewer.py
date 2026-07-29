"""Offline coverage for the one-task scalar viewer data model."""

from __future__ import annotations

import json
import sqlite3
from types import SimpleNamespace

from archolith_bench.dashboard import IngestSnapshot, RunSnapshot
from archolith_bench.scalar_viewer import ScalarTaskReader, scoring_rows, task_catalog


class _Driver:
    def __init__(self):
        self.closed = False

    def execute_query(self, query, **_kwargs):
        if "RETURN DISTINCT t.namespace" in query:
            rows = [{"namespace": "lme-postcards"}, {"namespace": "lme-other"}]
        elif "TurnEvidence" in query:
            rows = [{
                "id": "turn-25",
                "role": "user",
                "text": "I have added 25 postcards.",
                "session_id": "s2",
                "occurred_at": "2023-11-30T20:25:00Z",
                "recorded_at": "2026-07-29T13:00:00Z",
                "founds": ["assert-25"],
            }]
        elif "TypedAssertion" in query:
            rows = [{
                "id": "assert-25",
                "source_key": "source-25",
                "evidence_id": "turn-25",
                "subject": "user",
                "attribute": "postcard_count",
                "value": "25",
                "unit": "",
            }]
        elif 'view_kind: "scalar_state"' in query:
            rows = [{
                "id": "view-25",
                "attribute": "postcard_count",
                "value": "25",
                "current": True,
                "contributor_ids": ["assert-25"],
            }]
        else:
            rows = [{"subject": "user", "object": "postcards", "fact": "User collects postcards."}]
        return SimpleNamespace(records=rows)

    def close(self):
        self.closed = True


def _telemetry(path):
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE lifecycle_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recorded_at TEXT NOT NULL,
                phase TEXT NOT NULL,
                event TEXT NOT NULL,
                status TEXT NOT NULL,
                episode_uuid TEXT,
                details_json TEXT
            )
            """
        )
        rows = [
            (
                "2026-07-29T13:00:01Z",
                "gate",
                "commit",
                "cap-matching",
                {
                    "namespace": "lme-postcards",
                    "source_key": "source-25",
                    "agreement": 2 / 3,
                    "k": 3,
                    "distribution": {"count||absolute|25|": 2, "(absent)": 1},
                },
            ),
            (
                "2026-07-29T13:00:02Z",
                "perceive",
                "bound",
                "cap-matching",
                {
                    "namespace": "lme-postcards",
                    "assertion_id": "assert-25",
                    "source_key": "source-25",
                },
            ),
            # A newer pass for the same namespace belongs to another graph attempt. It must
            # not replace the receipt correlated to the assertion actually read from Neo4j.
            (
                "2026-07-29T14:00:01Z",
                "gate",
                "commit",
                "cap-other-graph",
                {
                    "namespace": "lme-postcards",
                    "source_key": "different-source",
                    "agreement": 1.0,
                    "k": 3,
                },
            ),
        ]
        conn.executemany(
            """
            INSERT INTO lifecycle_events
              (recorded_at, phase, event, status, episode_uuid, details_json)
            VALUES (?, 'consolidation_audit', ?, ?, ?, ?)
            """,
            [(at, event, state, pass_id, json.dumps(details))
             for at, event, state, pass_id, details in rows],
        )


def test_reader_correlates_vote_receipt_to_graph_assertions(tmp_path):
    db = tmp_path / "telemetry.db"
    _telemetry(db)
    driver = _Driver()
    reader = ScalarTaskReader(
        neo4j_uri="bolt://unused",
        neo4j_user="neo4j",
        neo4j_password="unused",
        telemetry_db=db,
        driver=driver,
    )

    data = reader.read("lme-postcards")

    assert data["evidence"][0]["founds"] == ["assert-25"]
    assert data["evidence"][0]["occurred_at"] == "2023-11-30T20:25:00Z"
    assert data["evidence"][0]["recorded_at"] == "2026-07-29T13:00:00Z"
    assert data["assertions"][0]["value"] == "25"
    assert data["views"][0]["current"] is True
    assert data["audit_pass_id"] == "cap-matching"
    assert [event["event"] for event in data["audit"]] == ["gate", "perceive"]
    assert data["audit"][0]["details"]["agreement"] == 2 / 3
    assert data["audit_warning"] is None
    assert reader.available_namespaces() == {"lme-postcards", "lme-other"}
    reader.close()
    assert driver.closed is True


def test_reader_explains_missing_telemetry_without_hiding_graph():
    reader = ScalarTaskReader(
        neo4j_uri="bolt://unused",
        neo4j_user="neo4j",
        neo4j_password="unused",
        driver=_Driver(),
    )

    data = reader.read("lme-postcards")

    assert data["views"]
    assert data["audit"] == []
    assert "No telemetry DB" in data["audit_warning"]


def test_task_catalog_and_scoring_rows():
    ingest = IngestSnapshot(
        manifest=None,
        source="candidate",
        items=[{
            "namespace": "lme-postcards",
            "question_id": "postcards",
            "question": "How many?",
            "answer": "25",
            "typed_assertions": 2,
        }],
    )
    run = RunSnapshot(
        checkpoint=None,
        benchmark="longmemeval",
        variant="candidate",
        model="answerer",
        items=[{
            "task_id": "postcards",
            "arm": "menhir_recall",
            "correct": True,
            "resp": "25",
            "recalled": "postcard count = 25",
            "gold": "25",
        }],
    )

    assert task_catalog([ingest])[0]["typed_assertions"] == 2
    assert scoring_rows([run], "postcards") == [{
        "arm": "menhir_recall",
        "correct": True,
        "response": "25",
        "recalled": "postcard count = 25",
        "gold": "25",
    }]
