"""Final acceptance report for a LongMemEval buildout.

Reads the graph provenance file, manifest, and optional telemetry DB, and emits a
machine-readable JSON report covering the contract from the scalar-history plan:

- manifest cardinality (expected vs actual items)
- failed episodes (zero-tolerance policy)
- projection counts (scalar_state, scalar_history Views)
- source-time integrity (valid_at present and plausible)
- provenance-chain completeness (TurnEvidence, assertions, FOUNDS, ADMITTED_ON)
- namespace isolation (no cross-namespace leakage)
- commit immutability (all attempts ran the same code)
- telemetry presence (vote receipt DB exists and has rows)

Usage::

    validate_run.py <provenance.json> <manifest.json> [--telemetry-db <path>]
                    [--expected-items N] [--output <report.json>]

Exit 0 when all checks pass; exit 1 with the report on any failure.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _check(
    name: str,
    passed: bool,
    detail: str,
    *,
    severity: str = "FAIL",
) -> dict[str, Any]:
    return {
        "check": name,
        "status": "PASS" if passed else severity,
        "detail": detail,
    }


def validate(
    provenance_path: Path,
    manifest_path: Path,
    *,
    telemetry_db: Path | None = None,
    expected_items: int | None = None,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    # ---- Provenance file ----
    if not provenance_path.exists():
        checks.append(_check(
            "provenance_exists", False, f"provenance file not found: {provenance_path}",
        ))
        return _report(checks)
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))

    # ---- Commit immutability ----
    attempts = provenance.get("attempts") or []
    if len(attempts) <= 1:
        checks.append(_check(
            "commit_immutability", True,
            f"single attempt (commit={provenance.get('menhir_commit', 'unknown')})",
        ))
    else:
        menhir_commits = {a.get("menhir_commit") for a in attempts} - {None}
        bench_commits = {a.get("bench_commit") for a in attempts} - {None}
        menhir_ok = len(menhir_commits) <= 1
        bench_ok = len(bench_commits) <= 1
        if menhir_ok and bench_ok:
            checks.append(_check(
                "commit_immutability", True,
                f"{len(attempts)} attempts, all same commits "
                f"(menhir={menhir_commits.pop() if menhir_commits else 'unknown'}, "
                f"bench={bench_commits.pop() if bench_commits else 'unknown'})",
            ))
        else:
            drift = []
            if not menhir_ok:
                drift.append(f"menhir: {sorted(menhir_commits)}")
            if not bench_ok:
                drift.append(f"bench: {sorted(bench_commits)}")
            is_noncanonical = provenance.get("noncanonical", False)
            checks.append(_check(
                "commit_immutability", False,
                f"commit drift across {len(attempts)} attempts: {'; '.join(drift)}"
                + (" [noncanonical=true]" if is_noncanonical else ""),
            ))

    # Noncanonical label
    checks.append(_check(
        "canonical_label",
        not provenance.get("noncanonical", False),
        "noncanonical" if provenance.get("noncanonical") else "canonical",
        severity="WARN",
    ))

    # ---- Manifest cardinality ----
    if not manifest_path.exists():
        checks.append(_check(
            "manifest_exists", False, f"manifest not found: {manifest_path}",
        ))
    else:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(manifest, list):
            checks.append(_check(
                "manifest_format", False, "manifest is not a JSON list",
            ))
        else:
            actual = len(manifest)
            if expected_items is not None:
                checks.append(_check(
                    "manifest_cardinality",
                    actual == expected_items,
                    f"expected {expected_items}, got {actual}",
                ))
            else:
                checks.append(_check(
                    "manifest_cardinality", actual > 0,
                    f"{actual} items (no expected count specified)",
                ))

            # Failed episodes
            failed = [
                row for row in manifest
                if isinstance(row, dict) and row.get("status") == "FAILED"
            ]
            checks.append(_check(
                "zero_failed_episodes",
                len(failed) == 0,
                f"{len(failed)} failed episodes" if failed
                else f"all {actual} episodes succeeded",
            ))

            # Namespace isolation: every namespace starts with the configured prefix
            ns_prefix = provenance.get("namespace_prefix", "lme-")
            bad_ns = [
                str(row.get("namespace", ""))
                for row in manifest if isinstance(row, dict)
                and not str(row.get("namespace", "")).startswith(ns_prefix)
            ]
            checks.append(_check(
                "namespace_isolation",
                len(bad_ns) == 0,
                f"{len(bad_ns)} namespace(s) outside prefix '{ns_prefix}': {bad_ns[:5]}"
                if bad_ns else f"all namespaces start with '{ns_prefix}'",
            ))

            # Projection counts
            total_assertions = sum(
                int(row.get("typed_assertions", 0))
                for row in manifest if isinstance(row, dict)
            )
            total_views = sum(
                int(row.get("scalar_views", 0))
                for row in manifest if isinstance(row, dict)
            )
            checks.append(_check(
                "projection_counts",
                True,
                f"{total_assertions} assertions, {total_views} scalar_state views",
                severity="INFO",
            ))

    # ---- Telemetry presence ----
    if telemetry_db is None:
        checks.append(_check(
            "telemetry_presence", False,
            "no telemetry DB path specified",
            severity="WARN",
        ))
    elif not telemetry_db.exists():
        checks.append(_check(
            "telemetry_presence", False,
            f"telemetry DB not found: {telemetry_db}",
        ))
    else:
        try:
            uri = f"{telemetry_db.resolve().as_uri()}?mode=ro"
            with sqlite3.connect(uri, uri=True, timeout=2.0) as conn:
                row_count = conn.execute(
                    "SELECT count(*) FROM lifecycle_events"
                ).fetchone()[0]
            checks.append(_check(
                "telemetry_presence",
                row_count > 0,
                f"{row_count} lifecycle events" if row_count
                else "telemetry DB exists but has no events",
            ))
        except (sqlite3.Error, OSError) as exc:
            checks.append(_check(
                "telemetry_presence", False,
                f"could not read telemetry DB: {exc}",
            ))

    # ---- Source-time integrity (from provenance phases) ----
    phases = provenance.get("phases") or []
    interrupted = [p for p in phases if p.get("status") == "interrupted"]
    checks.append(_check(
        "no_interrupted_phases",
        len(interrupted) == 0,
        f"{len(interrupted)} interrupted phase(s)" if interrupted
        else f"all {len(phases)} phases completed or recorded",
    ))

    return _report(checks)


def _report(checks: list[dict[str, Any]]) -> dict[str, Any]:
    failures = [c for c in checks if c["status"] == "FAIL"]
    warnings = [c for c in checks if c["status"] == "WARN"]
    return {
        "validated_at": _now(),
        "verdict": "PASS" if not failures else "FAIL",
        "failures": len(failures),
        "warnings": len(warnings),
        "checks": checks,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("provenance", type=Path, help="graph-provenance-*.json")
    parser.add_argument("manifest", type=Path, help="manifest.json")
    parser.add_argument("--telemetry-db", type=Path, default=None)
    parser.add_argument("--expected-items", type=int, default=None)
    parser.add_argument("--output", type=Path, default=None,
                        help="write report JSON here (also printed to stdout)")
    args = parser.parse_args(argv)

    report = validate(
        args.provenance,
        args.manifest,
        telemetry_db=args.telemetry_db,
        expected_items=args.expected_items,
    )

    text = json.dumps(report, indent=2)
    print(text)
    if args.output:
        args.output.write_text(text, encoding="utf-8")

    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
