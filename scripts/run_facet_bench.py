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
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from archolith_bench.facet.models import FacetFixture  # noqa: E402
from archolith_bench.facet.runner import BASELINE_CONDITIONS, FacetBenchmarkRunner  # noqa: E402

DEFAULT_FIXTURE = REPO_ROOT / "fixtures" / "facet_demo.json"
MENHIR_ENV = Path(r"C:\Users\thron\IdeaProjects\projects\archolith\menhir\.env")


def _load_openai_key() -> str:
    """OPENAI_API_KEY from the env, falling back to menhir/.env."""
    key = os.environ.get("OPENAI_API_KEY")
    if not key and MENHIR_ENV.exists():
        from dotenv import dotenv_values

        key = dotenv_values(str(MENHIR_ENV)).get("OPENAI_API_KEY")
    if not key:
        raise SystemExit("--embedder openai needs OPENAI_API_KEY (env or menhir/.env)")
    return key


def _cosine(a: list[float], b: list[float]) -> float:
    import math

    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (na * nb)


class OpenAIEmbeddingScorer:
    """Real EmbeddingScorer: OpenAI text-embedding-3-small + cosine, cached by text.

    Implements the ``archolith_bench.facet.baselines.EmbeddingScorer`` protocol so it
    drops into conditions B/C/E in place of the offline LexicalEmbeddingStub. Only
    constructed when ``--embedder openai`` is passed, so the package stays offline /
    CI-pure. Every distinct text is embedded once and reused across queries/modes.
    """

    name = "openai-text-embedding-3-small"

    def __init__(self, model: str = "text-embedding-3-small") -> None:
        from openai import OpenAI

        self._client = OpenAI(api_key=_load_openai_key())
        self._model = model
        self._cache: dict[str, list[float]] = {}

    def _embed(self, texts: list[str]) -> list[list[float]]:
        need = [t for t in dict.fromkeys(texts) if t not in self._cache]
        if need:
            resp = self._client.embeddings.create(
                model=self._model, input=[t or " " for t in need]
            )
            for text, item in zip(need, resp.data):
                self._cache[text] = item.embedding
        return [self._cache[t] for t in texts]

    def score(self, query_text: str, memories) -> dict[str, float]:
        if not memories:
            return {}
        qv = self._embed([query_text])[0]
        mvs = self._embed([m.text for m in memories])
        return {m.id: _cosine(qv, mv) for m, mv in zip(memories, mvs)}


def _build_embedder(kind: str):
    """None -> runner uses its offline LexicalEmbeddingStub; 'openai' -> real model."""
    if kind == "openai":
        return OpenAIEmbeddingScorer()
    return None


def _strip_structural(fixture: FacetFixture) -> FacetFixture:
    """Return a copy with file/symbol/test facets removed on every memory + query.

    Simulates REGULAR (unanchored) memories: the facet system keeps only the
    interpretive (operation/object/actor/evidence) + scope (repo/project/namespace) +
    belief/time facets that any memory carries, with no code-anchoring. Tests whether
    the facet fashion helps corpus-wide, not just on the structural (anchored) slice.
    """
    import copy

    fx = copy.deepcopy(fixture)
    for m in fx.memories:
        m.facets.file, m.facets.symbol, m.facets.test = set(), set(), set()
    for q in fx.queries:
        q.facets.file, q.facets.symbol, q.facets.test = set(), set(), set()
    return fx


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
    parser.add_argument("--embedder", choices=["stub", "openai"], default="stub",
                        help="conditions B/C/E embedder: offline stub (default) or real OpenAI model")
    parser.add_argument("--facet-scope", choices=["all", "regular"], default="all",
                        help="'regular' strips file/symbol/test facets (regular-memory fashion: "
                             "interpretive + scope + belief only, no code anchoring)")
    args = parser.parse_args(argv)

    fixture_path = Path(args.fixture)
    if not fixture_path.exists():
        print(f"error: fixture not found: {fixture_path}", file=sys.stderr)
        return 1

    fixture = FacetFixture.from_file(fixture_path)
    if args.facet_scope == "regular":
        fixture = _strip_structural(fixture)
    runner = FacetBenchmarkRunner(fixture, embedder=_build_embedder(args.embedder))
    artifact = runner.run(include_traces=not args.no_traces)
    _print_table(artifact)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as handle:
        json.dump(artifact, handle, indent=2, sort_keys=True)
    print(f"\nwrote artifact: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
