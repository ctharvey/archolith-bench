# Rung 3 — Topological Fill Under Real File Pressure — PRE-REGISTERED PROTOCOL

**Status:** PRE-REGISTERED (design only; not yet run). Pre-registered before any run so the
result cannot be rationalized post-hoc.
**Rung:** #3 of `archolith/.agent/plans/archolith-context-deterministic-layers-direction.md`.
**Builds on:** Phase-5 seeded recall (`RESULT-3arm-seeded.md`) found NO headroom because the 8-file
seed all fit the budget; the offline sweeps (`RESULT-pressure-sweep.md`) found the real boundary but
on a synthetic corpus with a hand-written dependency map. Rung 2 shipped a MECHANICAL extractor
(`archolith-context/archolith_proxy/curator/dependency_graph.py`). This rung tests that extractor +
topological fill on a REAL, file-heavy codebase where eviction is forced.

## Question
When the curator's pre-fetched file set EXCEEDS the assembler token budget (so files must be
evicted), does **topological fill** (foundations-first, `ASSEMBLER_TOPOLOGICAL_FILL=true`) keep the
load-bearing files — and the agent's convention-recall — better than **FIFO** (insertion order)?
And does the **combo** (curator + topological) beat raw **passthrough** on a real codebase?

Two sub-questions, separated on purpose:
- **Q1 (mechanism, offline-testable):** under budget pressure, does topological fill keep the
  high-in-degree foundations in the assembled context block more often than FIFO/scored?
- **Q2 (product, live):** does that foundation survival translate to the agent reusing the
  established conventions (recall) when it generates a new screen?

## Corpus — `projects/forked/yawn.frontend/src` (a real Astro + React/TSX app)
Cloned fresh into `projects/forked` (HEAD `75ca56b`) so the experiment corpus is stable and isolated
from the live frontend. Domain-matched to the Phase-5 recall task (it is the real app the seed
miniaturized). Characterized offline by `rung3/analyze_corpus.py` (reproducible):

- **275 source files, ~983k chars (~246k tok) = ~40x the 6000-tok assembler budget -> eviction is
  forced**, unlike Phase 5.
- **Mechanical extractor coverage: 471 edges; 161/275 files (58%) have >=1 outgoing edge; 240/275 are
  depended-upon.** A clean in-degree gradient with genuine foundations:

  | in-degree | file | role |
  |-----------|------|------|
  | 35 | `data/apiClient.ts` | API client (the `api.js` analogue) |
  | 35 | `domain/slug.ts` | shared slug util |
  | 24 | `data/repository.ts` | data repository |
  | 21 | `layouts/Layout.astro` | shared page layout (the design-system shell) |
  | 19 | `features/cards-v3/types.ts` | shared feature types |
  | 10 | `domain/printing-labels.ts` | shared labels |
  | 5-8 | `data/api-types.ts`, `domain/{color-styles,formatters,color-utils,models/Common}.ts` | shared domain |

  These are exactly the silent anchors topological fill should protect (the user never names
  `apiClient`/`Layout` in a feature request).

### Extraction caveat (the load-bearing limit, recorded up front)
42% of files show no extracted outgoing edge. Some are genuine leaves; some are **misses** — the
basename matcher does not resolve TS **directory-index imports** (`from '../models'` -> `models/index.ts`)
or **path aliases** (`@/data/api`). This caps topological quality on this corpus and is itself a
finding. **Pre-registered sub-task R3a (offline, optional, before Phase B):** add index-resolution +
alias-map support to the extractor and re-measure coverage. Do NOT silently improve the extractor
mid-experiment; if R3a runs, re-run Phase A on both extractor versions and report both.

## Phase A — OFFLINE mechanism test (free; CAN RUN NOW, not blocked on the key)
No proxy, no agent, no API calls. Directly tests Q1.

1. **Construct a realistic briefing file-set** for the recall task: the files a prepper would
   plausibly pull as exemplars for "add a new browse screen" — e.g. 2-3 existing feature screens
   (`features/set-v3/*`, `features/cards-v3/*`), their hooks, `data/apiClient.ts`, `data/repository.ts`,
   `domain/models/*`, `layouts/Layout.astro`, a `*.module.css`. Place the foundations LAST (worst case
   for FIFO). Total set must exceed the budget under test.
2. For `budget in {6000, 4000, 3000, 2000, 1500}` and `strategy in {fifo, scored, topological}`, run
   `build_deterministic_context(briefing, budget, topological=..., scored=...)` and record which files
   survive in `files_selected`.
3. **Metric:** foundation-survival rate = fraction of the high-in-degree foundations (apiClient,
   repository, Layout, models/Common, design tokens) that survive, per strategy per budget.
4. Reuse the harness shape of `archolith-context/scripts/assembly_strategy_sweep.py` (now with the
   real extractor instead of the hand map). Write results to `rung3/RESULT-phaseA-offline.md`.

**Pre-registered Phase-A decision rule:** topological EARNS the live test IFF its foundation-survival
rate >= FIFO at every budget and strictly > FIFO at >=2 budget levels. If topological does NOT beat
FIFO offline, STOP — do not spend money on Phase B; investigate extraction coverage (R3a) first.

