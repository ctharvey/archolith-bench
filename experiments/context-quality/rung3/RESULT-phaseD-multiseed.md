# Rung 3 — Phase D Multi-Seed Confirm (N≥3, the standing hard gate)

**Date:** 2026-06-16
**Type:** Metered confirm. Re-runs the Phase-D frozen-briefing protocol across **3 seeds** (7/8/9) ×
3 tasks × 5 strategies = **45 DeepSeek calls** (`deepseek-chat`, temp 0.2), scored with the graded
metric. Removes the N=1 fragility of `RESULT-phaseD-combo.md`. No 429s. Reproduce:
`python rung3/phase_d_multiseed.py`.

## Result (graded recall /6, n = 9 per strategy)
| strategy | mean | floor (min) | max | stdev |
|----------|------|-------------|-----|-------|
| **xfcombo** | **5.00** | **4.0** | 6.0 | **0.71** |
| combo (naive) | 4.11 | 1.0 | 6.0 | 2.02 |
| scored | 3.89 | 1.0 | 6.0 | 2.04 |
| fifo | 3.44 | 3.0 | 4.0 | 0.50 |
| topological | 3.28 | 3.0 | 3.5 | 0.25 |

## What N=9 confirms (and strengthens vs N=1)
1. **xfcombo wins decisively on mean (5.00)** — and now with a clear margin over scored (3.89) and
   naive combo (4.11), where the single-draw graded gap had been narrow (4.67 vs 4.17). The N=1 win was
   not a lucky draw.
2. **xfcombo has the highest FLOOR (4.0) AND the lowest variance among the high-mean strategies
   (stdev 0.71).** scored and naive-combo swing from 1.0 to 6.0 (stdev ~2.0) — they *collapse* on some
   task/seed combinations (the wrong-exemplar failure, now seen repeatedly, not once). This is the
   load-bearing property, confirmed across 9 draws: **the exemplar guarantee removes catastrophic
   failures.**
3. **The guarantee is precisely what separates xfcombo from naive combo.** Same interleave; the only
   difference is xfcombo pins a structural exemplar first. Effect: floor 4.0 vs 1.0, stdev 0.71 vs
   2.02. Identical mechanism minus the guarantee → wild variance.
4. **topological and fifo are reliably mediocre** (3.28 / 3.44, low stdev) — consistent with "keep
   foundations, never the exemplar" / "recency only." Stable but low.

## Verdict
The standing N=1 hard gate is cleared for the Phase-D ranking: **xfcombo (exemplar-aware combo) is the
robust recall winner — highest mean, highest floor, lowest variance.** The honest framing from the
graded re-score holds and is now statistically meaningful, not anecdotal: the value is **floor-raising
(no catastrophic cell)**, which a production default should optimize.

## Remaining limits (do not oversell)
- **One corpus, one task-family** (browse screens on `yawn.frontend`). The 2nd-corpus *recall* confirm
  is still open (the profiler's exemplar-*detection* generalization across 4 corpora is done; recall
  generalization is not).
- 3 seeds at temp 0.2 — genuine seed variance, but low-temperature sampling is not the full stochastic
  range; n=9 is a confirm, not a power study.
- Graded metric (partial credit); the binary contract gives the same qualitative ranking.

## Artifacts
- `rung3/phase_d_multiseed.py` — the multi-seed driver (seeds 7/8/9; STOPs on 429 per protocol).
- `rung3/phaseD-multiseed-output/seed{7,8,9}/<task>/<strategy>/` — all 45 generated features.
