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
