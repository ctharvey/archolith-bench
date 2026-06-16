# Rung 3 Phase C — Frozen-Briefing Recall (deny re-reading) — RESULT

**Date:** 2026-06-16
**Type:** Controlled recall test. One DeepSeek (`deepseek-chat`) call per fill strategy, given ONLY the
context that strategy keeps at budget — no tools, no filesystem, so the briefing is the sole source of
conventions (the confound Phase B could not remove). Reproduce:
`python rung3/phase_c_frozen_briefing.py`.

## Why
Phase B tied all arms at 6/6 because a tool-using agent RE-READS source and bypasses the curated
briefing. Phase C denies re-reading to isolate **briefing-based recall**, directly testing the
pre-registered threat **"foundation != recall-critical"**: topological keeps high-in-degree
FOUNDATIONS, but the file that shows a feature CONVENTION is an exemplar feature — which topological
may evict.

## Setup
Same 115-file briefing as Phase A (exemplar feature dirs + shared `data`/`domain`/`ui` foundations).
For each strategy, `build_deterministic_context(briefing, budget=3000, ...)` produces the surviving
context (~12,039 chars each); that context is the system prompt; the user prompt asks for a Decks
browse screen with NO convention names. Output parsed into files and scored by `feature_contract.py`.

## Result — topological is WORST, scored is BEST (inverse of Phase A)
| strategy | briefing kept (which files) | recall | core | failed anchors |
|----------|------------------------------|--------|------|----------------|
| FIFO | 7 partial `set-v3` files (adapter + components, NO page/hook) | 4/6 | FAIL | F2 hook, F5 ui |
| **scored** | **1 file: `features/sealed/SealedPage.tsx`** (a complete page exemplar) | **5/6** | **OK** | F6 domain |
| topological | 9 FOUNDATIONS (`apiClient`, `models/index`, `ui/index`, `slug`, `Common`, `formatters`, `api-types`, 2x feature `types`) | **3/6** | FAIL | F1 page, F2 hook, F4 css |

## Reading the result
- **Topological kept the infrastructure but no exemplar.** With apiClient/models/formatters in context
  the model got F3 (data layer), F5 (ui), F6 (domain) — but with NO feature exemplar it could not
  reproduce the page/hook/css STRUCTURE (failed F1, F2, F4). High in-degree identifies *foundations*,
  not *templates*.
- **Scored kept the one most task-relevant exemplar** (`SealedPage.tsx` — a browse page, semantically
  close to "Decks browse screen"). One complete page was enough to recall the whole convention
  (page + hook + css + data layer): 5/6, the only core PASS.
- **FIFO kept fragments** of one feature (components but not its page or hook), so partial recall: 4/6.

## What this means (the synthesis across rungs)
The three rungs together tell a precise story, and it is NOT "topological wins":
- **Phase A:** topological is best at keeping high-in-degree FOUNDATIONS alive in the briefing.
- **Phase C:** but foundations are NOT what you need to RECALL a feature convention — you need an
  **exemplar**. Semantic relevance (scored) finds the exemplar; topological evicts it for
  infrastructure. So **topological is the worst strategy for convention recall** here.
- **Phase B:** live, the agent re-reads, so neither effect surfaces (all arms 6/6).

**The jobs are different.** Topological/anchor-survival serves CORRECTNESS — keeping a load-bearing
file that must not silently disappear (the seed experiment's `mobile.css` anchor). Convention RECALL
serves IMITATION — and imitation needs a relevant EXEMPLAR, which is a semantic-relevance job
(scored), not an in-degree job (topological). Rung 2's win and "better recall" were never the same
goal; Phase C makes that explicit. This VINDICATES keeping both scored and topological as distinct,
non-default options for distinct purposes — and is a clean negative result for "topological improves
recall."

## Threats / limits
- **N=1 per strategy**, temperature 0.2, one task/corpus. The ranking is one draw; the MECHANISM
  (topological keeps infra not exemplars; an exemplar drives structural recall) is structural and
  robust, but the exact 3/4/5 numbers are not.
- **Scored's win depends on the query matching an exemplar.** `SealedPage` surfaced because the task
  ("browse screen ... value") shares vocabulary with the sealed browse page. On a task whose exemplar
  shares no vocabulary, scored could miss it too — the general lesson is "keep a relevant exemplar,"
  not "scored is universally best."
- Same ~12k-char budget across strategies; only WHICH files differ, which is the point.
- Single-shot generation (no agentic refinement); structural contract metric only.

## Artifacts
- `rung3/phase_c_frozen_briefing.py` — the test harness.
- `rung3/phaseC-output/{fifo,scored,topological}/` — the three generated outputs.
