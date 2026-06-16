# Rung 3 — B1: Does Surfacing a Code Map Change Recall? (RESULT)

**Date:** 2026-06-16
**Type:** Metered, frozen-briefing (re-reading DENIED), budget=3000. Factor = MAP presence, crossed
with two fills, N≥3. 2 fills × 2 map-states × 3 tasks × 3 seeds = 36 DeepSeek calls. No 429s.
Reproduce: `python rung3/phase_b1_codemap.py`. Uses the Thread-1 `assembler_code_map` renderer
(`archolith-context` `ad0612c`).

## Result (graded recall /6, n=9 per cell)
| cell | mean | floor | max | stdev | MAP effect |
|------|------|-------|-----|-------|-----------|
| fifo + no-map | 3.50 | 2.5 | 4.0 | 0.58 | — |
| fifo + MAP | 3.33 | 3.0 | 4.0 | 0.47 | **−0.17** |
| xfcombo + no-map | 4.94 | 4.0 | 6.0 | 0.64 | — |
| xfcombo + MAP | 4.94 | 4.0 | 5.5 | 0.55 | **+0.00** |

## Finding: the code map does NOT move recall — but recall is the wrong axis for it
- **MAP effect on recall ≈ 0** (xfcombo +0.00; fifo −0.17). Surfacing the structural overview does not
  improve convention recall, and slightly *hurts* FIFO (the map's ~391 tokens displace RELEVANT CODE
  the weak fill needed). xfcombo is unaffected — it already secures the exemplar, so the displaced
  tokens weren't load-bearing.
- **This is the EXPECTED result, not a surprise, and it does NOT falsify the MAP job.** A map's purpose
  is NAVIGATION — telling the agent *what to go read*. The frozen-briefing protocol DENIES re-reading,
  so there is nothing to navigate to: a map can't help you fetch a file when fetching is forbidden.
  Testing the map on recall under frozen briefing is close to tautologically null.
- The genuine signal here is the **cost** side: a map is not free (it cost FIFO 0.17). So a map must
  pay for itself via navigation gains that this experiment, by construction, cannot measure.

## What this settles and what it leaves open
- **Settled:** the code map is recall-neutral-to-slightly-negative under frozen briefing. It is NOT a
  recall lever. (Consistent with the decomposition's own claim that MAP ≠ CONTENT.)
- **Still open (the real MAP test):** does the map improve NAVIGATION when re-reading is ALLOWED —
  fewer/sharper file fetches, fewer backtracks, faster to completion? That requires a LIVE run (agent
  with file tools) + tool-call trace capture (the A3 navigation metric). B1-recall was the cheap first
  cut; it shows the map doesn't help the axis it was never meant to help, and bounds its token cost.
- **Decision for the roadmap:** do NOT enable `assembler_code_map` for recall. Before investing in the
  live navigation rung, weigh that the map's cost is real (≈390 tok / 0.17 recall on weak fill) and its
  benefit is unproven — the navigation experiment must show a clear fetch-efficiency win to justify it.

## Honest limits
- One corpus, one task-family, 3 seeds (n=9/cell) — a real confirm on the recall axis, but the
  navigation axis is entirely unmeasured here.
- The map is built on the R3a regex extractor (~61% edge coverage); a richer (tree-sitter) map might
  navigate better — but that's a bigger bet, downstream of first showing navigation matters at all.
- Frozen-briefing is the wrong regime for MAP by design; this result is a bound, not the verdict on the
  MAP job.

## Artifacts
- `rung3/phase_b1_codemap.py` — the driver.
- `rung3/phaseB1-output/seed{7,8,9}/<task>/<cell>/` — the 36 generated features.
