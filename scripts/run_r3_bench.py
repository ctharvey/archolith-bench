"""Run the menhir R3 belief-currentness ladder over a fixture and emit an artifact.

Compares assert-all (baseline) vs Rung-0 belief buckets vs the intent-aware
currentness policy, and prints whether D cuts stale-current assertions without
losing historical context.

Usage:
    python scripts/run_r3_bench.py [fixture.json] [--out results/r3_run.json]

Defaults to the bundled DEMO fixture (`fixtures/r3_ce_willow.json`). Consumes
menhir's real belief domain — put menhir-frontier/src on PYTHONPATH:
    PYTHONPATH=../menhir-frontier/src python scripts/run_r3_bench.py
The demo is a harness sanity check; the real fixture families are owed.
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

from archolith_bench.r3.models import BeliefFixture  # noqa: E402
from archolith_bench.r3.runner import R3BenchmarkRunner  # noqa: E402

DEFAULT_FIXTURE = REPO_ROOT / "fixtures" / "r3_ce_willow.json"
_KEYS = ("stale_current_assertion_rate", "poisoned_context_injection_rate", "historical_context_preservation", "asserted_count", "surfaced_count")


def _print_table(artifact: dict) -> None:
    print(f"\n=== R3 belief-currentness ladder: {artifact['fixture']} (intent={artifact['intent']}) ===")
    print(f"{'condition':18s} " + " ".join(f"{k[:14]:>14s}" for k in _KEYS))
    for cond, res in artifact["conditions"].items():
        m = res["metrics"]
        print(f"{cond:18s} " + " ".join(f"{m[k]:>14.3f}" for k in _KEYS))
    gate = artifact["win_gate"]
    print(f"\n  win gate (D vs A_assert_all): {'GRADUATES' if gate['graduates'] else 'does not graduate'}")
    print(f"    stale-current assertion cut: {gate.get('stale_current_assertion_cut')}")
    print(f"    historical preservation loss: {gate.get('historical_preservation_loss')}")
    print(f"    poisoned injection cut: {gate.get('poisoned_injection_cut')}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the R3 belief-currentness ladder.")
    parser.add_argument("fixture", nargs="?", default=str(DEFAULT_FIXTURE))
    parser.add_argument("--out", default="results/r3_run.json")
    args = parser.parse_args(argv)

    fixture_path = Path(args.fixture)
    if not fixture_path.exists():
        print(f"error: fixture not found: {fixture_path}", file=sys.stderr)
        return 1

    fixture = BeliefFixture.from_file(fixture_path)
    artifact = R3BenchmarkRunner(fixture).run()
    _print_table(artifact)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as handle:
        json.dump(artifact, handle, indent=2, sort_keys=True)
    print(f"\nwrote artifact: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
