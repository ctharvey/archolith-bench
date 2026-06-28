# Oracle pipeline (menhir R4-R7) — benchmark-local implementation + DEMO run

**Date:** 2026-06-28
**Status:** bench-first scaffold landed. **DEMO-fixture numbers only — NOT headline numbers, NOT the
benchmark fixture.** Per `HEADLINE-NUMBERS.md` policy, fixture data demonstrates the harness, it does
not verify a claim.
**Owner docs (menhir):** `docs/research/oracle-amplified-retrieval.md` (interface + combiner math),
`docs/research/oracle-runtime-interfaces.md` (the runtime contract), execution-ladder rungs R4/R6/R7.

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

## Owed before any promotion decision (R4-R7)

1. **A real semantic scorer** in place of the lexical stand-in (conditions A/E/F all use it).
2. **A harder fixture** that actually separates E from F: high-support-but-stale, correlated-duplicate
   evidence, and candidate-vs-candidate contradiction cases. The current demo cannot graduate F because
   it cannot stress it — that is by design, not a failure.
3. **Calibration** of `FAMILY_ALPHA` / `TARGET_LAMBDA` / `GAMMA` / the ranking-score role blend on that
   fixture (they ship as placeholders, not tuned values).
4. **R5 (CostAwareOracleScheduler)** and the snapshot/budget rules before any latency claim.
5. Only if F beats E on the real setup does the R7 combiner earn a menhir production surface. Until then
   this stays bench-only; **iterative amplification (R11) is out of scope until it beats F.**
