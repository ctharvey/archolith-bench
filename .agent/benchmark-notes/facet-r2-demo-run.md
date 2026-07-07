# Facet retrieval (menhir R2) — benchmark-local implementation + DEMO run

**Date:** 2026-06-27
**Status:** bench-first scaffold landed. **DEMO-fixture numbers only — NOT headline numbers, NOT the
benchmark fixture.** Per `HEADLINE-NUMBERS.md` policy, fixture data demonstrates the harness, it does
not verify a claim.
**Owner doc (menhir):** `menhir/.agent/plans/r2-facet-candidate-generation.md`.

## What landed

The benchmark-local facet mechanism from menhir R2, entirely inside archolith-bench (R2 is bench-first;
nothing here touches menhir production recall):

- `archolith_bench/facet/models.py` — `MemoryFacetSet`, `Memory`, `Query`, `FacetFixture`; the R2 facet
  vocabulary (`actor, object, operation, file, symbol, test, valid_time, learned_time, evidence_type,
  source_id, repo, project, namespace, belief_bucket`).
- `archolith_bench/facet/extractor.py` — `FacetExtractor`: deterministic regex/vocab rules (no LLM).
- `archolith_bench/facet/index.py` — `MemoryFacetIndex`: candidates by compatible facet **overlap**.
- `archolith_bench/facet/reranker.py` — `MeetPointReranker`: `meet_score` + per-candidate explanation
  trace (matched facets, convergence, penalties, rank).
- `archolith_bench/facet/baselines.py` — BM25, a deterministic embedding stand-in, RRF fusion, file-context.
- `archolith_bench/facet/metrics.py` — recall@5 / precision@5 / MRR / NDCG / stale-hit / wrong-scope /
  support-sufficiency / false-neighbor / paraphrase-stability.
- `archolith_bench/facet/runner.py` — ladder A–F × {gold, extracted} + the promotion gate.
- `fixtures/facet_demo.json` — 10 memories / 6 queries DEMO fixture.
- `scripts/run_facet_bench.py` — runs the ladder, writes `results/facet_run.json`.
- `tests/test_facet_*.py` — 46 unit tests (pure stdlib, deterministic).

Run it: `python scripts/run_facet_bench.py`

## Conditions

`A` BM25 · `B` embedding top-k (lexical stand-in) · `C` BM25+embedding (RRF) ·
`D` graph/file-context (stand-in: file/symbol overlap) · `E` facet index + embedding rerank ·
`F` facet index + meet-point rerank.

## DEMO results (gold facet mode)

| cond | recall@5 | prec@5 | MRR | NDCG | stale_hit | wrong_scope | support_suff | paraphrase |
|------|---------:|-------:|----:|-----:|----------:|------------:|-------------:|-----------:|
| A bm25            | 1.000 | 0.267 | 1.000 | 0.966 | 0.200 | 0.533 | 1.000 | 0.667 |
| B embedding\*     | 1.000 | 0.267 | 1.000 | 0.959 | 0.200 | 0.500 | 1.000 | 0.667 |
| C hybrid          | 1.000 | 0.267 | 1.000 | 0.959 | 0.200 | 0.500 | 1.000 | 0.667 |
| D file-context\*  | 0.833 | 0.694 | 0.750 | 0.758 | 0.056 | 0.000 | 0.833 | 0.667 |
| E facet+embed\*   | 1.000 | 0.267 | 1.000 | 0.973 | 0.233 | 0.433 | 1.000 | 0.667 |
| **F facet+meet**  | 1.000 | 0.267 | 0.917 | 0.939 | **0.100** | **0.400** | 1.000 | **1.000** |

`*` = deterministic stand-in, not a real embedding / not the live menhir graph retriever.

**Gold-mode gate: GRADUATES (on the demo).** F halves stale-hit (0.20→0.10) and cuts wrong-scope
(0.50→0.40) versus the best of A/B/C, with **zero recall@5 loss** and the best paraphrase stability
(1.00). The honest cost: F trades a little first-rank precision (MRR 0.917 vs 1.000, NDCG 0.939 vs
0.966) — meet-point reorders *within* the support set in exchange for suppressing stale/wrong-scope
neighbors. Reported together, not cherry-picked.

## DEMO results (extracted facet mode) — gate FAILS, and that is the point

With facets recovered by the cheap deterministic extractor instead of gold labels, F **does not
graduate**: recall@5 drops to 0.833 (loss 0.167, over the 0.10 tolerance) and stale/wrong-scope no
longer improve. This is the gold-vs-extracted separation R2 Risk #2 demands — the extractor gap is
*measured*, not hidden behind hand-authored facets. The biggest extractor miss on this fixture: query
gold `file` facets use full paths (`src/menhir/services/recall_service.py`) while memory text mentions
only the basename (`recall_service.py`), so file-overlap candidate generation under-fires.

## Honest limits of this run

