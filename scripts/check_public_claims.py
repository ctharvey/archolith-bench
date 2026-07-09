#!/usr/bin/env python3
"""CLI entrypoint for the offline public-claim scanner.

Usage:
    python scripts/check_public_claims.py
    python scripts/check_public_claims.py --headline HEADLINE-NUMBERS.md --scan README.md
    python scripts/check_public_claims.py --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from archolith_bench.core.public_claims import (
    DEFAULT_SCAN_PATHS,
    scan_public_claims,
)


def _resolve_headline() -> Path:
    candidates = [
        Path.cwd() / "HEADLINE-NUMBERS.md",
        Path(__file__).resolve().parent.parent / "HEADLINE-NUMBERS.md",
    ]
    for c in candidates:
        if c.exists():
            return c
    return candidates[0]


def _print_human(result) -> None:
    status = "PASS" if result.ok else "FAIL"
    print(f"Public claim scan: {status}")
    print(f"  files_scanned={result.files_scanned}")
    print(f"  claims_detected={result.claims_detected}")
    print(f"  unapproved_claims={len(result.unapproved_claims)}")

    if result.ignored_claims:
        print(f"  ignored_claims={len(result.ignored_claims)}")

    if result.unapproved_claims:
        print("\nErrors:")
        for c in result.unapproved_claims:
            print(f"  - {c.path}:{c.line}: \"{c.text}\" is not backed by HEADLINE-NUMBERS.md")


def _print_json(result) -> None:
    print(json.dumps({
        "ok": result.ok,
        "files_scanned": result.files_scanned,
        "claims_detected": result.claims_detected,
        "unapproved_claims": [
            {"path": c.path, "line": c.line, "text": c.text, "reason": c.reason}
            for c in result.unapproved_claims
        ],
        "ignored_claims": [
            {"path": c.path, "line": c.line, "text": c.text}
            for c in result.ignored_claims
        ],
    }, indent=2))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Scan public-facing docs for unapproved benchmark claims",
    )
    parser.add_argument("--headline", type=Path, default=None,
                        help="Path to HEADLINE-NUMBERS.md (auto-detected if omitted)")
    parser.add_argument("--scan", type=Path, action="append", default=None,
                        help="File or directory to scan (repeatable; defaults to README.md, "
                             "BENCHMARKS.md, docs/)")
    parser.add_argument("--json", action="store_true",
                        help="Emit machine-readable JSON output")
    parser.add_argument("--exclude", type=str, action="append", default=None,
                        help="Extra path exclusion pattern (repeatable)")

    args = parser.parse_args(argv)
    repo_root = Path.cwd()

    headline_path = args.headline or _resolve_headline()
    if not headline_path.exists():
        print(f"ERROR: headline file not found: {headline_path}", file=sys.stderr)
        sys.exit(2)

    if args.scan:
        scan_targets = args.scan
    else:
        scan_targets = [
            repo_root / p for p in DEFAULT_SCAN_PATHS
        ]

    extra_excludes: tuple[str, ...] = tuple(args.exclude) if args.exclude else ()

    result = scan_public_claims(
        headline_path, scan_targets,
        repo_root=repo_root,
        extra_excludes=extra_excludes,
    )

    if args.json:
        _print_json(result)
    else:
        _print_human(result)

    sys.exit(0 if result.ok else 1)


if __name__ == "__main__":
    main()
