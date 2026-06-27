"""Run the menhir R2 facet ladder over a fixture and emit a run artifact.

Bench-first R2: compares facet-first candidate generation + meet-point reranking
against honest baselines (BM25 / embedding / hybrid / file-context), in both gold
and extracted facet modes, and prints the promotion-gate verdict.

Usage:
    python scripts/run_facet_bench.py [fixture_path] [--out results/facet_run.json] [--no-traces]

Defaults to the bundled DEMO fixture (`fixtures/facet_demo.json`). The demo is a
smoke/illustration corpus, not the benchmark fixture — see the fixture's own
description and `.agent/benchmark-notes/facet-r2-demo-run.md`.

NOTE: the default embedding condition is a deterministic lexical stand-in
(`LexicalEmbeddingStub`), not a real embedding model. Plug a real
`EmbeddingScorer` before quoting conditions B/C/E as an embedding comparison.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from archolith_bench.facet.models import FacetFixture  # noqa: E402
from archolith_bench.facet.runner import BASELINE_CONDITIONS, FacetBenchmarkRunner  # noqa: E402

DEFAULT_FIXTURE = REPO_ROOT / "fixtures" / "facet_demo.json"


def _print_table(artifact: dict) -> None:
    metric_keys = ("recall_at_5", "precision_at_5", "mrr", "ndcg_at_5", "stale_hit_rate",
                   "wrong_scope_injection_rate", "support_sufficiency", "false_neighbor_rate",
                   "paraphrase_stability")
    for mode, conditions in artifact["modes"].items():
        print(f"\n=== facet mode: {mode} ===")
        header = f"{'condition':16s} " + " ".join(f"{k[:10]:>10s}" for k in metric_keys)
        print(header)
        for cond, result in conditions.items():
            metrics = result["metrics"]
            row = f"{cond:16s} " + " ".join(f"{metrics[k]:>10.3f}" for k in metric_keys)
            print(row)
        gate = artifact["promotion_gate"][mode]
        verdict = "GRADUATES" if gate["graduates"] else "does not graduate"
        print(f"  promotion gate (F vs {','.join(BASELINE_CONDITIONS)}): {verdict}")
        print(f"    improvements vs best baseline: {gate['improvements_vs_best_baseline']}")
        print(f"    recall loss: {gate['recall_loss']} (acceptable: {gate['recall_acceptable']})")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the R2 facet ladder over a fixture.")
    parser.add_argument("fixture", nargs="?", default=str(DEFAULT_FIXTURE), help="path to a facet fixture JSON")
    parser.add_argument("--out", default="results/facet_run.json", help="where to write the full JSON artifact")
    parser.add_argument("--no-traces", action="store_true", help="omit per-candidate explanation traces from the artifact")
    args = parser.parse_args(argv)

    fixture_path = Path(args.fixture)
    if not fixture_path.exists():
        print(f"error: fixture not found: {fixture_path}", file=sys.stderr)
        return 1

    fixture = FacetFixture.from_file(fixture_path)
    artifact = FacetBenchmarkRunner(fixture).run(include_traces=not args.no_traces)
    _print_table(artifact)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as handle:
        json.dump(artifact, handle, indent=2, sort_keys=True)
    print(f"\nwrote artifact: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
