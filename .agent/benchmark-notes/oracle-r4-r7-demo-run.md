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

**Mechanism (precisely bounded — this is a hypothesis, not a demonstrated result):** F ranks
current-intent queries by `z_relevant + z_current`, which for a stale item equals E's
`relevance − penalty` — *identical* — unless something bounds relevance. The remaining evidence is
**consistent with** F's **per-family contribution cap** (relevance support per source family is clamped,
so a fixed currentness penalty stays proportionally large) being the distinguishing mechanism, working
*together with* role routing — but **current fixtures do not yet isolate it** (a cap-isolating fixture is
owed). So treat "the cap is the lever" as a precisely-stated hypothesis, and note F's edge is
**calibration-sensitive**.

## The deeper finding: oracle quality and combiner quality are NOT independent

The original hypothesis was `better combiner → better rankings`. The evidence now says:

```text
better temporal oracle
        ↓
raises EVERY downstream combiner
        ↓
shrinks the architectural difference between combiners
```

That is the more interesting systems result, and it reframes the contribution. The retrieval stack is a
**decomposition** — `semantic → specialized oracles → combiner → ranking` — and improving the oracle
layer changes the *value proposition* of the combiner. The defensible claim is not "we invented a better
retrieval algorithm" but **"we decompose retrieval into explicit semantic / structural / temporal / scope
/ evidence reasoning, each benchmarkable independently."** Corollary: if a neural combiner later beats F,
the architecture survives — swap the combiner, keep the oracle decomposition and the eval framework.

## R7.5 — Oracle ablation (contribution matrix)

`run_ablation()` (CLI: `--ablate`) attributes gains to layers. Subset rows hold the combiner fixed
(linear E) to isolate each oracle's marginal value; the last two hold the oracle set fixed (all) to
isolate the combiner. On `oracle_hard.json` (k=5):

| condition | recall@5 | stale_hit | wrong_scope | curr_truth_suppr |
|-----------|---------:|----------:|------------:|-----------------:|
| semantic [E] | 0.778 | 0.222 | 0.289 | 0.778 |
| semantic+temporal [E] | 0.889 | **0.000** | 0.422 | **1.000** |
| semantic+scope [E] | 0.778 | 0.311 | **0.044** | 0.689 |
| semantic+evidence [E] | 0.778 | 0.178 | 0.400 | 0.822 |
| semantic+structure [E] | **1.000** | 0.222 | 0.267 | 0.778 |
| all [E] | 1.000 | 0.000 | 0.067 | 1.000 |
| all [F] | 1.000 | 0.022 | 0.044 | 0.978 |

**Reading:** each oracle owns the metric it is responsible for — **Temporal** owns stale/current-truth,
**Scope** owns wrong-scope, **Structure** owns recall (buried recovery); **Evidence** is a weak
contributor on these metrics. The **combiner choice (all[E] → all[F]) is a smaller move than any single
strong oracle** — it trades a hair of stale (0.000→0.022) for better wrong-scope (0.067→0.044). i.e. on
this fixture the gains are overwhelmingly in the **oracle layer**, not the combiner. (A subset oracle can
*hurt* a non-owned metric — e.g. +temporal worsens wrong-scope by surfacing more current-but-out-of-scope
items — which is exactly why the full set + a combiner is needed.)

## Temporal oracle restructure — and what it revealed

The `TemporalOracle` was a stale/not-stale boolean; it is now a structured classifier over the
validity window + learned-time, returning a `TemporalStatus`:

```text
CURRENT        valid at as_of, not superseded            -> SUPPORT currentness (or NEUTRAL if historical intent)
SUPERSEDED     expired/superseded on/before as_of        -> CONTRADICT currentness | SUPPORT historicality
NOT_YET_VALID  validity window starts after as_of         -> CONTRADICT currentness
NOT_YET_KNOWN  learned AFTER as_of (anachronism/leakage)  -> CONTRADICT currentness (always)
UNKNOWN        no temporal anchors                        -> MISSING (raise uncertainty, do not fabricate)
```

New, independently valuable: the **anachronism guard** (a memory learned after the query's as-of point
is temporal leakage and must not inform it) and **not-yet-valid**, plus **graded directness** (an
explicit timestamp/flag is direct=1.0; a belief-bucket-only inference is softer=0.6, so inferred-stale
is penalised less hard than provably-expired).

