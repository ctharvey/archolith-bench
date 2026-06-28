# Oracle pipeline (menhir R4-R7) — benchmark-local implementation + DEMO run

**Date:** 2026-06-28
**Status:** bench-first scaffold landed. **DEMO-fixture numbers only — NOT headline numbers, NOT the
benchmark fixture.** Per `HEADLINE-NUMBERS.md` policy, fixture data demonstrates the harness, it does
not verify a claim.
**Owner docs (menhir):** `docs/research/oracle-amplified-retrieval.md` (interface + combiner math),
`docs/research/oracle-runtime-interfaces.md` (the runtime contract), execution-ladder rungs R4/R6/R7.

## Headline finding

> **A linear combiner lets relevance buy back currentness; role-separated logits don't.**

The important result is not the deltas — it is that a hand-authored fixture finally **exposes the
failure mode**: a weighted sum lets a "very relevant but stale" memory buy its way back into the top-k.
That is exactly the failure Menhir/Archolith exists to prevent. The log-space role-logit combiner (F)
routes the temporal contradiction to a separate currentness logit, so relevance cannot pay for
staleness.

**Verdict:** R7 graduates from *unjustified complexity* to *bench-justified, bench-only machinery*.
Not production, not headline, not a general benchmark win — but worth continuing. **R11 (iterative
amplification) remains blocked** (must beat F first).

## What landed

The benchmark-local oracle pipeline, entirely inside archolith-bench (R4-R7 are build-first rungs but
nothing here touches menhir production recall):

- `archolith_bench/oracle/models.py` — `QueryContext`, `CandidateMemory`, `OracleResult`, `OraclePacket`
  (the R4 interface, immutable for thread-safety) + the fixture model (`OracleMemory`/`OracleQuery`/
  `OracleFixture`).
- `archolith_bench/oracle/oracles.py` — cheap `RetrievalOracle`s (R6): Semantic (lexical stand-in),
  Structure (file/symbol/test overlap), Scope (repo/branch/project/namespace), Temporal
  (valid/invalid/as-of × intent), Evidence (provenance strength).
- `archolith_bench/oracle/executor.py` — bounded, deterministic `OracleExecutor` (R4).
- `archolith_bench/oracle/combiner.py` — `WeightedOracleCombiner` (ladder E) and
  `LogSpaceOracleCombiner` (ladder F, R7): role-specific log-space logits, contradiction as negative
  log-evidence `D=λ·q^γ`, source-family independence (`1/√n`), per-family contribution cap,
  missing-evidence → uncertainty (not suppression).
- `archolith_bench/oracle/metrics.py` — recall/precision/MRR/NDCG + stale-hit / wrong-scope /
  current-truth-suppression / historical-preservation / ranking-determinism.
- `archolith_bench/oracle/runner.py` — ladder A_semantic / E_weighted / F_logspace + promotion gate.
- `fixtures/oracle_demo.json` — 10 memories / 6 queries DEMO fixture (real menhir history: the R1 floor
  change vs the old cosine floor, the cth.mcp.memory→menhir rename, CE-willow drift, a cross-repo
  collision, a buried-by-embedding structural case).
- `scripts/run_oracle_bench.py` — runs the ladder, writes `results/oracle_run.json`.
- `tests/test_oracle_*.py` — 38 unit tests (pure stdlib, deterministic, ruff clean).

Run it: `python scripts/run_oracle_bench.py`

## DEMO numbers (k=5, lexical semantic stand-in — harness sanity check only)

| condition | recall@5 | stale_hit | wrong_scope | current_truth_suppression | historical_preservation |
|-----------|---------:|----------:|------------:|--------------------------:|------------------------:|
| A_semantic | 0.833 | 0.300 | 0.167 | 0.500 | 1.000 |
| E_weighted | 1.000 | 0.000 | 0.000 | 1.000 | 1.000 |
| F_logspace | 1.000 | 0.000 | 0.000 | 1.000 | 1.000 |

