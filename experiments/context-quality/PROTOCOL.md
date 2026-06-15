# Context-Quality Seeded-Recall A/B — PRE-REGISTERED PROTOCOL

**Supersedes** the earlier microtemplate acceptance-suite pre-registration (RESULT.md Runs 1-4, run on
the degraded `two_pass` mode). This is the **seeded-recall** design on the landed event-driven
`two_curator` + worker pipeline, extended with a third arm that isolates **Phase 4 scored selection**.

Pre-registered before any run so the result cannot be rationalized post-hoc.

## Question
On an open-ended agentic build where the right answer must be RECALLED from earlier context (not
re-derived), does the curator deliver equal-or-better recall than raw passthrough — and does **Phase 4
scored file selection** improve that recall over the unscored curator? Recall = does the agent reuse
the exact conventions established in the seeded files when later prompts deliberately omit their names.

## Arms (agent + model + goal held constant; ONLY the context layer varies)
| arm | proxy mode | opencode model route | isolates |
|-----|-----------|----------------------|----------|
| **passthrough** | no manipulation (traced) | `archolith/deepseek-v4-flash-passthrough` | raw context baseline |
| **curator-off** | two_curator + worker, `ASSEMBLER_SCORED_SELECTION=false` | `archolith/deepseek-v4-flash` | LLM curator, FIFO file fill |
| **curator-on** | two_curator + worker, `ASSEMBLER_SCORED_SELECTION=true` | `archolith/deepseek-v4-flash` | + Phase 4 scored selection |

The **passthrough -> curator-off** delta = the curator's recall value vs raw.
The **curator-off -> curator-on** delta = **whether Phase 4 scored selection actually helps recall**
(the open question from building it).

