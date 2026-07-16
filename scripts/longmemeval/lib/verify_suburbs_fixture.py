"""Verify the isolated LongMemEval suburbs-ingestion regression fixture."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

BENCH_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_FIXTURE = (
    BENCH_ROOT
    / "fixtures"
    / "longmemeval"
    / "menhir_suburbs_extraction_regression.json"
)


def _load_contract(path: Path) -> dict[str, Any]:
    items = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(items, list) or len(items) != 1:
        raise ValueError("fixture must contain exactly one LongMemEval item")

    item = items[0]
    expectations = item.get("fixture_expectations")
    if not isinstance(expectations, dict):
        raise ValueError("fixture item is missing fixture_expectations")

    question_id = str(item.get("question_id") or "")
    namespace = str(expectations.get("namespace") or "")
    if not question_id or namespace != f"lme-{question_id}":
        raise ValueError("fixture namespace must equal lme-<question_id>")

    turns = sum(
        1
        for session in item.get("haystack_sessions") or []
        for turn in session
        if str(turn.get("content") or "").strip()
    )
    minimum_turns = int(expectations.get("minimum_turns") or 0)
    if turns < minimum_turns:
        raise ValueError(f"fixture has {turns} turns; expected at least {minimum_turns}")

    required = (
        "subject",
        "current_object_contains",
        "stale_object",
        "required_current_fact_contains",
        "required_menhir_commit",
    )
    missing = [key for key in required if not str(expectations.get(key) or "").strip()]
    if missing:
        raise ValueError(f"fixture expectations missing: {', '.join(missing)}")

    return {
        "question_id": question_id,
        "namespace": namespace,
        "turns": turns,
        **{key: str(expectations[key]) for key in required},
    }


def _cypher_literal(value: str) -> str:
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


def _cypher_count(container: str, password: str, query: str) -> int:
    proc = subprocess.run(
        [
            "docker",
            "exec",
            container,
            "cypher-shell",
            "-u",
            "neo4j",
            "-p",
            password,
            "--format",
            "plain",
            query,
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip()
        raise RuntimeError(f"cypher-shell failed: {detail}")
    for line in reversed(proc.stdout.splitlines()):
        value = line.strip().strip('"')
        if re.fullmatch(r"\d+", value):
            return int(value)
    raise RuntimeError(f"cypher-shell returned no scalar count: {proc.stdout!r}")


def _menhir_contains_commit(menhir_root: Path, commit: str) -> bool:
    proc = subprocess.run(
        ["git", "-C", str(menhir_root), "merge-base", "--is-ancestor", commit, "HEAD"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    return proc.returncode == 0


def _graph_counts(contract: dict[str, Any], container: str, password: str) -> dict[str, int]:
    namespace = _cypher_literal(contract["namespace"])
    subject = _cypher_literal(contract["subject"].lower())
    current_object = _cypher_literal(contract["current_object_contains"].lower())
    stale_object = _cypher_literal(contract["stale_object"].lower())
    current_fact = _cypher_literal(contract["required_current_fact_contains"].lower())

    base_current = (
        f"MATCH (subject:Entity {{group_id: {namespace}}})"
        f"-[edge:RELATES_TO]-(place:Entity {{group_id: {namespace}}}) "
        f"WHERE toLower(subject.name) = {subject} "
        f"AND toLower(place.name) CONTAINS {current_object} "
        f"AND toLower(coalesce(edge.fact, '')) CONTAINS {current_fact} "
    )
    base_stale = (
        f"MATCH (subject:Entity {{group_id: {namespace}}})"
        f"-[edge:RELATES_TO]-(place:Entity {{group_id: {namespace}}}) "
        f"WHERE toLower(subject.name) = {subject} "
        f"AND toLower(place.name) = {stale_object} "
    )

    queries = {
        "suburb_entities": (
            f"MATCH (place:Entity {{group_id: {namespace}}}) "
            f"WHERE toLower(place.name) CONTAINS {current_object} RETURN count(place)"
        ),
        "current_suburb_edges": (
            base_current
            + "AND edge.invalid_at IS NULL AND edge.expired_at IS NULL RETURN count(edge)"
        ),
        "expired_stale_edges": (
            base_stale
            + "AND (edge.invalid_at IS NOT NULL OR edge.expired_at IS NOT NULL) RETURN count(edge)"
        ),
        "current_stale_edges": (
            base_stale
            + "AND edge.invalid_at IS NULL AND edge.expired_at IS NULL RETURN count(edge)"
        ),
        "target_episodes": (
            f"MATCH (episode:Episodic {{group_id: {namespace}}}) "
            f"WHERE toLower(coalesce(episode.content, '')) CONTAINS {current_object} "
            "RETURN count(episode)"
        ),
    }
    return {
        name: _cypher_count(container, password, query)
        for name, query in queries.items()
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--menhir-root", type=Path, required=True)
    parser.add_argument("--container", default=os.getenv("LME_NEO4J_NAME", ""))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args(argv)

    contract = _load_contract(args.fixture.resolve())
    commit_ok = _menhir_contains_commit(
        args.menhir_root.resolve(),
        contract["required_menhir_commit"],
    )
    if not commit_ok:
        raise SystemExit(
            "configured Menhir checkout does not contain the required combined-extraction fix "
            f"{contract['required_menhir_commit']}"
        )

    if args.preflight_only:
        print(json.dumps({"passed": True, "contract": contract}, indent=2))
        return 0

    password = os.getenv("LME_NEO4J_PW", "")
    if not args.container or not password:
        raise SystemExit("LME_NEO4J_NAME and LME_NEO4J_PW are required for graph verification")

    counts = _graph_counts(contract, args.container, password)
    passed = (
        counts["suburb_entities"] >= 1
        and counts["current_suburb_edges"] >= 1
        and counts["expired_stale_edges"] >= 1
        and counts["current_stale_edges"] == 0
        and counts["target_episodes"] >= 1
    )
    result = {
        "passed": passed,
        "fixture": str(args.fixture.resolve()),
        "container": args.container,
        "contract": contract,
        "counts": counts,
    }
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
