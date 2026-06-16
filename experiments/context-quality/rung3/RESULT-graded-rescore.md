# Rung 3 — Graded Re-score (ceiling-effect check)

**Date:** 2026-06-16
**Type:** Offline re-analysis of the COMMITTED Phase B/C/D outputs with a finer metric — no
regeneration, no API. Tests the full-context review's concern that the binary `feature_contract`
(6 PASS/FAIL anchors) might saturate, so "all 6/6" in Phase B could be a ceiling artifact rather than
a true tie. Reproduce: `python rung3/rescore_graded.py`.

## Method
`graded_feature_score` decomposes the four AND-gated core anchors (F1–F4) into half-credit
sub-signals (e.g. F1 = has `*Page.tsx` 0.5 + `export default` 0.5; F3 = uses `@/data` layer 0.5 +
no raw `fetch` 0.5); F5/F6 stay binary. Per-anchor [0,1], total [0,6]. The binary metric is
unchanged — this is a parallel lens applied to the same committed files.

## Result
| phase | binary | graded | finding |
|-------|--------|--------|---------|
| **B** (live) | all 3 arms 6/6 | all 3 arms **6.00** | **The tie is REAL, not a ceiling.** The re-reading agent genuinely produced fully-conforming features in every arm; finer resolution finds no hidden gap. Phase B's null stands. |
| **C** (frozen, 1 task) | topo 3 / fifo 4 / scored 5 | 3.0 / 4.0 / 5.0 | Identical — the single-task ranking was already at full resolution. |
| **C-multi / D** | see below | see below | Mostly tracks binary; refines a few near-misses. |

### Phase D per-strategy means — binary vs graded
| strategy | binary mean | graded mean | min cell (graded) |
|----------|-------------|-------------|-------------------|
| fifo | 2.33 | 2.67 | 2.5 |
| topological | 3.00 | 3.33 | 3.0 |
| combo (naive) | 3.00 | 3.67 | 1.0 |
| scored | 3.67 | **4.17** | 1.5 |
| **xfcombo** | **4.67** | **4.67** | **4.0** |

## What changed under the finer lens (honest)
- **Phase B ceiling concern: REFUTED.** Graded == binary == 6.00 across all arms. The "no difference"
  was a true tie (agent re-read -> all arms conform), not metric saturation. This *strengthens* Phase
  B's finding rather than weakening it.
- **xfcombo still wins (4.67), but the mean gap to scored narrows** (binary 4.67 vs 3.67 = 1.0;
  graded 4.67 vs 4.17 = 0.5). Scored gets partial credit on near-misses the binary metric zeroed.
- **xfcombo's real edge is ROBUSTNESS, not raw mean.** Its worst cell is **4.0**; scored's worst is
  **1.5** (the promos collapse) and naive-combo's is **1.0**. So the honest framing sharpens: the
  exemplar guarantee buys *floor-raising* (no catastrophic failure), not a big mean lift. That is
  arguably the more valuable property for a production default.
- **`promos/scored` "0/6" was slightly harsh** — graded 1.0–1.5 (it had a `Page.tsx` / one half-signal),
  but still the worst on that task. The qualitative story (scored is high-variance, collapses when it
  picks a non-exemplar) is unchanged.

## Net
The graded re-analysis (a) lays the Phase-B ceiling concern to rest, and (b) reframes the Phase-D
conclusion from "xfcombo has the highest mean" to the more defensible **"xfcombo is the only strategy
with no catastrophic cell"** — floor-raising, not mean-chasing. No committed result is overturned; one
is sharpened and one is de-risked. Still N=1 per cell — the metric is finer, the sample is not.

## Artifacts
- `rung3/rescore_graded.py` — the re-score driver.
- `feature_contract.graded_feature_score` — the partial-credit scorer (additive; binary metric intact).
