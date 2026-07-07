"""Run the R5 StructureTemporalOracle bench (time-aware blast radius).

Compares structure-only ranking vs the time-aware oracle and prints whether the oracle
surfaces the in-window-changed culprit where blind structure cannot. Consumes
menhir.domain.structure_temporal.

Usage:
    PYTHONPATH=../menhir-frontier/src python scripts/run_r5_bench.py [fixture.json]
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

from archolith_bench.r5.runner import R5BenchRunner, R5Fixture  # noqa: E402

DEFAULT_FIXTURE = REPO_ROOT / "fixtures" / "r5_seed_blast_radius.json"
_KEYS = ("culprit_at_1", "culprit_recall_at_k", "noise_at_1")


def _print_table(artifact: dict) -> None:
    print(f"\n=== R5 time-aware blast radius: {artifact['fixture']} (culprit={artifact['config']['culprit']}) ===")
    print(f"{'condition':22s} " + " ".join(f"{k:>20s}" for k in _KEYS))
    for cond, res in artifact["conditions"].items():
        m = res["metrics"]
        print(f"{cond:22s} " + " ".join(f"{m[k]:>20.3f}" for k in _KEYS))
    gate = artifact["win_gate"]
    print(f"\n  win gate (B vs A): {'GRADUATES' if gate['graduates'] else 'does not graduate'}")
    print(f"    culprit_at_1: {gate.get('culprit_at_1')}  noise_at_1: {gate.get('noise_at_1')}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the R5 StructureTemporalOracle bench.")
    parser.add_argument("fixture", nargs="?", default=str(DEFAULT_FIXTURE))
    parser.add_argument("--k", type=int, default=3)
    parser.add_argument("--out", default="results/r5_run.json")
    args = parser.parse_args(argv)

    fixture_path = Path(args.fixture)
    if not fixture_path.exists():
        print(f"error: fixture not found: {fixture_path}", file=sys.stderr)
        return 1

    artifact = R5BenchRunner(R5Fixture.from_file(fixture_path), k=args.k).run()
    _print_table(artifact)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as h:
        json.dump(artifact, h, indent=2, sort_keys=True)
    print(f"\nwrote artifact: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