## Phase B — LIVE agent run (BLOCKED until the leaked metered OpenAI key is rotated)
Tests Q2. Mirrors the Phase-5 harness (`PROTOCOL.md` setup), three arms, byte-identical prompts led
by Claude via the harness PTY, ONE agent model held constant.

### Arms (only the context layer varies)
| arm | proxy config | isolates |
|-----|--------------|----------|
| A1 passthrough | no curation | raw baseline |
| A2 curator + FIFO | `ASSEMBLER_TOPOLOGICAL_FILL=false`, `ASSEMBLER_SCORED_SELECTION=false` | curator, insertion-order eviction |
| A3 curator + topological | `ASSEMBLER_TOPOLOGICAL_FILL=true` | + foundations-first eviction |

(Scored (Phase-4) is omitted from the primary comparison — the offline sweep already placed it below
topological; add as A4 only if Phase A shows it competitive.)

### Pressure guarantee (REQUIRED — Phase 5's failure mode was no pressure)
The briefing file-set MUST exceed `ASSEMBLER_TOKEN_BUDGET`. Ensure via: (a) a task that legitimately
pulls many exemplar files, AND (b) if the briefing still fits, lower `ASSEMBLER_TOKEN_BUDGET` (e.g.
to 3000) to force contention — documented as a knob, not hidden. Verify per turn via
`proxy_status.py metrics` that `deterministic_assemblies` climbs and that `files_selected` <
briefing file count (i.e. eviction actually happened). A run with no eviction is INVALID.

### The recall task (under-specified; NO convention names)
Lead a new screen the app does not already have, consistent with the existing browse screens, e.g.:
> "Add a Decks browse screen, consistent with the rest of the app. It lists decks, each showing its
>  total market value."
NEVER name `apiClient` / `repository` / `Layout` / the `*.module.css` pattern / the `features/<name>/`
folder structure. Run ~3-4 such screens (Decks, Bundles, Promos) so recall is measured across pages.

### Recall metric — REUSE the Rung-1 contract checker (automated, deterministic)
Derive a contract from THIS corpus's dominant conventions and run
`experiments/context-quality/contract/contract_check.py` over each arm's generated screen. The
contract IS the recall scorer (unifies rungs 1 and 3). Anchors to encode for the TS corpus:
1. imports the data layer via `data/apiClient` / `data/repository` (not raw `fetch`),
2. uses a `*.module.css` per the feature-folder convention (not inline styles / a new global sheet),
3. lives under `features/<name>/` with a `use<Name>Data` hook (the established structure),
4. uses shared `domain/models` types and `domain/formatters` (not re-declared shapes),
5. renders inside the shared `Layout` shell.
Score each generated screen 0/1 per anchor; per-arm recall = mean across the screens.

### Cost ground truth
Helper tokens (`curator_*` + `extractor_*` + `embedding_tokens`) from `proxy_status.py metrics`, priced
on the gpt-4.1-mini ladder; upstream prompt+completion from the trace. Read the dashboard delta per arm.
passthrough ~0 helper.

## Pre-registered decision rule (Phase B)
- **Topological earns its keep** IFF A3 recall > A2 recall on the same screens, at no material extra
  cost (topological is a sort — cost delta should be ~0). If equal -> topological is recall-neutral
  under this pressure (keep off by default; the offline foundation-survival win stands as the
  mechanism result). If A3 < A2 -> topological HURT (investigate: did it evict a query-relevant leaf
  to keep a never-used foundation? -> the foundations are not the recall-critical files here).
- **The combo beats doing nothing** IFF A3 (or A2) recall >= A1 passthrough. If passthrough wins
  (raw code keeps exact conventions verbatim), document it — that is the real, publishable finding
  (curator trades recall for compression even under pressure).

## INVALID runs (discard, don't rationalize)
- No eviction occurred (briefing fit the budget) -> not a pressure test; raise pressure, re-run.
- All arms recall everything / nothing -> task too easy / too hard or corpus not loaded; re-tune.
- Curator never fired on A2/A3 (verify `mode=curator` + `deterministic_assemblies` climbing).
- Upstream 5xx / 429 mid-run (note + re-run; obey the rate-limit protocol — STOP on 429).
- Extractor changed between arms (R3a must be done before, not during).

## Threats to validity (be honest in the writeup)
- **Extraction coverage (42% no-edge):** if the recall-critical files are among the MISSED edges,
  topological can't protect them. Phase A foundation-survival is only as good as the extraction; R3a
  may be a prerequisite, not optional.
- **Foundation != recall-critical:** high in-degree (apiClient, Layout) may not be what the agent
  needs to RECALL a convention; the recall-critical file might be a low-in-degree exemplar screen.
  This is the central risk; Phase B's contract metric, not Phase A, settles it.
- **Stochastic agent:** one session per arm; generation style varies. Lead identical prompts; if
  budget allows, N=2-3 seeds per arm and report variance.
- **Budget-knob artifact:** lowering `ASSEMBLER_TOKEN_BUDGET` to force pressure is a lever, not the
  real default; report results at the real 6000 too if natural pressure exists.

## Artifacts
- `rung3/analyze_corpus.py` — reproducible corpus characterization (run to regenerate the numbers).
- `rung3/RESULT-phaseA-offline.md` — (to be written when Phase A runs).
- `rung3/RESULT-phaseB-live.md` — (to be written when Phase B runs, post key-rotation).
