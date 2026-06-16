# Rung 3 Phase B — Live 3-Arm Run (RESULT)

**Date:** 2026-06-16
**Type:** LIVE agentic run (metered). 3 arms, opencode on direct DeepSeek (`deepseek-v4-flash`) via
the archolith proxy on :9800, driven by Claude through the harness PTY. Recall scored by
`rung3/feature_contract.py` (the validated Phase-B metric).

## Setup
- **Corpus / cwd per arm:** a fresh clone of `forked/yawn.frontend` (278 src files) seeded into
  `projects/forked/_phaseB/{passthrough,fifo,topo}`.
- **Pressure knob:** `ASSEMBLER_TOKEN_BUDGET=3000` (lowered from 6000 to force eviction in the curated
  briefing). `ASSEMBLER_SCORED_SELECTION=false`. Proxy restarted on current code per arm config.
- **Arms (only the context layer varies):**
  - A1 passthrough — route `archolith/deepseek-v4-flash-passthrough` (no curation).
  - A2 curator+FIFO — route `archolith/deepseek-v4-flash`, `ASSEMBLER_TOPOLOGICAL_FILL=false`.
  - A3 curator+topological — same route, `ASSEMBLER_TOPOLOGICAL_FILL=true` (proxy restarted).
- **Identical 4-turn lead, byte-for-byte across arms:** T1 orient/read (no writes), T2+T3 short
  warm-up (clear `COLD_START_TURNS=3`), **T4 the deliverable** — "Add a Decks browse screen,
  consistent with the rest of the app... it lists decks, each showing its total market value" — with
  NO convention names (no "hook"/"adapter"/"module.css"/"apiClient"/"features folder").
- Curation engaged on the curated arms (`assembly_modes curator=2`, `hot_path determin=2`,
  `prepper fires=3-4`, `llm_calls=0`); topological fill was active on A3.

## Result — all three arms scored identically
| arm | F1 page | F2 hook | F3 data-layer | F4 css-module | F5 ui | F6 domain | recall |
|-----|---------|---------|---------------|---------------|-------|-----------|--------|
| A1 passthrough | PASS | PASS | PASS | PASS | PASS | PASS | **6/6** |
| A2 curator+FIFO | PASS | PASS | PASS | PASS | PASS | PASS | **6/6** |
| A3 curator+topological | PASS | PASS | PASS | PASS | PASS | PASS | **6/6** |

All three produced a clean, convention-following Decks feature (page + `use*Data` hook + co-located
`*.module.css`, data through `@/data` layer, `@/ui` + `@/domain` reuse). A2 and A3 went further and
wired the data layer end-to-end (added `DeckDto`, `getDecks`, `mapDeck`, a `repository.decks` section).

## The mechanism — why no difference (the load-bearing finding)
**At the deliverable turn the agent RE-READ source files** rather than relying on the curated briefing
("Let me look at a representative v3 browse feature to understand the exact structure" -> `Read
src/data/...`). Both curated arms re-read; A3 (topological) re-read AND wired the whole data layer.

So in an agentic setting **the agent routes around context compression by re-reading the filesystem.**
The curator's fill strategy (FIFO vs topological) only governs what survives in the *briefing*, but the
briefing is not the agent's only source of conventions — the source tree is, and it is re-fetchable on
demand. Foundation survival in the briefing (the Phase-A win) therefore does **not** translate into a
live recall delta when the agent has file-read tools.

## Verdict (against the pre-registered decision rule)
- **Topological vs FIFO:** A3 recall == A2 recall (6/6 == 6/6). Per the rule, topological is
  **recall-NEUTRAL** under live agentic conditions on this task (keep off by default; the Phase-A
  briefing-level mechanism win stands as a mechanism result, not a live-recall win).
- **Combo vs passthrough:** A3 == A1 (6/6 == 6/6). The combo does **not beat passthrough on recall**,
  and does not regress it. Consistent with Phase 5 ("curator recall == passthrough == perfect, no
  headroom") — and this run EXPLAINS the no-headroom: the agent re-reads, so curation cannot move
  recall up or down.

## What this means for the thesis (honest reframing)
- Topological fill's value is **not live recall** when the agent can re-read source. Its real value is
  **cost / latency** (ship fewer, better-ordered tokens) and **recall only where re-reading is
  impossible** — pure-conversation recall, files absent from the cwd, or a hard no-tool-read budget.
- The Phase-A result (topological is the only strategy that keeps foundations in the briefing under
  pressure) is still true and useful; Phase B just bounds WHERE it pays off.
- This is a genuine negative result for "topological fill improves live recall" on a re-read-capable
  agent — and a sharper understanding of the curator's actual lever (economics, not recall) on
  file-backed agentic tasks.

## Threats / limits (do not oversell)
- **N=1 per arm.** Single stochastic session each; no variance estimate. The qualitative result (agent
  re-reads -> arms converge) is robust, but the 6/6-across-the-board number is one draw.
- **The re-read confound is the whole story.** To actually test the recall hypothesis you must DENY
  re-reading (remove the corpus from the cwd after orient, or a no-file-read deliverable turn) — that
  is a different experiment (Rung 3c). As designed, the filesystem masks the briefing.
- **Budget knob:** eviction was forced via `ASSEMBLER_TOKEN_BUDGET=3000`; at the real 6000 the briefing
  may not even evict on this task.
- Build/typecheck was NOT the metric (environmental `*.module.css` type-decl errors without
  node_modules); the contract scores structure, captured before any env-driven churn.

## Artifacts
- `rung3/phaseB-output/{passthrough-decks, fifo-decks-v3, topo-decks}/` — the three generated features.
- Scored with `rung3/feature_contract.py`.
