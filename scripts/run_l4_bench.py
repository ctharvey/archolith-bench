"""Run the L4 artifact-loop benchmark over a fixture and print the without/with_l4 table.

Bench-first: builds a ColdStartBrief v0 with and without the institutional artifacts and
scores it deterministically. The expected headline is `failed_approach_surfaced` and
`first_action_quality` flipping 0 -> 1 once the L4 Failure artifact is present.

Usage:
    python scripts/run_l4_bench.py [fixture_path] [--out results/l4_run.json]

Defaults to the bundled demo fixture (`fixtures/l4_failure_demo.json`).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from archolith_bench.l4.models import ArtifactFixture  # noqa: E402
from archolith_bench.l4.runner import CONDITIONS, METRIC_KEYS, run_l4_benchmark  # noqa: E402

DEFAULT_FIXTURE = REPO_ROOT / "fixtures" / "l4_failure_demo.json"


def _print_table(artifact: dict) -> None:
    print(f"\n=== L4 artifact loop: {artifact['fixture']} ===")
    for task in artifact["tasks"]:
        print(f"\ntask {task['task']}: {task['text']}")
        header = f"{'condition':12s} " + " ".join(f"{k[:13]:>13s}" for k in METRIC_KEYS)
        print(header)
        for cond in CONDITIONS:
            m = task["conditions"][cond]["metrics"]
            print(f"{cond:12s} " + " ".join(f"{m[k]:>13.3f}" for k in METRIC_KEYS))
        rec = task["conditions"]["with_l4"]["brief"]["recommended_first_action"]
        print(f"  with_l4 recommended first action: {rec}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the L4 artifact-loop benchmark over a fixture.")
    parser.add_argument("fixture", nargs="?", default=str(DEFAULT_FIXTURE), help="path to an L4 fixture JSON")
    parser.add_argument("--out", default="results/l4_run.json", help="where to write the full JSON artifact")
    args = parser.parse_args(argv)

    fixture_path = Path(args.fixture)
    if not fixture_path.exists():
        print(f"error: fixture not found: {fixture_path}", file=sys.stderr)
        return 1

    fixture = ArtifactFixture.from_file(fixture_path)
    artifact = run_l4_benchmark(fixture)
    _print_table(artifact)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as handle:
        json.dump(artifact, handle, indent=2, sort_keys=True)
    print(f"\nwrote artifact: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