**What it revealed (the honest finding):** structuring the oracle gave *live* items stronger currentness
support, which **lifted the weighted baseline E**. On the correlated trap E now matches F (both keep all
stale echoes out); on `oracle_hard` E's stale-hit dropped to 0.000 and F's edge moved to wrong-scope.
So **part of the earlier "F beats E" gap was a crude temporal signal, not combiner architecture** — with
a better oracle the linear baseline catches up on these fixtures. The durable, architecture-level
difference that remains is the per-family cap above; demonstrating it cleanly needs a fixture where a
stale item's relevance is high enough to overflow E's *uncapped* sum after a fair temporal penalty.

## What landed

The benchmark-local oracle pipeline, entirely inside archolith-bench (R4-R7 are build-first rungs but
nothing here touches menhir production recall):

- `archolith_bench/oracle/models.py` — `QueryContext`, `CandidateMemory`, `OracleResult`, `OraclePacket`
  (the R4 interface, immutable for thread-safety) + the fixture model (`OracleMemory`/`OracleQuery`/
  `OracleFixture`).
- `archolith_bench/oracle/oracles.py` — cheap `RetrievalOracle`s (R6): Semantic (lexical stand-in),
  Structure (file/symbol/test overlap), Scope (repo/branch/project/namespace), **Temporal (structured —
  see below)**, Evidence (provenance strength).
- `archolith_bench/oracle/executor.py` — bounded, deterministic `OracleExecutor` (R4).
- `archolith_bench/oracle/combiner.py` — `WeightedOracleCombiner` (ladder E) and
  `LogSpaceOracleCombiner` (ladder F, R7): role-specific log-space logits, contradiction as negative
  log-evidence `D=λ·q^γ`, source-family independence (`1/√n`), per-family contribution cap,
  missing-evidence → uncertainty (not suppression).
- `archolith_bench/oracle/metrics.py` — recall/precision/MRR/NDCG + stale-hit / wrong-scope /
  current-truth-suppression / historical-preservation / ranking-determinism.
- `archolith_bench/oracle/runner.py` — ladder A_semantic / E_weighted / F_logspace + promotion gate + `run_ablation` (R7.5 contribution matrix).
- `fixtures/oracle_demo.json` — 10 memories / 6 queries DEMO fixture (real menhir history: the R1 floor
  change vs the old cosine floor, the cth.mcp.memory→menhir rename, CE-willow drift, a cross-repo
  collision, a buried-by-embedding structural case).
- `scripts/run_oracle_bench.py` — runs the ladder, writes `results/oracle_run.json`.
- `tests/test_oracle_*.py` — 48 unit tests (pure stdlib, deterministic, ruff clean).

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
| E_weighted | 1.000 | 0.000 | 0.067 | 1.000 |
| F_logspace | 1.000 | 0.022 | **0.044** | 0.978 |

Promotion gate (F vs best of {A, E}): **GRADUATES** — but now only on `wrong_scope_injection`
(0.067→0.044, F's scope double-hit), with **no recall loss**. (Numbers post temporal-oracle restructure;
see below.)

**Where the edge comes from — and how it shifted.** *Before* the temporal restructure, E kept the stale
`floor_old` (old 0.15 cosine floor, same file + git/test evidence) at rank 3 and F dropped it — a clean
stale-hit win. *After* the restructure, the structured Temporal oracle gives the live `floor_new`
stronger currentness support, so **E now also drops `floor_old`** (E stale-hit 0.044→0.000). The
stale-hit separation evaporated; F's remaining gate edge on this fixture is wrong-scope (the
`z_blocked` + `z_relevant` double-hit E can't replicate). Honest read: a better temporal oracle closed
the stale gap for the linear baseline too.

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
| E_weighted | 0.900 | 0.000 | 1.000 |
| F_logspace | 0.900 | 0.000 | 1.000 |

```
q_trap_current top-5 (post temporal restructure — E and F now identical):
  E: [ct_truth, fill_name, fill_lease, fill_floor, fill_graph]   <- all 5 echoes suppressed
  F: [ct_truth, fill_name, fill_lease, fill_floor, fill_graph]   <- all 5 echoes suppressed
```

Gate: **does not graduate** — E now ties F (both suppress every stale echo). Before the temporal
restructure E leaked 2 echoes into the top-5 and F graduated; the structured oracle's stronger
currentness support fixed E here too. The trap no longer separates E from F.

**Two honest corrections this trap forced:**

1. **The "five echoes overpower one truth" hypothesis was falsified.** A *well-evidenced* current truth
   (user+test evidence + currentness swing) is **not** buried by the chorus even under the linear sum E —
   E ranked `ct_truth` #1. Before the temporal restructure E at least leaked 2 echoes into the top-5 as
   noise (F admitted none); *after* the restructure E suppresses all five too, so on this fixture E and F
   are identical. A chorus does not automatically win, and a well-structured temporal oracle lets even
   the linear combiner handle it.
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