Promotion gate (F vs best of {A, E}): **does not graduate** — F ties E, no strict improvement.

## What the numbers honestly say

1. **A single semantic signal is not enough.** A_semantic misses the buried-by-embedding case
   (q06: zero lexical overlap, recovered only by the structure oracle) and lets stale / wrong-scope
   neighbours into the top-k — the exact failures the oracle layer exists to fix.
2. **Intent-aware oracles + a simple weighted sum (E) already saturate this easy fixture.** Because each
   oracle is intent-aware (the Temporal oracle flips SUPPORT↔CONTRADICT on current-vs-historical), even
   the naive linear combiner suppresses stale/wrong-scope and preserves historical correctly.
3. **The log-space combiner (F) matches E here — it does not beat it.** This is the important, honest
   signal: **F's marginal value over a weighted sum is not demonstrated on an easy fixture and must not
   be assumed.** The log-space machinery (role separation, independence caps, family caps) is built to
   pay off on *harder* cases — a stale/contradicted candidate with overwhelming relevance support that a
   linear sum keeps, correlated duplicate evidence that fakes certainty, candidate-vs-candidate
   contradiction — none of which this 10-memory smoke fixture stresses.

This mirrors the facet demo's lesson (BM25 is a strong baseline): the bench's job is to make us *earn*
the more complex mechanism, not adopt it on faith.

## Bug found by running it

The first run exposed a real bug: `ScopeOracle` set `scope_match=0` on a scope conflict, but the
combiner multiplies contradiction strength by `scope_match`, so a total mismatch produced a **zero**
penalty (wrong-scope items leaked into F). Fixed: `scope_match` downweights *other* oracles' evidence,
not the scope oracle's own verdict; the conflict strength is carried by `probability`. (Captured as a
regression test.)

## Harder fixture (`fixtures/oracle_hard.json`) — F now separates from E

Authored from real archolith/menhir history to stress the cases the easy demo could not:
high-support-but-stale (the old `MIN_SIMILARITY_THRESHOLD` 0.15 cosine floor, same file + git/test
evidence as the current `source_aware_floor`); cross-repo scope collisions (menhir `scheduler_lease`/
`force_acquire` vs archolith-maintenance `SchedulerLeaseStore`; subgraph-code `projection` vs menhir
graph; archolith-context `archolith_proxy`); real rename trails (cth.mcp.memory→yawn_memory→menhir,
archolith-memory→menhir) plus the **yawn.scheduler trap** (a real component, not a rename); and the
buried-by-embedding willow case. 27 memories / 9 queries.

| condition | recall@5 | stale_hit | wrong_scope | current_truth_suppression |
|-----------|---------:|----------:|------------:|--------------------------:|
| A_semantic | 0.778 | 0.222 | 0.289 | 0.778 |
| E_weighted | 1.000 | 0.044 | 0.044 | 0.956 |
| F_logspace | 1.000 | **0.022** | 0.044 | **0.978** |

Promotion gate (F vs best of {A, E}): **GRADUATES** — F improves stale_hit (0.044→0.022) and
current-truth suppression (0.956→0.978) with **no recall loss**.

**Where the win comes from (q01, the high-support-but-stale case):** E keeps the stale `floor_old`
(old 0.15 cosine floor — same file, git+test evidence) at **rank 3**, in the top-5; F's role-separated
currentness routes the temporal contradiction to `z_current` and pushes `floor_old` **out of the top-5**
entirely. A linear sum lets strong relevance support buy back currentness; the log-space role logits
do not. That is the designed advantage, demonstrated.

**A fixture-design lesson worth keeping:** `wrong_scope_injection_rate@k` is **uninformative when a
scoped query has fewer than k in-scope candidates** — top-k is then forced to contain out-of-scope
items for *every* condition (a corpus-depth artifact, not a combiner result). The first draft of this
fixture had repos with a single in-scope memory and `wrong_scope` was pinned at 0.244 for both E and F;
deepening each scoped repo to ≥4 plausible in-scope memories dropped it to 0.044 and made the metric
meaningful. (Captured as `test_logspace_beats_weighted_on_hard_fixture`.)

