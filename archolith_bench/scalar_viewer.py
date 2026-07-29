"""Read-only data model for the dashboard's one-task scalar-state explorer."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


_EVIDENCE_QUERY = """
MATCH (t:TurnEvidence {namespace: $namespace})
OPTIONAL MATCH (t)-[:FOUNDS]->(a:TypedAssertion {namespace: $namespace})
RETURN t.turn_id AS id,
       coalesce(t.role, t.declarant, "unknown") AS role,
       t.text AS text,
       t.session_id AS session_id,
       toString(t.recorded_at) AS recorded_at,
       collect(DISTINCT a.assertion_id) AS founds
ORDER BY recorded_at, id
"""

_ASSERTIONS_QUERY = """
MATCH (a:TypedAssertion {namespace: $namespace})
RETURN a.assertion_id AS id,
       a.source_key AS source_key,
       a.episode_uuid AS evidence_id,
       a.subject_uuid AS subject_uuid,
       a.subject_display AS subject,
       a.attribute AS attribute,
       a.scope AS scope,
       a.value_kind AS value_kind,
       a.unit AS unit,
       a.operation AS operation,
       a.value AS value,
       a.stated_span AS stated_span,
       toString(a.valid_at) AS valid_at,
       toString(a.learned_at) AS learned_at,
       a.time_basis AS time_basis,
       a.evidence_tier AS evidence_tier,
       a.perceiver_version AS perceiver_version,
       coalesce(a.binding_pending, false) AS binding_pending,
       coalesce(a.superseded, false) AS superseded
ORDER BY valid_at, learned_at, id
"""

_VIEWS_QUERY = """
MATCH (v:Entity {group_id: $namespace, view_kind: "scalar_state"})
RETURN v.uuid AS id,
       v.view_key AS view_key,
       v.view_subject_uuid AS subject_uuid,
       v.view_subject AS subject,
       v.ss_attribute AS attribute,
       v.ss_scope AS scope,
       v.ss_kind AS value_kind,
       v.ss_unit AS unit,
       v.ss_value AS value,
       v.ss_display AS display,
       v.summary AS summary,
       toString(v.valid_at) AS valid_at,
       toString(v.created_at) AS created_at,
       coalesce(v.view_current, true) AS current,
       v.scalar_effective_tier AS effective_tier,
       coalesce(v.scalar_contributors, []) AS contributor_ids,
       v.supersedes AS supersedes,
       v.superseded_by AS superseded_by
ORDER BY valid_at, created_at, id
"""

_FACTS_QUERY = """
MATCH (s:Entity {group_id: $namespace})-[r]->(o:Entity {group_id: $namespace})
WHERE r.fact IS NOT NULL
RETURN s.name AS subject,
       type(r) AS relation,
       o.name AS object,
       r.fact AS fact,
       coalesce(r.episodes, []) AS episode_ids
