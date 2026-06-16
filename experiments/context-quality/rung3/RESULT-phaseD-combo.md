# Rung 3 Phase D — Combo Fill Strategies (frozen-briefing recall)

**Date:** 2026-06-16
**Type:** Frozen-briefing recall (re-reading denied, budget=3000), 5 strategies x 3 tasks. Tests the
"use a combo of each" hypothesis after Phase C showed each PURE strategy optimizes one objective and
fails the others. Reproduce: `python rung3/phase_d_combo.py`.

## Strategies
- **fifo / scored / topological** — the pure baselines (Phase C).
- **combo** — naive round-robin INTERLEAVE of the scored ranking and the topological ranking (dedup).
  Intent: front-load both a task-relevant exemplar AND the top foundations.
- **xfcombo** — exemplar-aware combo: GUARANTEE a structural page exemplar (the top-scored file whose
  name ends `Page.tsx`) survives FIRST, then interleave scored x topological. Motivated by Phase C's
  failure analysis (scored's #1 can be a non-template file, e.g. a types file -> no structure to copy).

## Result
| task | fifo | scored | topological | combo | **xfcombo** |
|------|------|--------|-------------|-------|-------------|
| decks | 3/6 | 6/6* | 3/6 | 5/6 | **6/6*** |
| promos | 2/6 | 0/6 | 3/6 | 0/6 | **4/6** |
| bundles | 2/6 | 5/6 | 3/6 | 4/6 | **4/6** |
| **mean** | 2.33 | 3.67 | 3.00 | 3.00 | **4.67** |
| **core-OK** | 0/3 | 1/3 | 0/3 | 0/3 | 1/3 |
(* = core PASS; budget 3000; single shot per cell)

## What the combos showed
- **Naive interleave combo did NOT beat scored (3.00 vs 3.67).** It matches scored when scored picks a
  good exemplar (decks, bundles) but INHERITS scored's failure on promos (0/6): front-loading scored's
  #1 still wastes budget on the wrong file (`api-types.ts`), and adding foundations does not substitute
  for a missing TEMPLATE. Lesson: blending budget between exemplar+foundations is not the lever — the
  lever is getting a CORRECT exemplar.
- **Exemplar-aware combo (xfcombo) WINS (4.67) and has NO catastrophic cell.** By guaranteeing a page
  template survives, it FIXED promos (0 -> 4/6) — for promos it grabbed a real browse page instead of
  the types file — while matching scored's best on decks (6/6*). It dominates every pure strategy and
  the naive combo on mean recall, and is the only blend that never collapses to 0.

## Conclusion — the combo works, but only the EXEMPLAR-AWARE one
The user's "combo of each" intuition is correct, with a sharp refinement: the synthesis is not a naive
rank blend (that just averages the pure strategies' luck). The winning recipe is
**guarantee a structural exemplar (the template the model imitates) + then layer semantic relevance
(scored) + structural foundations (topological).** Each ingredient does a distinct job:
- exemplar -> the page/hook/css STRUCTURE to copy (the thing Phase C proved is recall-critical),
- scored -> task relevance (pick the closest exemplar + relevant helpers),
- topological -> foundations survive (data layer / shared types -> F3/F5/F6).

## Honest caveats
- **N=1 per cell**, single-shot generation; cells wobble ~+-1 run to run (e.g. fifo 2.33 here vs 3.33 in
  Phase C multi). xfcombo's MARGIN (4.67 vs 3.67 next) and its mechanistic win (guaranteed template ->
  no 0-cell, promos fixed 0->4) are the robust signal; exact means need a multi-seed confirm.
- **The exemplar guarantee is corpus-specific** — `*Page.tsx` is this app's template marker. A
  production combo fill would need a configurable "exemplar detector" (what a template looks like),
  the same corpus-specificity caveat that the dependency extractor carries for topological. The naive
  (fully general) interleave does NOT win; the win requires this corpus knowledge.
- Still re-reading-denied (the controlled regime). Live (Phase B) agents re-read, so this matters where
  re-reading is impossible (pure-conversation recall, files absent from cwd, hard no-read budgets).

## Recommended next (actionable)
Port an `xfcombo`-style fill into `deterministic_assembler.py` as a new flag-gated mode
(`assembler_combo_fill`), with a configurable exemplar matcher (default: a small set of template
markers), alongside FIFO/scored/topological. Then a multi-seed confirm (N>=3) of the Phase-D ranking.

## Artifacts
- `rung3/phase_d_combo.py` — 5-strategy harness (incl. `_combo_order`, `_xf_combo_order`).
- `rung3/phaseD-output/<task>/<strategy>/` — generated outputs.
