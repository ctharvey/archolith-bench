"""Offline coverage for the one-task scalar viewer data model."""

from __future__ import annotations

import json
import sqlite3
from types import SimpleNamespace

from archolith_bench.dashboard import IngestSnapshot, RunSnapshot
from archolith_bench.scalar_viewer import (
    ScalarTaskReader,
    annotate_assertion_fold_outcomes,
    build_memory_inventory,
    catalog_with_graph_availability,
    scoring_rows,
    task_catalog,
)


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
        elif 'view_kind: "scalar_state"' in query:
            rows = [{
                "id": "view-25",
                "attribute": "postcard_count",
                "value": "25",
                "current": True,
                "contributor_ids": ["assert-25"],
            }]
        elif 'view_kind: "scalar_history"' in query:
            rows = [{
                "id": "hist-postcards",
                "view_key": "sh_abc123",
                "subject_uuid": "ent-postcards",
                "subject": "user",
                "attribute": "postcard_count",
                "scope": "collection",
                "value_kind": "count",
                "unit": "postcards",
                "entry_count": 2,
                "signature": "sig123",
                "op_counts": '{"delta": 2}',
                "first_valid_at": "2023-08-11T00:00:00+00:00",
                "last_valid_at": "2023-11-30T00:00:00+00:00",
                "payload": json.dumps([
                    {"assertion_id": "a1", "operation": "delta", "value": 17,
                     "valid_at": "2023-08-11T00:00:00+00:00",
                     "stated_span": "17 postcards since I started"},
                    {"assertion_id": "a2", "operation": "delta", "value": 25,
                     "valid_at": "2023-11-30T00:00:00+00:00",
                     "stated_span": "25 postcards since I started"},
                ]),
                "contributor_ids": ["assert-25"],
                "valid_at": "2023-11-30T00:00:00+00:00",
                "created_at": "2026-07-29T13:00:00Z",
                "current": True,
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
                "operation": "absolute",
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
    assert data["assertions"][0]["fold_outcome"] == {
        "state": {
            "status": "current",
            "reason": "contributes to the current scalar_state view",
        },
        "history": {
            "status": "recorded",
            "reason": "recorded in the current scalar_history view",
        },
    }
    assert data["views"][0]["current"] is True
    assert [(row["memory_type"], row["view_kind"], row["derivation"]) for row in data["memory_inventory"]] == [
        ("view", "scalar_state", "absolute"),
        ("view", "scalar_history", "delta"),
        ("content", None, None),
    ]
    # scalar_history View is returned alongside scalar_state
    assert len(data["history_views"]) == 1
    hv = data["history_views"][0]
    assert hv["id"] == "hist-postcards"
    assert hv["attribute"] == "postcard_count"
    assert hv["entry_count"] == 2
    assert hv["current"] is True
    # JSON payload was parsed into entries list
    assert len(hv["entries"]) == 2
    assert hv["entries"][0]["value"] == 17
    assert hv["entries"][1]["value"] == 25
    # op_counts JSON was parsed into dict
    assert hv["op_counts"] == {"delta": 2}
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


def test_catalog_keeps_manifest_tasks_that_are_not_yet_visible_in_graph():
    tasks = [
        {"namespace": "lme-ready", "question": "Ready?"},
        {"namespace": "lme-pending", "question": "Pending?"},
    ]

    catalog = catalog_with_graph_availability(tasks, {"lme-ready"})

    assert [task["namespace"] for task in catalog] == ["lme-ready", "lme-pending"]
    assert [task["graph_available"] for task in catalog] == [True, False]


def test_memory_inventory_distinguishes_content_and_view_derivation():
    assertions = [
        {"id": "a-abs", "operation": "absolute"},
        {"id": "a-delta", "operation": "delta"},
    ]
    views = [
        {
            "id": "view-absolute",
            "subject": "user",
            "attribute": "bike_count",
            "display": "3",
            "current": True,
            "contributor_ids": ["a-abs"],
        },
        {
            "id": "view-mixed",
            "subject": "user",
            "attribute": "postcard_count",
            "display": "25",
            "current": True,
            "contributor_ids": ["a-abs", "a-delta"],
        },
    ]
    history_views = [{
        "id": "history-delta",
        "subject": "user",
        "attribute": "postcard_count",
        "current": True,
        "op_counts": {"delta": 2},
    }]
    facts = [{
        "subject": "user",
        "relation": "OWNS",
        "object": "road bike",
        "fact": "User owns a road bike.",
        "episode_ids": ["episode-1"],
    }]

    inventory = build_memory_inventory(assertions, views, history_views, facts)

    assert [row["memory_type"] for row in inventory] == ["view", "view", "view", "content"]
    assert [row["derivation"] for row in inventory] == ["absolute", "mixed", "delta", None]
    assert inventory[-1]["content"] == "User owns a road bike."


def test_assertion_fold_outcomes_distinguish_current_pending_and_state_abstention():
    assertions = [
        {
            "id": "a-current",
            "subject_uuid": "user-1",
            "attribute": "followers",
            "scope": "",
            "value_kind": "count",
            "unit": "",
            "binding_pending": False,
            "superseded": False,
        },
        {
            "id": "a-pending",
            "subject_uuid": "unbound:a-pending",
            "attribute": "shoe_count",
            "scope": "",
            "value_kind": "count",
            "unit": "",
            "binding_pending": True,
            "superseded": False,
        },
        {
            "id": "a-delta",
            "subject_uuid": "user-1",
            "attribute": "postcards",
            "scope": "collection",
            "value_kind": "count",
            "unit": "",
            "binding_pending": False,
            "superseded": False,
        },
    ]
    views = [{"current": True, "contributor_ids": ["a-current"]}]
    history_views = [{
        "current": True,
        "contributor_ids": ["a-current", "a-delta"],
        "entries": [],
    }]
    audit = [{
        "event": "fold",
        "state": "abstain",
        "details": {
            "subject_uuid": "user-1",
            "slot": ["user-1", "postcards", "collection", "count", ""],
            "reason": "no_anchor",
        },
    }]

    annotated = annotate_assertion_fold_outcomes(assertions, views, history_views, audit)

    assert annotated[0]["fold_outcome"]["state"]["status"] == "current"
    assert annotated[0]["fold_outcome"]["history"]["status"] == "recorded"
    assert annotated[1]["fold_outcome"] == {
        "state": {"status": "not_folded", "reason": "subject binding is pending"},
        "history": {"status": "not_folded", "reason": "subject binding is pending"},
    }
    assert annotated[2]["fold_outcome"]["state"] == {
        "status": "abstained",
        "reason": "no_anchor",
    }
    assert annotated[2]["fold_outcome"]["history"]["status"] == "recorded"


class _DeltaOnlyDriver(_Driver):
    """Graph with delta-only postcards: scalar_state abstains, scalar_history materializes."""

    def execute_query(self, query, **kwargs):
        if 'view_kind: "scalar_state"' in query:
            return SimpleNamespace(records=[])  # state abstains: no anchor
        return super().execute_query(query, **kwargs)


def test_postcard_delta_only_state_abstains_history_materializes():
    """The postcard regression: scalar_state correctly abstains (no anchor),
    but scalar_history materializes the two delta entries in source-time order.
    The dashboard data model shows both projections' states correctly."""
    reader = ScalarTaskReader(
        neo4j_uri="bolt://unused",
        neo4j_user="neo4j",
        neo4j_password="unused",
        driver=_DeltaOnlyDriver(),
    )
    data = reader.read("lme-postcards")

    # scalar_state: abstained (empty — no anchor)
    assert data["views"] == []

    # scalar_history: materialized with two delta entries
    assert len(data["history_views"]) == 1
    hv = data["history_views"][0]
    assert hv["attribute"] == "postcard_count"
    assert hv["entry_count"] == 2
    assert hv["op_counts"] == {"delta": 2}

    # Entries are in source-time order
    entries = hv["entries"]
    assert entries[0]["valid_at"] == "2023-08-11T00:00:00+00:00"
    assert entries[0]["value"] == 17
    assert entries[0]["operation"] == "delta"
    assert entries[1]["valid_at"] == "2023-11-30T00:00:00+00:00"
    assert entries[1]["value"] == 25
    assert entries[1]["operation"] == "delta"

    # The answer is the latest delta (25), NOT the sum (42)
    latest = entries[-1]
    assert latest["value"] == 25
    assert latest["value"] != 42  # never compute a total from unanchored deltas

    # Source times are world/event times, not ingest times
    assert "2023-08-11" in entries[0]["valid_at"]
    assert "2023-11-30" in entries[1]["valid_at"]


def test_history_view_payload_parsing_handles_raw_json():
    """The reader correctly parses JSON payload and op_counts strings from Neo4j."""
    reader = ScalarTaskReader(
        neo4j_uri="bolt://unused",
        neo4j_user="neo4j",
        neo4j_password="unused",
        driver=_Driver(),
    )
    data = reader.read("lme-postcards")
    hv = data["history_views"][0]

    # payload (JSON string) → entries (list of dicts)
    assert isinstance(hv["entries"], list)
    assert all(isinstance(e, dict) for e in hv["entries"])

    # op_counts (JSON string) → dict
    assert isinstance(hv["op_counts"], dict)
    assert hv["op_counts"]["delta"] == 2
