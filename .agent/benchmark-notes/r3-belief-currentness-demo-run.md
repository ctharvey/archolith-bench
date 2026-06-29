# R3 belief-currentness ladder — DEMO run

**Date:** 2026-06-28 · **Fixture:** `fixtures/r3_ce_willow.json` (5 belief items, intent=current)
**Driver:** `scripts/run_r3_bench.py` · **Consumes:** menhir `domain/belief` (real policy, not reimplemented)

> Harness sanity check, NOT a promotion decision. The demo is the CE-willow story from
> belief-layer.md; the real fixture families (ce_willow_belief_drift, auth_payload_refactor,
> out_of_order_insertion, retroactive_correction, wrong_repo/branch, agent_retrieval_loop,
> structural_neighbor_bug) are owed.

## Ladder (intent = current)

| condition | stale_current_assertion | poisoned_injection | historical_preservation | asserted | surfaced |
|---|---|---|---|---|---|
| A_assert_all (baseline) | 0.600 | 0.200 | 1.000 | 5 | 5 |
| C_belief_buckets (Rung-0) | 0.333 | 0.000 | 0.500 | 3 | 3 |
| **D_currentness** (intent-aware) | **0.000** | 0.000 | **1.000** | 2 | 4 |

**Win gate: GRADUATES.** D cuts stale-current assertion 0.600 → 0.000 with **zero**
historical-preservation loss.

## The finding (why D beats both A and C — the real signal)

- **A_assert_all** asserts everything relevant as current truth → it states 3 stale/
  noise beliefs as fact (0.60 stale, 0.20 poisoned). The poisoning baseline.
- **C_belief_buckets** (Rung-0 scorer, no intent) cuts stale to 0.33 **but its only
  "drop" is DO_NOT_ASSERT**, so it throws away the superseded former beliefs entirely —
  historical preservation collapses 1.0 → 0.5. It can't tell "stop asserting this as
  current" from "delete this."
- **D_currentness** routes the superseded-but-relevant belief to ANERGIC_CURRENT /
  HISTORICAL_ONLY: **not asserted as current (stale → 0.0), but still surfaced as
  history (preservation stays 1.0)**, and blocks the noise. This is exactly the
  belief-layer thesis — *relevant ≠ current*; suppress stale current-truth without
  erasing the belief-drift story — and it's the capability the naive bucket split can't
  express.

## Owed before this counts

- Build the remaining real fixture families (above) with gold current/historical/noise
  labels grounded in real menhir/archolith + RimWorld history.
- Add the B (temporal metadata) and E/F (exhaustion penalty / bounded structural
  expansion) ladder rungs from belief-layer.md.
- Only then read the gate as evidence to wire the currentness policy into production
  recall (still gated — no production recall change until graduation on real fixtures).

Artifact: `results/r3_run.json` (gitignored).

---

## Real fixtures (grounded in menhir history, 2026-06-28)

Three fixtures authored from CITED menhir history (not invented), gold labels grounded
in the provenance, ctharvey confirmation still the stated pairing step.

| fixture (intent) | family | A stale | D stale | hist loss | gate |
|---|---|---|---|---|---|
| `r3_floor_retroactive` (current) | retroactive_correction | 0.50 | **0.00** | 0.0 | GRADUATES |
| `r3_rename_wrong_scope` (current) | wrong_repo_or_branch | 0.50 | 0.33 | 0.0 | GRADUATES |
| `r3_floor_history` (historical) | out_of_order / drift | 0.67 | **0.00** | 0.0 | GRADUATES |
| `r3_seed_refactor` (current) | refactor_stale_memory (yawn.seed) | 0.60 | **0.00** | 0.0 | GRADUATES |
| `r3_structural_neighbor_bug` (current) | structural_neighbor_bug (unflag fix) | 0.50 | **0.00** | 0.0 | GRADUATES |
| `r3_agent_retrieval_loop` (current) | agent_retrieval_loop (recency mechanism) | 0.50 | **0.00** | 0.0 | GRADUATES |

Provenance: the floor cosine→rank-cut correction is recorded in `scoring_service.py:50-55`
(R1 commit e8da67d) and confirmed live by `probe_rrf_scale.py` (RRF max 2.0); the
`cth.mcp.memory → yawn_memory → menhir` rename is `chain-handoff.md:480`.

### The honest finding the real fixtures surfaced — the policy's boundary

`r3_rename_wrong_scope` only cuts stale 0.50 → 0.33 (not to zero) and leaves poison at
0.25. That is **correct and important**: the currentness policy gates **temporal
staleness** (superseded / expired beliefs), **not scope conflict**. The wrong-repo
`hybrid_alpha_other_repo` belief carries no supersession signal and scores assertable,
so D does not suppress it. Scope conflict is a *different* gate — R1's
`wrong_scope_injection` / the belief-layer `SelfToleranceGate` — not R3's job. A
too-clean synthetic fixture would have hidden this; the real wrong-repo case exposed
exactly where R3 stops. `r3_floor_history` is the intent-sensitivity control: the same
superseded belief that D suppresses under *current* intent is *surfaced as history*
(preservation 1.0) under *historical* intent.