ORDER BY coalesce(toString(r.valid_at), toString(r.created_at)), fact
LIMIT 40
"""

_AVAILABLE_NAMESPACES_QUERY = """
MATCH (t:TurnEvidence)
WHERE t.namespace IS NOT NULL
RETURN DISTINCT t.namespace AS namespace
ORDER BY namespace
"""


def task_catalog(ingests: list[Any]) -> list[dict[str, Any]]:
    """Return the latest manifest row for each namespace, newest manifest first."""
    by_namespace: dict[str, dict[str, Any]] = {}
    for ingest in ingests:
        for item in reversed(ingest.items):
            namespace = str(item.get("namespace") or "").strip()
            if not namespace or namespace in by_namespace:
                continue
            by_namespace[namespace] = {
                "namespace": namespace,
                "question_id": str(item.get("question_id") or ""),
                "question": str(item.get("question") or ""),
                "answer": str(item.get("answer") or ""),
                "question_type": str(item.get("question_type") or ""),
                "turns": int(item.get("turns") or 0),
                "ready": int(item.get("ready") or 0),
                "scalar_llm_calls": int(item.get("scalar_llm_calls") or 0),
                "typed_assertions": int(item.get("typed_assertions") or 0),
                "scalar_views": int(item.get("scalar_views") or 0),
            }
    return list(by_namespace.values())


def scoring_rows(snaps: list[Any], question_id: str) -> list[dict[str, Any]]:
    """Find any recall/answer checkpoint rows already written for one task."""
    out: list[dict[str, Any]] = []
    for snap in snaps:
        for item in snap.items:
            if str(item.get("task_id") or "") != question_id:
                continue
            out.append({
                "arm": item.get("arm"),
                "correct": bool(item.get("correct")),
                "response": item.get("resp") or "",
                "recalled": item.get("recalled") or "",
                "gold": item.get("gold") or "",
            })
    return out


class ScalarTaskReader:
    """Combine Neo4j scalar provenance with the optional SQLite vote receipt."""

    def __init__(
        self,
        *,
        neo4j_uri: str,
        neo4j_user: str,
        neo4j_password: str,
        telemetry_db: Path | None = None,
        driver: Any = None,
    ) -> None:
        if driver is None:
            try:
                from neo4j import GraphDatabase
            except ImportError as exc:  # pragma: no cover - depends on optional install
                raise RuntimeError(
                    "the scalar viewer needs the 'menhir-scalar' extra (neo4j driver)"
                ) from exc
            driver = GraphDatabase.driver(
                neo4j_uri,
                auth=(neo4j_user, neo4j_password),
            )
        self._driver = driver
        self.telemetry_db = Path(telemetry_db) if telemetry_db else None

    def close(self) -> None:
        close = getattr(self._driver, "close", None)
        if close:
            close()

    def _query(self, query: str, namespace: str) -> list[dict[str, Any]]:
        result = self._driver.execute_query(
            query,
            namespace=namespace,
            database_="neo4j",
            routing_="r",
        )
        return [dict(record) for record in result.records]

    def available_namespaces(self) -> set[str]:
        """Namespaces that have source evidence in the connected graph."""
        result = self._driver.execute_query(
            _AVAILABLE_NAMESPACES_QUERY,
            database_="neo4j",
            routing_="r",
        )
        return {
            str(record["namespace"])
            for record in result.records
            if record.get("namespace")
        }

    def _read_audit(
        self,
        namespace: str,
        assertions: list[dict[str, Any]],
    ) -> tuple[str | None, list[dict[str, Any]], str | None]:
        if self.telemetry_db is None:
            return None, [], "No telemetry DB was configured; k-sample vote receipts are unavailable."
        if not self.telemetry_db.exists():
            return None, [], f"Telemetry DB not found: {self.telemetry_db}"

        uri = f"{self.telemetry_db.resolve().as_uri()}?mode=ro"
        try:
            with sqlite3.connect(uri, uri=True, timeout=2.0) as conn:
                rows = conn.execute(
                    """
                    SELECT id, recorded_at, event, status, episode_uuid, details_json
                    FROM lifecycle_events
                    WHERE phase = 'consolidation_audit'
                      AND json_extract(details_json, '$.namespace') = ?
                    ORDER BY id
                    """,
                    (namespace,),
                ).fetchall()
        except (sqlite3.Error, OSError) as exc:
            return None, [], f"Could not read the telemetry vote receipt: {exc}"

        assertion_ids = {str(a.get("id") or "") for a in assertions}
        source_keys = {str(a.get("source_key") or "") for a in assertions}
        parsed: list[dict[str, Any]] = []
        relevant_passes: set[str] = set()
        pass_last_id: dict[str, int] = {}
        for row_id, at, event, state, pass_id, details_json in rows:
            try:
                details = json.loads(details_json or "{}")
            except (TypeError, ValueError):
                details = {"_raw": details_json}
            pid = str(pass_id or "")
            parsed.append({
                "id": int(row_id),
                "recorded_at": at,
                "event": event,
                "state": state,
                "pass_id": pid,
                "details": details,
            })
            pass_last_id[pid] = int(row_id)
            if (
                str(details.get("assertion_id") or "") in assertion_ids
                or str(details.get("source_key") or "") in source_keys
            ):
                relevant_passes.add(pid)

        if not relevant_passes:
            return None, [], (
                "Audit events exist for this namespace, but none match the assertions in this graph. "
                "The graph and telemetry may come from different benchmark attempts."
            )
        pass_id = max(relevant_passes, key=lambda pid: pass_last_id.get(pid, -1))
        events = [
            {
                "recorded_at": row["recorded_at"],
                "event": row["event"],
                "state": row["state"],
                "details": row["details"],
            }
            for row in parsed
            if row["pass_id"] == pass_id
        ]
        return pass_id, events, None

    def read(self, namespace: str) -> dict[str, Any]:
        """Read all stages for one namespace without mutating Neo4j or telemetry."""
        evidence = self._query(_EVIDENCE_QUERY, namespace)
        assertions = self._query(_ASSERTIONS_QUERY, namespace)
        views = self._query(_VIEWS_QUERY, namespace)
        facts = self._query(_FACTS_QUERY, namespace)
        audit_pass_id, audit, audit_warning = self._read_audit(namespace, assertions)
        return {
            "namespace": namespace,
            "evidence": evidence,
            "assertions": assertions,
            "views": views,
            "facts": facts,
            "audit_pass_id": audit_pass_id,
            "audit": audit,
            "audit_warning": audit_warning,
        }
