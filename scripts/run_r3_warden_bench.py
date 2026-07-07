"""Run the R3 Warden consolidation bench: the decide layer composed.

Shows each single warden (currentness / exhaustion / scope) only guards its own axis, while
the WardenChain catches every wrong candidate without over-blocking the safe one. Consumes
menhir.domain.warden.

Usage:
    PYTHONPATH=../menhir-frontier/src python scripts/run_r3_warden_bench.py [fixture.json]
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

from archolith_bench.r3.warden import WardenBenchRunner, WardenFixture  # noqa: E402

DEFAULT_FIXTURE = REPO_ROOT / "fixtures" / "r3_warden_chain.json"
_KEYS = ("refuse_recall", "admit_retention")


def _print_table(artifact: dict) -> None:
    print(f"\n=== R3 Warden consolidation: {artifact['fixture']} ===")
    print(f"{'condition':18s} " + " ".join(f"{k:>16s}" for k in _KEYS))
    for cond, res in artifact["conditions"].items():
        m = res["metrics"]
        print(f"{cond:18s} " + " ".join(f"{m[k]:>16.3f}" for k in _KEYS))
    gate = artifact["win_gate"]
    print(f"\n  win gate (chain vs single wardens): {'GRADUATES' if gate['graduates'] else 'does not graduate'}")
    print(f"    chain refuse_recall {gate.get('chain_refuse_recall')} > best single {gate.get('best_single_refuse_recall')}")
    print(f"    chain admit_retention {gate.get('chain_admit_retention')}  singles: {gate.get('singles')}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the R3 Warden consolidation bench.")
    parser.add_argument("fixture", nargs="?", default=str(DEFAULT_FIXTURE))
    parser.add_argument("--out", default="results/r3_warden_run.json")
    args = parser.parse_args(argv)

    fixture_path = Path(args.fixture)
    if not fixture_path.exists():
        print(f"error: fixture not found: {fixture_path}", file=sys.stderr)
        return 1

    artifact = WardenBenchRunner(WardenFixture.from_file(fixture_path)).run()
    _print_table(artifact)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as h:
        json.dump(artifact, h, indent=2, sort_keys=True)
    print(f"\nwrote artifact: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