### Second finding — Rung-0 buckets are useless against refactor-staleness (`r3_seed_refactor`)

The yawn.seed god-class split (`LocalDataSourceService` → `CardIngestMapper` c9940ae +
`RepoSyncService` cb2d013) is the `refactor_stale_memory` family. Result: **C scores
identically to the baseline (stale 0.60 = 0.60)** — it does nothing. Refactor-stale
beliefs ("mapping lives in LocalDataSourceService") are *well-supported* (`source_is_git`,
`embedding_match`), so the Rung-0 scorer rates them SAFE_TO_ASSERT. **Staleness is not low
confidence.** Only the currentness policy, reading the `is_expired` / `symbol_changed`
supersession signals, catches them — D cuts stale 0.60 → 0.00. This is the strongest
argument for R3: confidence-based bucketing alone cannot detect superseded-but-confident
beliefs; you need an explicit supersession axis.

A secondary nuance it exposed: a belief that is BOTH superseded AND noise (the wrong+stale
"Japanese sets imported by default", now blocked by 139163f) lands in HISTORICAL_ONLY
(surfaced) rather than BLOCKED, because `is_unsafe_belief` treats any superseded item as
history. Distinguishing "superseded-but-was-true" from "superseded-and-was-wrong" is a
future policy refinement (poison stayed 0.20 here).

### Cross-fixture synthesis — when is R3 actually essential (vs nice-to-have)?

All seven fixtures graduate, but C-vs-D tells the real story of *where the currentness
axis earns its keep*:

| C vs D | fixtures | why |
|---|---|---|
| **D >> C** (R3 essential) | `r3_seed_refactor` (C == baseline) | stale belief is *confidently held* (well-supported, no in-score contradiction) — confidence bucketing is blind to it; only the supersession axis catches it |
| **D > C** (R3 adds value) | `r3_floor_retroactive`, `r3_floor_history` | C drops the stale belief but also loses history; D suppresses-without-deleting |
| **D == C** (Rung-0 suffices) | `r3_structural_neighbor_bug`, `r3_agent_retrieval_loop`, `ce_willow` | stale belief carries explicit `later_contradicted` -> already low-confidence/CONFLICT under Rung-0 |
| **D partial** (out of scope) | `r3_rename_wrong_scope` | wrong-*scope* not temporal staleness — R1/SelfToleranceGate's job |

**The headline claim, precisely scoped:** R3's distinctive, non-redundant contribution is
detecting **confidently-held stale beliefs** — the refactor-stale case, where a belief is
well-evidenced yet superseded. That is exactly the failure a confidence score cannot see,
and it is the case that most poisons a coding agent ("the mapping is in LocalDataSourceService"
stated with full confidence, long after it moved). For already-contradicted beliefs the
Rung-0 scorer is enough; for wrong-scope, R3 is the wrong tool.

### Boundary families (last two) — honest framing

`r3_structural_neighbor_bug` and `r3_agent_retrieval_loop` each have a currentness CORE
(a superseded belief) that D handles, but their *full* mechanisms live in later rungs:
surfacing the real structural-neighbor cause is R1/file-context + the **F** bounded-
structural-expansion rung; breaking a recency loop needs the **RetrievalExhaustionPenalty
(E rung)**, session-local counters R3 does not model. They are included as real grounded
fixtures (the unflag wiring fix b49f3c0/7528c11; menhir's last_accessed recency loop) that
motivate E/F — not as proof R3 alone solves loops or structural bugs.

## Rung E — RetrievalExhaustionPenalty (session-replay, 2026-06-28)

The `agent_retrieval_loop` boundary fixture motivated rung E, now built:
menhir `domain/exhaustion.py` (the policy) + `archolith_bench/r3/session.py` (a
session-trace ladder) + `fixtures/r3_session_loop.json` + `scripts/run_r3_exhaustion_bench.py`.

Fixture: an agent re-retrieves the unproductive "just lower the 0.15 cosine floor" tweak
every turn (recency self-reinforced) with no progress until turn 6.

| condition | loop_injection_rate | productive_retention | exempt_retention |
|---|---|---|---|
| A_no_penalty | 0.400 | 1.000 | 1.000 |
| **E_exhaustion** | **0.000** | 1.000 | 1.000 |

**GRADUATES.** E eliminates loop injections (0.40 → 0.00) while keeping productive AND
exempt retention at 1.0 — it suppresses the trap only after it crosses the unproductive
threshold (`retrievals_since_progress >= 4`), and never touches the exempt active-error /
task-goal memories or the productive progress-driver. A unit test also confirms that a
trap which *produces progress* every couple of turns is never suppressed (counter resets) —
productive recency is preserved, which is the entire design constraint.

### Still owed

- B (temporal metadata) + F (bounded structural expansion) rungs.
- B (temporal metadata) + E/F (exhaustion penalty / bounded structural expansion) rungs.
- ctharvey confirmation of gold labels; then production-recall wiring (still gated).

Artifacts: `results/r3_floor_retroactive.json`, `results/r3_rename_wrong_scope.json`,
`results/r3_floor_history.json` (gitignored).
