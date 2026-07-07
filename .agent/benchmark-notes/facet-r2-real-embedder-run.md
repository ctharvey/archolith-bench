# R2 facet ladder — real-embedder run (2026-07-05)

_Chunk F / R2 promotion gate with the `EmbeddingScorer` stub swapped for a real model.
Companion to `facet-r2-demo-run.md` (demo) and the R2 plan. Fixture:
`fixtures/facet_r2_draft.json` (50 memories / 20 queries, DRAFT — see caveats)._

## What this closes

The R2 promotion gate compares **F (facet index + meet-point rerank)** against the best of the
baselines **A_bm25 / B_embedding / C_hybrid**. B and C use the `EmbeddingScorer` seam, which
shipped as an **offline lexical stub** — so every prior facet verdict carried the caveat "swap in
a real embedder before trusting B/C/E." That swap is now done: `scripts/run_facet_bench.py
--embedder openai` injects an `OpenAIEmbeddingScorer` (text-embedding-3-small + cosine, cached by
text; ~70 embeddings total, no graph). The package stays offline/CI-pure; the real embedder lives
in the script behind the flag.

## Result — F GRADUATES against a REAL embedder (gold + hybrid)

Real-embedder run (`--embedder openai`), key metrics (recall@5 / stale_hit / wrong_scope / support):

```
gold mode          recall  stale  wrong_scope  support
A_bm25              0.850  0.270        0.400    0.800
B_embedding         0.850  0.200        0.380    0.800    <- real embedder (was a stub)
C_hybrid            0.875  0.230        0.400    0.850    <- real embedder
F_facet_meet        0.850  0.150        0.070    0.850
  GRADUATES: wrong_scope +0.31, stale +0.05, support +0.0, recall_loss 0.025 (ok)

hybrid mode        recall  stale  wrong_scope  support
C_hybrid            0.875  0.230        0.400    0.850
F_facet_meet        0.825  0.130        0.070    0.800
  GRADUATES: wrong_scope +0.31, stale +0.07, support -0.05, recall_loss 0.05 (ok)

extracted mode     recall  stale  wrong_scope  support
C_hybrid            0.875  0.230        0.400    0.850
F_facet_meet        0.275  0.000        0.730    0.200
  DOES NOT GRADUATE: recall_loss 0.6 (extractor gap — Risk #2, expected)
```

### Read

- **The real embedder raised the bar and F still clears it.** Swapping the stub for
  text-embedding-3-small made B/C genuinely stronger (C recall 0.80→0.875, B stale 0.23→0.20),
  so the baseline F must beat is higher than in the stub run — yet **F still graduates in gold and
  hybrid**. The durable win is **wrong-scope suppression**: F injects a wrong-scope memory only 7%
  of the time vs **38–40%** for BM25/embedding/hybrid, at ≤0.05 recall loss. The meet-point
  reranker's scope/stale discipline is real, not a lexical-stub artifact.
- **`stale_hit_rate` also improves** (F 0.13–0.15 vs 0.20–0.27 baselines) — F keeps superseded
  memories out of top-k better than pure similarity.
- **Extracted mode still collapses** (recall 0.275, wrong_scope 0.73). This is the known Risk #2:
  the pure-text `FacetExtractor` can't recover structural facets (file/symbol/test/scope), so the
  facet index has nothing to gate on. It is *not* a facet-engine failure — hybrid mode (real
  structural facets + interpretive facets extracted) recovers fully.
- **Contrast with R1 (same day):** R1's source-aware floor was neutral-to-negative against a real
  test; R2's facet + meet-point **earns graduation against a real embedder**. The leverage in R2
  is structural/scope facets at candidate-generation time, not a read-time re-rank.

## Caveats — why this is PROMISING, not yet a production go

1. **DRAFT fixture (Risk #1).** `facet_r2_draft.json` is grounded in real menhir/archolith history
   but is **not adversarially hardened** — the "too clean" risk stands. Numbers are directional
   until ctharvey hardens it (and the fixture validator's quality warnings are cleared).
2. **Hybrid mode uses a gold structural-facet stand-in.** `extract_memory_hybrid` reads the
   fixture's gold file/symbol/scope/time/bucket facets rather than deriving them from real
   Layer-2/Git. So hybrid assumes *perfect* structural facets — the real question (can we extract
   them cheaply and keep the win?) is the remaining owed piece.
3. **Condition D (file_context) is still a stand-in** (file/symbol overlap, not the live graph).
   It is NOT in the gate's baseline set (A/B/C), so it does not affect the verdict — but D is not a
   real graph-retriever comparison.

## Owed before wiring `CandidateSource.FACET` into production

- Harden the fixture with ctharvey (Risk #1); clear validator quality warnings.
- Real deterministic structural-facet extraction (Layer-2/Git), then re-run hybrid mode — the win
  must survive *derived* structural facets, not just gold ones.
- Only then wire `CandidateSource.FACET` + its prior/floor exemption into recall.

_Artifacts (regenerable, not committed): `results/facet_r2_openai.json` (real),
`results/facet_r2_stub.json` (stub, for comparison)._