**Still honest caveats:** semantic is a lexical stand-in; weights are placeholders; `wrong_scope` no
longer separates E from F here (both handle it once the corpus is deep enough) — the separation that
survives is on stale / current-truth, which is exactly the role-separation claim.

## Correlated-evidence trap (`fixtures/oracle_correlated.json`)

One CURRENT truth ("resolved by the load-order adjustment") vs **five STALE echoes** of the same
superseded belief ("the patch fully fixes it") spread across a design note, commit message, test
comment, memory summary, and a copied README — with the stale belief given *higher* lexical match to the
query than the current truth. 12 memories / 2 queries (a current-intent trap + a historical query that
must preserve the echoes).

| condition | recall@5 | stale_hit | current_truth_suppression |
|-----------|---------:|----------:|--------------------------:|
| A_semantic | 1.000 | 0.400 | 0.600 |
| E_weighted | 0.900 | 0.200 | 0.800 |
| F_logspace | 0.900 | **0.000** | **1.000** |

```
q_trap_current top-5:
  E: [ct_truth, fill_name, echo_commit, echo_testcomment, fill_lease]   <- 2 stale echoes leak in
  F: [ct_truth, fill_name, fill_lease, fill_floor, fill_graph]          <- all 5 echoes suppressed
```

Gate: **GRADUATES** (F cuts stale_hit 0.2→0.0 and lifts suppression 0.8→1.0; recall_loss 0.1 vs the
A baseline, at the tolerance boundary).

**Two honest corrections this trap forced:**

1. **The "five echoes overpower one truth" hypothesis was partially falsified.** A *well-evidenced*
   current truth (user+test evidence + currentness swing) is **not** buried by the chorus even under the
   linear sum E — E ranked `ct_truth` #1. So a chorus does not automatically win; the truth's evidence
   carried it. What E *does* do is admit 2 of the 5 stale echoes into the top-5 as noise; F admits none.
   The sharper, true claim: **F keeps stale out of top-k; E admits it.** Whether stale then *displaces*
   the truth (recall failure — `oracle_hard` q01) or only adds top-k noise (this trap) depends on the
   evidence balance.
2. **This trap exercises temporal role-separation, NOT the source-family cap.** Five separate echoes are
   five candidates; the within-candidate independence cap (`1/√n` over one candidate's own oracle
   results) never fires. Each echo is suppressed individually by its temporal contradiction. A genuine
   test of the source-family cap needs a *single* candidate piling up many same-source SUPPORT signals —
   still owed.

## Do NOT claim (bounds on this result)

This is bench-only, lexical-stand-in, placeholder-weight machinery. None of the following is shown:

1. real embedding performance,
2. calibrated weights,
3. latency viability,
4. general benchmark superiority,
5. production readiness.

## Next promotion gate (the real-setup bar for R7)

F must beat E when **all** of these hold:

1. the semantic scorer is **real** (not the lexical stand-in),
2. the stale truth has a **stronger semantic match** than the current truth,
3. **duplicate stale evidence** is present,
4. **scoped corpus depth** is sufficient (≥ k in-scope candidates per scoped query),
5. with **no recall@5 loss**.

Only if F clears that bar does the R7 combiner earn a menhir production surface.

## Owed before any promotion decision (R4-R7)

1. **A real semantic scorer** in place of the lexical stand-in (conditions A/E/F all use it).
2. **Calibration** of `FAMILY_ALPHA` / `TARGET_LAMBDA` / `GAMMA` / the ranking-score role blend (they
   ship as placeholders, not tuned values).
3. **A source-family-cap fixture**: a single candidate citing many same-source supports (the cap is not
   yet exercised by any fixture).
4. **R5 (CostAwareOracleScheduler)** and the snapshot/budget rules before any latency claim.
5. **Takeaway:** R7 is now justified as **bench-only machinery**; **R11 remains blocked** (must beat F).
