"""Run the menhir IntentOracle benchmark (Phase 4) over an intent fixture.

Four arms over ONE topic so any change in the top artifact is attributable to task
intent, not topic:

    baseline    semantic-only (no task intent)
    intent_on   default oracles + IntentOracle through the log-space combiner
    shuffle     intent_on with a deliberately WRONG intent (mean over all wrong intents)
    no_harm     orientation queries; intent_on nDCG must not drop below baseline

Usage:
    python scripts/run_intent_bench.py [fixture_path] [--out results/intent_run.json]

Defaults to fixtures/intent_floor_corpus.json. The semantic oracle is a deterministic
lexical stand-in; swap a real embedder before quoting absolute numbers.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from archolith_bench.intent.models import IntentFixture  # noqa: E402
from archolith_bench.intent.runner import IntentBenchmarkRunner  # noqa: E402
from archolith_bench.intent.validate import has_errors, validate_intent_fixture  # noqa: E402

DEFAULT_FIXTURE = REPO_ROOT / "fixtures" / "intent_floor_corpus.json"


def _print_report(art: dict) -> None:
    ic = art["intent_correct_at_1"]
    nh = art["no_harm_ndcg_at_5"]
    gate = art["promotion_gate"]
    print(f"\n=== intent ladder: {art['fixture']} ===")
    print(f"  intent-correct@1   baseline={ic['baseline']:.3f}  "
          f"intent_on={ic['intent_on']:.3f}  shuffle={ic['shuffle_ablation']:.3f}")
    print(f"  no-harm nDCG@5     no_intent={nh['no_intent']:.3f}  intent_on={nh['intent_on']:.3f} (n={nh['n']})")
    print(f"  determinism        {art['determinism']:.1f}")
    print("\n  per-query (true intent -> intent_on top / baseline top):")
    for d in art["per_query"]:
        flag = "OK " if d["intent_correct"] else "-- "
        print(f"    {flag}{d['query_id']:11s} {d['true_intent']:18s} "
              f"on={d['intent_top']:16s} base={d['baseline_top']:16s} shuffle={d['shuffle_correct']:.2f}")
    verdict = "GRADUATES" if gate["graduates"] else "does not graduate"
    print(f"\n  promotion gate: {verdict}")
    print(f"    intent beats baseline: {gate['intent_beats_baseline']} (lift {gate['lift_vs_baseline']:+.3f})")
    print(f"    shuffle collapses:     {gate['shuffle_collapses']} "
          f"(lift vs shuffle {gate['lift_vs_shuffle']:+.3f}, margin {gate['shuffle_margin']})")
    print(f"    no-harm holds:         {gate['no_harm_holds']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the IntentOracle benchmark over a fixture.")
    parser.add_argument("fixture", nargs="?", default=str(DEFAULT_FIXTURE))
    parser.add_argument("--out", default="results/intent_run.json")
    parser.add_argument("--scorer", choices=("lexical", "lmstudio", "openai"), default="lexical",
                        help="semantic backend: lexical stand-in (default), LM Studio, or OpenAI")
    args = parser.parse_args(argv)

    fixture_path = Path(args.fixture)
    if not fixture_path.exists():
        print(f"error: fixture not found: {fixture_path}", file=sys.stderr)
        return 1

    fixture = IntentFixture.from_file(fixture_path)

    findings = validate_intent_fixture(fixture)
    if findings:
        print(f"\n=== fixture validation: {len(findings)} finding(s) ===")
        for f in findings:
            print(" ", f)
        if has_errors(findings):
            print("\nerror: fixture has validation errors — results are not trustworthy", file=sys.stderr)
            return 1

    scorer = None
    if args.scorer != "lexical":
        from archolith_bench.intent.embedder import (
            EmbedderUnavailable,
            LMStudioEmbeddingScorer,
            OpenAIEmbeddingScorer,
        )
        scorer = LMStudioEmbeddingScorer() if args.scorer == "lmstudio" else OpenAIEmbeddingScorer()
        try:
            scorer.similarity("warmup", "warmup")  # fail loudly now, not mid-run
        except EmbedderUnavailable as exc:
            print(f"error: --scorer {args.scorer} requested but {exc}", file=sys.stderr)
            return 1
        print(f"semantic scorer: {scorer.name}")

    artifact = IntentBenchmarkRunner(fixture, semantic_scorer=scorer).run()
    _print_report(artifact)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as handle:
        json.dump(artifact, handle, indent=2, sort_keys=True)
    print(f"\nwrote artifact: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
