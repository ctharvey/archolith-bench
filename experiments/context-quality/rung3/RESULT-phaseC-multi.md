# Rung 3 Phase C (multi-task) — Hardening the Frozen-Briefing Recall Ranking

**Date:** 2026-06-16
**Type:** 3 target tasks x 3 fill strategies = 9 DeepSeek calls, re-reading denied (briefing is the
only context). Hardens single-task Phase C (`RESULT-phaseC-frozen-briefing.md`), which was N=1 and
left the caveat "scored only wins when the query matches an exemplar." Reproduce:
`python rung3/phase_c_multi.py`.

## Result
| task | FIFO | scored | topological |
|------|------|--------|-------------|
| decks (total market value) | 3/6 | **6/6 (core OK)** | 3/6 |
| promos (release year) | 3/6 | **0/6** | 3/6 |
| bundles (discount %) | 4/6 | 5/6 | 3/6 |
| **mean recall** | 3.33 | 3.67 | **3.00** |
| **core-OK count** | 0/3 | 1/3 | 0/3 |

## What hardened (and what changed) vs single-task Phase C
- **Topological is consistently 3/6 on EVERY task** — lowest mean, lowest variance. It always keeps the
  same high-in-degree FOUNDATIONS (apiClient/models/formatters/ui) and NEVER a feature exemplar, so it
  reliably gets the data-layer/ui/domain anchors and reliably misses the page/hook/css STRUCTURE.
  Robustly the worst for convention recall — confirmed across tasks.
- **Scored is HIGH-VARIANCE (6 / 0 / 5), not reliably best.** Its mean (3.67) barely edges topological
  (3.00), driven entirely by whether its keyword relevance surfaces a structural EXEMPLAR:
  - decks -> kept `SealedPage.tsx` (a real browse page) -> 6/6.
  - bundles -> kept a usable page -> 5/6.
  - **promos -> kept only `data/api-types.ts` (a TYPES file, "release year" matched type vocab, NOT a
    page) -> 0/6.** With no structural exemplar the model invented a non-conforming feature (a
    `PromosBrowsePage` plus `.stories`/`.test` files the app does not use).
- **FIFO is stable-mediocre (3-4/6), task-independent** — it keeps the same insertion-order files
  (`set-v3` fragments) regardless of task, so partial, consistent recall.

## The hardened conclusion
**No deterministic fill strategy reliably delivers convention recall from a budget-truncated briefing.**
The recall-critical artifact is a *task-relevant structural exemplar* (one complete feature). Only
semantic relevance even targets it, and keyword-relevance (the Phase-4 scorer) does so UNRELIABLY —
when the query's vocabulary matches a non-exemplar (promos -> a types file) scored collapses to 0/6,
worse than the stable strategies. Topological optimizes in-degree (foundations), which is the *wrong
objective* for recall, so it is reliably mediocre.

This strengthens the cross-rung synthesis:
- **Anchor survival / correctness** (keep a load-bearing file alive) -> topological wins (Phase A).
- **Convention recall / imitation** (reproduce a pattern) -> needs a relevant exemplar; NO deterministic
  fill nails it reliably (Phase C multi); the robust answers are (a) better semantic retrieval than
  keyword overlap, or (b) let the agent re-read (Phase B — what real agents do).
- These are DIFFERENT objectives; conflating "topological protects foundations" with "topological
  improves recall" is the error this rung disproves.

## Threats / limits
- Still single-shot per (task, strategy); the per-cell number is one draw, but the QUALITATIVE pattern
  (topological flat-mediocre; scored high-variance/query-dependent; FIFO flat) is now seen across 3
  tasks and is the robust finding.
- `feature_contract.py` is a structural metric; "0/6" for promos-scored means the produced feature
  matched none of the core anchors (it invented `.stories`/`.test`, no hook, no module.css).
- Budget fixed at 3000; the qualitative ranking is what transfers, not the absolute scores.

## Artifacts
- `rung3/phase_c_multi.py` — multi-task harness.
- `rung3/phaseC-multi-output/<task>/<strategy>/` — all 9 generated outputs.
