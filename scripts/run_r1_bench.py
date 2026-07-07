"""Run the menhir R1 hybrid-retrieval ladder over a fixture and emit an artifact.

Bench-first R1: compares the attributed hybrid path (vector + BM25, source-aware
floor) swept over hybrid_alpha against today's fused recall baseline, and prints
the win-gate verdict (does an alpha beat A on exact-string AND symbol recall
without regressing stale-hit / wrong-scope?).

Usage:
    python scripts/run_r1_bench.py [fixture_path] [--out results/r1_run.json] [--k 5]

Defaults to the bundled DEMO fixture (`fixtures/r1_demo.json`) and the deterministic
StubRetriever ladder, which runs anywhere/CI. The stub is a harness sanity device,
NOT a source of headline numbers — the real numbers come from the live run
(MenhirLiveRetriever against a throwaway Neo4j + an embedder; see
archolith_bench/r1/retriever.py and scripts/probe_rrf_scale.py for the seed
pattern). Grounding fixture support ids to extracted graph uuids is the owed
pairing step before the live numbers count.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from archolith_bench.r1.models import R1Fixture  # noqa: E402
from archolith_bench.r1.runner import R1BenchmarkRunner, build_stub_conditions  # noqa: E402

DEFAULT_FIXTURE = REPO_ROOT / "fixtures" / "r1_demo.json"
_METRIC_KEYS = (
    "recall_at_5",
    "exact_string_recall",
    "symbol_recall",
    "stale_hit_rate",
    "wrong_scope_injection_rate",
    "latency_ms",
)


def _print_table(artifact: dict) -> None:
    print(f"\n=== R1 ladder: {artifact['fixture']} ===")
    header = f"{'condition':16s} " + " ".join(f"{k[:12]:>12s}" for k in _METRIC_KEYS)
    print(header)
    for cond, result in artifact["conditions"].items():
        m = result["metrics"]
        row = f"{cond:16s} " + " ".join(f"{m[k]:>12.3f}" for k in _METRIC_KEYS)
        print(row)

    gate = artifact["win_gate"]
    verdict = "GRADUATES" if gate["graduates"] else "does not graduate"
    print(f"\n  win gate (E vs A_current): {verdict}")
    if gate["graduates"]:
        print(
            f"    recommended: {gate['recommended_condition']} "
            f"(hybrid_alpha={gate['recommended_hybrid_alpha']})"
        )
    print(f"    baseline A_current: {gate['baseline']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the R1 hybrid-retrieval ladder.")
    parser.add_argument("fixture", nargs="?", default=str(DEFAULT_FIXTURE), help="path to an R1 fixture JSON")
    parser.add_argument("--out", default="results/r1_run.json", help="where to write the JSON artifact")
    parser.add_argument("--k", type=int, default=5, help="top-k cutoff for metrics")
    args = parser.parse_args(argv)

    fixture_path = Path(args.fixture)
    if not fixture_path.exists():
        print(f"error: fixture not found: {fixture_path}", file=sys.stderr)
        return 1

    fixture = R1Fixture.from_file(fixture_path)
    conditions = build_stub_conditions(fixture)
    artifact = R1BenchmarkRunner(fixture, conditions, k=args.k).run()
    _print_table(artifact)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as handle:
        json.dump(artifact, handle, indent=2, sort_keys=True)
    print(f"\nwrote artifact: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
