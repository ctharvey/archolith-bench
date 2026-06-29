# R1 live ladder — DEMO run (harness sanity check)

**Date:** 2026-06-28 · **Fixture:** `fixtures/r1_demo.json` (synthetic, 19 memories / 8 queries)
**Driver:** `scripts/run_r1_live.py` · **Graph:** throwaway Neo4j (bolt 7688) · **Extraction:** gpt-4.1-nano

> **This is a harness sanity check, NOT a promotion decision.** The demo corpus is
> synthetic and small, and its queries embed the exact identifiers, so the fused
> baseline already saturates recall. A real verdict needs the labeled prod corpus
> (`fixtures/local/r1_prod.json`, dumped read-only) where recall has headroom.

## What ran

The full live path executed end-to-end: seed corpus into the throwaway via menhir
ingestion, then run today's fused recall (`A_current`) and the attributed hybrid
path (`E`) swept over `hybrid_alpha`, each through `recall(trace=True)` (the R0
instrument), scored with the shared R1 metrics + win gate.

- Seeded 19/19 memories (each produced entities); 27 entity uuids grounded back to
  fixture ids (first-source-wins).
- All six conditions ran (A + alpha = 0 / 0.25 / 0.5 / 0.75 / 1.0).

## Numbers (top-k = 5)

| condition | recall@5 | exact_string | symbol | stale_hit | wrong_scope | latency_ms |
|---|---|---|---|---|---|---|
| A_current      | 1.000 | 1.000 | 1.000 | 0.094 | 0.260 | 310 |
| E_hybrid_a0    | 1.000 | 1.000 | 1.000 | 0.050 | 0.250 | 177 |
| E_hybrid_a0.25 | 1.000 | 1.000 | 1.000 | 0.050 | 0.350 | 188 |
| E_hybrid_a0.5  | 1.000 | 1.000 | 1.000 | 0.050 | 0.325 | 189 |
| E_hybrid_a0.75 | 1.000 | 1.000 | 1.000 | 0.050 | 0.325 | 183 |
| E_hybrid_a1    | 1.000 | 1.000 | 1.000 | 0.075 | 0.325 | 149 |

**Win gate: does not graduate.** recall/exact/symbol are saturated at 1.0, so E has
no headroom to *beat* A on exact-string/symbol recall, and E regresses wrong-scope.

## Honest findings

1. **Saturation is the fixture, not the engine.** Every condition finds every
   support in the top-5 because the corpus is tiny and the queries carry the rare
   identifiers. The gate correctly refuses to graduate without a measurable win.
2. **Real directional signal on stale-hit:** the hybrid path *lowers* stale-hit
   (A 0.094 -> E ~0.050) — BM25/source-aware candidates displacing a stale lexical
   neighbor. Genuinely in menhir's favor.
3. **Real directional signal on wrong-scope (negative):** E *raises* wrong-scope
   injection (A 0.260 -> E ~0.325). On the live graph, raw-seeded nodes have no
   menhir scope/namespace property, so the wrong-scope metric is weak here; this is
   partly a fixture/grounding artifact, not necessarily an engine regression.
4. **Latency:** the hybrid path is not slower than the fused baseline on this corpus
   (~150-190 ms vs ~310 ms for A_current's first call; warm-up dominated).

## Owed before this counts

- Run on the **labeled prod corpus** (`fixtures/local/r1_prod.json`): author queries +
  gold labels (support_ids / target_symbol / target_exact_string / stale / scope),
  so recall has headroom and the exact-string/symbol win is measurable.
- **Harden uuid -> fixture-id grounding** (entity de-dup makes first-source-wins
  approximate).
- Stamp menhir scope/namespace on seeded nodes (or author scope into the fixture) so
  wrong-scope injection is measured on real scope, not absent properties.
- Only then read the gate as a `hybrid_alpha` decision.

Artifact: `results/r1_live_run.json` (gitignored).