- **DEMO fixture, hand-authored by one agent.** It is small and likely "too clean" (R2 Risk #1). The
  real fixture (50 memories / 20 queries / gold facets, with stale/wrong-repo/symbol-rename distractors
  and ≥1 vague query where embedding should win) is a **pair-authoring task with ctharvey** and is not
  done here.
- **Embedding conditions (B/C/E) use a lexical stand-in**, not a real embedding model. Until a real
  `EmbeddingScorer` is injected, B/C/E are not an embedding comparison.
- **Condition D is a file/symbol-overlap stand-in**, not menhir's live graph/file-context retriever.
- Therefore: the gold-mode "graduates" verdict is a *harness sanity check*, **not** evidence that R2
  should promote into menhir production. The promotion decision stays gated on a real fixture + real
  baselines, per the R2 plan.

## Next (at home)

1. Pair-author the real 50/20 gold fixture with ctharvey.
2. Inject a real `EmbeddingScorer` (B/C/E) and, if available, the live menhir graph retriever (D).
3. Re-run; report all metrics together; apply the promotion gate. Only if F graduates on the *real*
   fixture does the menhir production-integration rung (wiring `CandidateSource.FACET`) open.

---

## Update 2026-06-27 — fixture validator + real-grounded 50/20 DRAFT

Public datasets (LongMemEval etc.) are the wrong source (wrong domain, no scope/stale/rename
distractors), so the real fixture is authored from **our own history**. Two additions landed:

- **`archolith_bench/facet/validate.py`** — a fixture validator (errors vs quality warnings). It
  separates "malformed, can't run" (missing support IDs, dup IDs, bad buckets) from "probably too
  clean" (no stale/rename/wrong-repo/vague distractor, under-spec counts). Expanded with four
  modest heuristics that flag (not fix) hardening opportunities: (1) **uncontested** current queries,
  named with their topic + the missing distractor family; (2) **fake-paraphrase** detection (a
  paraphrase-group query that is a near-verbatim copy of its support text, ≥85% content-token overlap);
  (3) a stricter **facet-less vague** check (a query labelled embedding-should-win must carry no
  repo/file/symbol/valid_time facet); (4) **multi-support dependency** (a query claiming ≥2 support
  where one support facet-dominates, or two supports are near-duplicate text — i.e. one may suffice).
  On the DRAFT it correctly flags q01/q02/q07 as facet-dominated multi-support but passes the genuinely
  differentiated q12/q15, and the real paraphrases q01/q02 do not trip the near-copy check. The
  validator flags; it does not design the benchmark. 11 unit tests; 57 facet tests total.

- **`fixtures/facet_r2_draft.json`** — a **DRAFT** 50-memory / 20-query fixture grounded in *real*
  menhir + archolith-bench history: the R1 source-aware-floor change superseding the old cosine
  floor; the `cth.mcp.memory → yawn_memory → menhir` rename chain (great knowledge-update / historical
  cases); the documented CE-willow belief drift (E1–E5, with the anergic "patch fixed it" distractor);
  real files/symbols/bugs; and genuine cross-repo collisions (both repos talk about BM25/floor/RRF/
  meet-point). **Still needs adversarial hardening with ctharvey** (R2 Risk #1).

DRAFT run (still the lexical-embedding stand-in, not a real embedder):

| mode | A bm25 R@5 | F facet+meet R@5 | F stale | F wrong-scope | gate |
|---|---|---|---|---|---|
| gold      | 0.85 | 0.85 | 0.15 (vs 0.23 best baseline) | 0.07 (vs 0.40) | **graduates** (recall loss 0.000) |
| extracted | 0.85 | 0.28 | 0.00 | 0.73 | fails (recall loss 0.575) |
| **hybrid** | 0.85 | **0.83** | 0.13 | 0.07 | **graduates** (recall loss 0.025) |

Notably more discriminating than the demo: BM25 is a *strong* baseline (R@5 0.85), F barely beats it
on recall but slashes wrong-scope (0.40→0.07) and stale (0.23→0.13) — the win is exactly on the
targeted metrics. Extracted-mode F collapses, honestly exposing that the cheap extractor can't recover
facets from real prose (full file paths in gold vs basenames in text).

**Hybrid mode (Priority 6 — the fix) recovers the gap.** Reading the deterministic facets
(file/symbol/test/scope/time/bucket) from structure/Git instead of regexing them from prose — and
extracting *only* the interpretive facets (actor/object/operation/evidence_type) — takes F's recall from
**0.28 → 0.83** (gold is 0.85) and re-graduates the gate (recall loss 0.025), with stale/wrong-scope at
gold levels. This confirms the plan's central claim: **the extractor bottleneck is the structural-facet
extraction, not the engine** — a system should *read* those facets, never regex them. The small residual
vs gold (0.83 vs 0.85) is the genuinely-interpretive facets the regex still misses. **Still the stand-in
embedder; still a DRAFT fixture; not a promotion decision.**

Run: `python scripts/run_facet_bench.py fixtures/facet_r2_draft.json`
