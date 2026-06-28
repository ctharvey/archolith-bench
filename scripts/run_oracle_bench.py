"""Run the menhir R4-R7 oracle ladder over a fixture and emit a run artifact.

Bench-first: compares a single semantic signal (A) against a one-pass weighted
oracle sum (E) and the one-pass log-space role-logit combiner (F, the R7 killer
baseline), and prints the promotion-gate verdict.

Usage:
    python scripts/run_oracle_bench.py [fixture_path] [--out results/oracle_run.json] [--no-traces]

Defaults to the bundled DEMO fixture (`fixtures/oracle_demo.json`) — a
smoke/illustration corpus, not the benchmark fixture.

NOTE: the semantic oracle is a deterministic lexical stand-in, not a real embedding
model. Plug a real embedder before quoting A/E/F as an embedding comparison.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from archolith_bench.oracle.models import OracleFixture  # noqa: E402
from archolith_bench.oracle.runner import BASELINE_CONDITIONS, OracleBenchmarkRunner  # noqa: E402

DEFAULT_FIXTURE = REPO_ROOT / "fixtures" / "oracle_demo.json"


def _print_table(artifact: dict) -> None:
    metric_keys = ("recall_at_5", "mrr", "ndcg_at_5", "stale_hit_rate",
                   "wrong_scope_injection_rate", "current_truth_suppression_accuracy",
                   "historical_context_preservation", "ranking_determinism")
    print(f"\n=== oracle ladder: {artifact['fixture']} ===")
    header = f"{'condition':14s} " + " ".join(f"{k[:11]:>11s}" for k in metric_keys)
    print(header)
    for cond, result in artifact["conditions"].items():
        m = result["metrics"]
        print(f"{cond:14s} " + " ".join(f"{m[k]:>11.3f}" for k in metric_keys))
    gate = artifact["promotion_gate"]
    verdict = "GRADUATES" if gate["graduates"] else "does not graduate"
    print(f"\n  promotion gate (F vs {','.join(BASELINE_CONDITIONS)}): {verdict}")
    print(f"    improvements vs best baseline: {gate['improvements_vs_best_baseline']}")
    print(f"    recall loss: {gate['recall_loss']} (acceptable: {gate['recall_acceptable']})")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the R4-R7 oracle ladder over a fixture.")
    parser.add_argument("fixture", nargs="?", default=str(DEFAULT_FIXTURE), help="path to an oracle fixture JSON")
    parser.add_argument("--out", default="results/oracle_run.json", help="where to write the full JSON artifact")
    parser.add_argument("--no-traces", action="store_true", help="omit per-candidate packet traces from the artifact")
    args = parser.parse_args(argv)

    fixture_path = Path(args.fixture)
    if not fixture_path.exists():
        print(f"error: fixture not found: {fixture_path}", file=sys.stderr)
        return 1

    fixture = OracleFixture.from_file(fixture_path)
    artifact = OracleBenchmarkRunner(fixture).run(include_traces=not args.no_traces)
    _print_table(artifact)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as handle:
        json.dump(artifact, handle, indent=2, sort_keys=True)
    print(f"\nwrote artifact: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
