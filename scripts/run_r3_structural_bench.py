"""Run the R3 rung-F bounded-structural-expansion ladder over a graph fixture.

Compares semantic-only candidate generation vs semantic + bounded structural expansion,
and prints whether F surfaces the bug-relevant structural neighbor without unbounded
blow-up. Consumes menhir.domain.structural_expansion.

Usage:
    PYTHONPATH=../menhir-frontier/src python scripts/run_r3_structural_bench.py [fixture.json]
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

from archolith_bench.r3.structural import StructuralBenchRunner, StructuralFixture  # noqa: E402

DEFAULT_FIXTURE = REPO_ROOT / "fixtures" / "r3_structural_graph.json"
_KEYS = ("structural_neighbor_recall", "hub_kept_out", "pool_size")


def _print_table(artifact: dict) -> None:
    print(f"\n=== R3 structural-expansion ladder: {artifact['fixture']} ===")
    print(f"{'condition':22s} " + " ".join(f"{k[:22]:>22s}" for k in _KEYS))
    for cond, res in artifact["conditions"].items():
        m = res["metrics"]
        print(f"{cond:22s} " + " ".join(f"{m[k]:>22.3f}" for k in _KEYS))
    gate = artifact["win_gate"]
    print(f"\n  win gate (F vs A_semantic_only): {'GRADUATES' if gate['graduates'] else 'does not graduate'}")
    print(f"    recall gain: {gate.get('recall_gain')}  hub_kept_out: {gate.get('hub_kept_out')}")
    print(f"    pool_size {gate.get('pool_size')} <= bound {gate.get('pool_bound')}: {gate.get('bounded')}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the R3 structural-expansion (rung F) ladder.")
    parser.add_argument("fixture", nargs="?", default=str(DEFAULT_FIXTURE))
    parser.add_argument("--out", default="results/r3_structural_run.json")
    args = parser.parse_args(argv)

    fixture_path = Path(args.fixture)
    if not fixture_path.exists():
        print(f"error: fixture not found: {fixture_path}", file=sys.stderr)
        return 1

    artifact = StructuralBenchRunner(StructuralFixture.from_file(fixture_path)).run()
    _print_table(artifact)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as h:
        json.dump(artifact, h, indent=2, sort_keys=True)
    print(f"\nwrote artifact: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
