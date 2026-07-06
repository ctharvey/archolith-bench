"""Gate (b) anchor-noise + hygiene sweep (menhir R2 Phase-4 viability).

Runs the facet ladder in HYBRID mode (menhir's real regime: structural facets from the
graph, interpretive from text) under three anchor regimes, calibrated to the measured
live-menhir profile (mean ~9 anchors/mem, ~75% text-unsupported, boilerplate magnets):

  1. clean          — hybrid mode as-is (structural facets trusted; F graduates today)
  2. +noise         — inject spurious over-anchoring (the real regime); expect F to collapse
  3. +noise+hygiene — inject, then filter (text_support / boilerplate / cap); measure recovery

Prints F's recall/wrong-scope/support + the promotion-gate verdict per regime, plus the
mean structural anchors/memory each transform produces. Answers: does F survive real anchor
noise, and does cheap ingest-side hygiene recover the structural win? Offline (stub embedder)
by default; pass --embedder openai for a real-embedding baseline.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from archolith_bench.facet.anchor_noise import (  # noqa: E402
    AnchorHygieneConfig,
    AnchorNoiseConfig,
    apply_anchor_hygiene,
    inject_anchor_noise,
)
from archolith_bench.facet.models import FacetFixture  # noqa: E402
from archolith_bench.facet.runner import FacetBenchmarkRunner  # noqa: E402

MODE = "hybrid"
_METRICS = ("recall_at_5", "wrong_scope_injection_rate", "support_sufficiency", "stale_hit_rate")


def _mean_anchors(memories) -> float:
    counts = [len(m.facets.file) + len(m.facets.symbol) for m in memories]
    return sum(counts) / len(counts) if counts else 0.0


def _run(fixture, embedder, transform) -> tuple[dict, dict, dict]:
    runner = FacetBenchmarkRunner(fixture, embedder=embedder, corpus_transform=transform)
    art = runner.run(include_traces=False)
    conds = art["modes"][MODE]
    return conds["F_facet_meet"]["metrics"], conds["A_bm25"]["metrics"], art["promotion_gate"][MODE]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixture", nargs="?", default=str(REPO_ROOT / "fixtures" / "facet_r2_draft.json"))
    parser.add_argument("--embedder", choices=["stub", "openai"], default="stub")
    parser.add_argument("--target-anchors", type=int, default=9)
    args = parser.parse_args(argv)

    embedder = None
    if args.embedder == "openai":
        from run_facet_bench import OpenAIEmbeddingScorer  # noqa: E402

        embedder = OpenAIEmbeddingScorer()

    fixture = FacetFixture.from_file(Path(args.fixture))

    def cfg(drop: float) -> AnchorNoiseConfig:
        return AnchorNoiseConfig(target_anchors=args.target_anchors, true_drop_frac=drop)

    def noise(drop: float):
        return lambda c: inject_anchor_noise(c, cfg(drop))

    def noise_then(drop: float, mode: str):
        hy = AnchorHygieneConfig(mode=mode)
        return lambda c: apply_anchor_hygiene(inject_anchor_noise(c, cfg(drop)), hy)

    # drop = fraction of the RIGHT answer's true anchors lost (scanner missed the link).
    # 0.0 = over-anchor only; 1.0 = all true structural gone (F falls back to scope-only).
    regimes: list[tuple[str, object]] = [
        ("clean", None),
        ("+noise drop=0.0", noise(0.0)),
        ("+noise drop=0.5", noise(0.5)),
        ("+noise drop=1.0", noise(1.0)),
        ("+noise0.5 +hy:text_support", noise_then(0.5, "text_support")),
        ("+noise0.5 +hy:boilerplate", noise_then(0.5, "boilerplate")),
        ("+noise0.5 +hy:cap", noise_then(0.5, "cap")),
    ]

    # Baseline anchor density (hybrid corpus before/after each transform).
    base_corpus = [FacetBenchmarkRunner(fixture)._corpus_for_mode(MODE)][0]

    print(f"fixture={Path(args.fixture).name} mode={MODE} embedder={args.embedder} "
          f"target_anchors={args.target_anchors}")
    print(f"clean hybrid corpus mean structural anchors/mem: {_mean_anchors(base_corpus):.1f}\n")
    header = f"{'regime':30s} {'anchors/mem':>11s} " + " ".join(f"{m[:12]:>13s}" for m in _METRICS) + f" {'gate':>10s}"
    print(header)
    print("-" * len(header))

    for name, transform in regimes:
        corpus = transform(base_corpus) if transform else base_corpus
        f_metrics, _a, gate = _run(fixture, embedder, transform)
        verdict = "GRAD" if gate["graduates"] else "no"
        row = f"{name:30s} {_mean_anchors(corpus):>11.1f} " + " ".join(
            f"{f_metrics[m]:>13.3f}" for m in _METRICS
        ) + f" {verdict:>10s}"
        print(row)

    print("\nrecall_at_5: higher better | wrong_scope_injection_rate: LOWER better | "
          "support_sufficiency: higher better")
    print("gate = F graduates vs BM25/embedding/hybrid baselines (>= parity recall + "
          "discipline improvement).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