## Fixed across arms (held constant — confounds if varied)
- **Agent model = DeepSeek.** Upstream = **direct DeepSeek API** (`https://api.deepseek.com/v1`), model
  `deepseek-v4-flash` (DeepSeek aliases `deepseek-chat`/`v4-flash` to the same chat model). NOT wafer
  (it 503'd `no_healthy_backends` mid-run before — quality floor + outage risk). One opencode agent,
  same system prompt + tool set, same per-turn budget.
- **Input is operator-led by Claude.** Each `harness_resume_session(message=...)` is ONE fresh USER
  turn. Claude sends byte-identical page prompts to every arm in the same order. This is required: a
  hand-rolled chat driver stalls on opencode's tool handshake (workflow rule 3); the harness PTY
  services the full tool loop. Lead >=4-5 user turns per arm to clear the 3-turn cold start.
- **Seed = identical starting files** for every arm, copied from `seeded/_seed/` into each arm's cwd:
  `mobile.css`, `api.js`, `cards.html`, `card-detail.html`. So the recall target is the same; only
  context management differs.
- **Curator gate left at realistic defaults:** `COLD_START_TURNS=3`, `ASSEMBLY_MIN_INPUT_TOKENS=5000`
  (do NOT lower — we want the real gating; the leading must accumulate >=5k history by turn 4).
  `SESSION_RECALL_TOOL_ENABLED=false`. Helper model gpt-4.1-mini on a metered key (cost ground truth).

## The seeded conventions the agent must RECALL (exact anchors from `_seed/`)
| convention | exact token | seeded in |
|---|---|---|
| list row class | `.list-row` (+ `.row-thumb`/`.row-body`/`.row-name`/`.row-sub`/`.row-meta`) | mobile.css, cards.html |
| accent color token | `var(--accent)` (#16a34a); sub-text `var(--muted)` | mobile.css |
| price/metric slot | `.row-meta` colored with `--accent` | mobile.css, cards.html |
| detail back-header | `<header class="detail-header"><a class="back-btn">` | card-detail.html |
| API helper style | named exports in `api.js` (e.g. `sealedList`, `cardSearch`, `setsList`) | api.js |

## Method (lead page-by-page; same prompts, same order, every arm)
- **Turn 1 (load):** "Read the 4 existing files and confirm the conventions. Write nothing." (loads the
  conventions into history; no deliverable.)
- **Turns 2-3 (warm-up, cold-start passthrough on ALL arms):** under-specified pages that build history
  but are pre-cold-start, so non-differentiating. e.g. "Add the Sets browse screen, consistent with the
  app." (No anchor names.)
- **Turns 4-7 (THE comparison — past cold start, curator fires on the curator arms):** under-specified
  pages with NO anchor names, forcing recall from context. Canonical example:
  > "Now add the Sealed products browse screen, consistent with the rest of the app. It lists sealed
  > products, each showing its expected value (EV)."
  NEVER name `.list-row` / `--accent` / `.row-meta` / `sealedList` / the file. Run ~4 such pages
  (Sealed, Graded, Series, Transactions — each maps to an existing `api.js` helper).

## Recall metric (per generated page, per arm — grep the produced file)
Score each of the turn 4-7 pages 0/1 on each anchor, then sum:
1. Reused `.list-row` (+ its `.row-*` children) rather than inventing a row class? 
2. Used `var(--accent)` / `var(--muted)` rather than hard-coded colors?
3. Put the metric (EV/price) in `.row-meta` with the accent?
4. Reused the `detail-header`/`back-btn` pattern on any detail screen?
5. Called the CORRECT named `api.js` helper (e.g. `sealedList`) rather than a raw `fetch`/new name?
Per arm = mean anchor-recall across the 4 comparison pages. **Primary comparison = curator-off vs
curator-on on the SAME pages; secondary = both vs passthrough.**

## Cost (pulled from the trace / metered key, per arm)
Upstream prompt+completion tokens + helper tokens (`curator_*` + `extractor_*` + `embedding_tokens`
from `proxy_status.py metrics` `helper_tokens`), priced on the v4-flash / v4-pro / opus-4-8 ladder.
passthrough has ~0 helper; both curator arms nonzero (curator-on may differ slightly via scoring).
Read the OpenAI dashboard delta around each arm for ground truth.

## Pre-registered decision rule (fixed now; applied whatever the numbers say)
- **Scored selection earns its keep** IFF curator-on's mean anchor-recall **exceeds** curator-off's on
  the same comparison pages, at no material extra cost. If equal -> scored selection is neutral on this
  task (keep it off by default, revisit signals). If WORSE -> scored selection hurts recall here ->
  do not enable; investigate why (likely keyword-relevance dropping a high-importance file).
- **The curator earns its keep** IFF curator-off (or -on) **>=** passthrough on recall. If passthrough
  wins (raw code preserves exact `.list-row`/`--accent` verbatim while the curator distills and loses
  them), that is a real finding: the curator trades recall for compression -> document, don't bury.
- HYPOTHESIS (test, don't assume): passthrough keeps RAW code so exact tokens survive verbatim; the
  curator distills and may keep "use api.js helpers" but lose exact class names; scored selection may
  recover some by keeping the most query-relevant seed file in budget.

## INVALID runs (discard, don't rationalize)
- All arms recall ~everything -> task too easy / pages too specific (tighten under-specification, re-run).
- All arms recall ~nothing -> task too hard / seed not loaded (verify turn-1 file read, re-run).
- Curator never fires on the curator arms (verify `proxy_status.py turns <ses>` shows `mode=curator`
  rows + `prepper_fires`/`briefing_reads` climbing; `curator_tokens=0` on a short run = cold start, not
  broken — lead more turns).
- Upstream 5xx / rate-limit mid-run, or harness fault (note + re-run).

## Setup / run sequence (per arm)
1. Proxy `.env`: upstream -> direct DeepSeek (`.env.pre-deepseek-swap-bak` is the reference); back up
   first. CURATION_MODE=two_curator, CURATOR_ENABLED=true, BACKGROUND_PASS_ENABLED=true,
   CURATOR_WORKER_ENABLED=true, PREPPER_LATENCY_BUDGET_MS=60000.
2. opencode `archolith` route -> `:9800`, models `deepseek-v4-flash` + `-passthrough`. GENERATED config:
   edit `cth.agentsmith/mcp-registry.json` -> `sync.py validate && diff && generate`. Never hand-edit
   opencode.json.
3. **Restart A — `ASSEMBLER_SCORED_SELECTION=false`** (`proxy_restart.py`). Run **passthrough** arm
   (route suffix) + **curator-off** arm against this one proxy (no restart between them; route differs).
4. **Restart B — `ASSEMBLER_SCORED_SELECTION=true`** (`proxy_restart.py`). Run **curator-on** arm.
5. Per arm: clean cwd `oc/<arm>/` seeded from `_seed/`; `harness_start_session` (agent=opencode, the
   route model, the turn-1 task); 2nd arm trips the duplicate-task guard -> `forceNew=true`. Lead turns
   2-7 via `harness_resume_session`. Verify curator engagement before trusting the arm label.
6. Recall-audit each turn 4-7 page head-to-head; pull cost off the meter; write `RESULT.md` verdict
   against THIS rule.

## Gotchas (from the workflow — pre-empt)
- `PYTHONIOENCODING=utf-8` for agent output with arrows/box chars (Windows UnicodeEncodeError).
- opencode auto-rejects reads outside its cwd -> keep all files IN the session cwd.
- Watch WSL memory (a vmmemwsl leak OOM'd a prior long run); `harness_health` after any restart.
- Passthrough writes a `turn_number=0` synthetic-session trace -> its tokens still show in `/metrics`
  `assembly_modes=passthrough`; fall back to chat-response `usage` only if needed.
