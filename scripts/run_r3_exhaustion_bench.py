"""Run the R3 rung-E exhaustion ladder over a session-trace fixture.

Replays a session (turns + progress events) under A_no_penalty vs E_exhaustion and
prints whether the exhaustion policy cuts loop injections without over-suppressing
productive/exempt memory. Consumes menhir.domain.exhaustion.

Usage:
    PYTHONPATH=../menhir-frontier/src python scripts/run_r3_exhaustion_bench.py [fixture.json]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MENHIR_FRONTIER_SRC = Path(r"C:\Users\thron\IdeaProjects\projects\archolith\menhir-frontier") / "src"
for p in (str(REPO_ROOT), str(MENHIR_FRONTIER_SRC)):
    if p not in sys.path:
        sys.path.insert(0, p)

from archolith_bench.r3.session import ExhaustionSessionRunner, SessionFixture  # noqa: E402

DEFAULT_FIXTURE = REPO_ROOT / "fixtures" / "r3_session_loop.json"
_KEYS = ("loop_injection_rate", "productive_retention", "exempt_retention")


def _print_table(artifact: dict) -> None:
    print(f"\n=== R3 exhaustion ladder: {artifact['fixture']} ===")
    print(f"{'condition':16s} " + " ".join(f"{k[:18]:>18s}" for k in _KEYS))
    for cond, res in artifact["conditions"].items():
        m = res["metrics"]
        print(f"{cond:16s} " + " ".join(f"{m[k]:>18.3f}" for k in _KEYS))
    gate = artifact["win_gate"]
    print(f"\n  win gate (E vs A_no_penalty): {'GRADUATES' if gate['graduates'] else 'does not graduate'}")
    print(f"    loop-injection cut: {gate.get('loop_injection_cut')}")
    print(f"    productive retention: {gate.get('productive_retention')}  exempt retention: {gate.get('exempt_retention')}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the R3 exhaustion (rung E) ladder.")
    parser.add_argument("fixture", nargs="?", default=str(DEFAULT_FIXTURE))
    parser.add_argument("--out", default="results/r3_exhaustion_run.json")
    args = parser.parse_args(argv)

    fixture_path = Path(args.fixture)
    if not fixture_path.exists():
        print(f"error: fixture not found: {fixture_path}", file=sys.stderr)
        return 1

    artifact = ExhaustionSessionRunner(SessionFixture.from_file(fixture_path)).run()
    _print_table(artifact)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as h:
        json.dump(artifact, h, indent=2, sort_keys=True)
    print(f"\nwrote artifact: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
