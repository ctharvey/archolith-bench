# Workflow: Context-Quality A/B (does curated context build a better product?)

Measures what the **cost bench cannot**: whether a context strategy (curator / mechanical /
passthrough) makes a real agent produce an **equal-or-better product, faster, at justifiable cost**,
on an open-ended agentic build. Cost is one axis; **product quality is the other**, and for agentic
work it often dominates. This workflow captures the methodology and the traps that wasted iterations
the first time -- read it before running another arm comparison.

## When to use this (vs the cost bench)

- **Cost bench (`archolith-bench proxy`)**: scripted scenarios, fixed turns, measures tokens/cache/
  cost per turn. Answers "what does compression cost." Cannot see agent behavior.
- **This workflow**: a live agent builds an open-ended deliverable; you judge the PRODUCT. Answers
  "does better context make the agent work better." Use when a cost verdict says "compression is
  break-even/negative" but you suspect a quality benefit the cost number can't capture.

## The five hard-won rules (each one cost an iteration)

1. **Standardized GOAL, not a standardized TEST.** Give every arm a byte-identical goal prompt, but
   the deliverable must be OPEN-ENDED so quality can vary. A frozen acceptance suite (templated task)
   measures only convergence to one answer -- context quality has nowhere to show. Judge by comparing
   the PRODUCTS, not by a pass/fail gate the task can game.
2. **Only the context layer varies.** Same agent, same model, same upstream, same goal. The ONLY
   difference is the proxy's context mode. Anything else confounds the result.
3. **Run real agent sessions through the harness -- NOT a hand-rolled chat driver.** The full product
   includes interactive tools (e.g. the session-recall tool) that require a tool-executing client. A
   plain chat-completions loop stalls on the tool handshake on turn 1 and you measure a harness
   artifact, not the curator. The harness (opencode PTY session) services the full tool loop.
4. **The arm is the proxy MODEL ROUTE, not a proxy restart.** Passthrough is selected per-request by
   the `-passthrough` model suffix (`chat.py::_handle_passthrough_*`). So `deepseek-v4-flash`
   (curated) and `deepseek-v4-flash-passthrough` (raw) run against the SAME curator-on proxy with no
   restart -- identical proxy state, only the route differs. (Mechanical-only = a separate proxy
   config: CURATOR_ENABLED=false, levers on -- that one needs a restart.)
5. **Judge the product objectively + pull cost from the trace.** Run each arm's deliverable through
   identical functional AND edge-case probes (check output correctness AND exit codes). Pull tokens
   from the proxy trace / `/metrics` (upstream in/out + helper curator/extractor tokens), price across
   the v4-flash / v4-pro / opus-4-8 ladder. Report quality, efficiency (turns/walltime), net cost.

## Arms

| arm | proxy mode | model route | isolates |
|-----|-----------|-------------|----------|
| **passthrough** | no manipulation (instrument baseline) | `archolith/deepseek-v4-flash-passthrough` | raw context, traced |
| **mechanical** | curator OFF, levers ON | `archolith/deepseek-v4-flash` (proxy CURATOR_ENABLED=false) | deterministic compression |
| **full** | curator ON + levers | `archolith/deepseek-v4-flash` (proxy CURATOR_ENABLED=true) | + LLM curator |

passthrough vs full run against ONE curator-on proxy (route suffix switches). mechanical needs its
own curator-off proxy run. The **mechanical->full delta is the curator's marginal value**.

## Procedure

### 0. Pre-register (before any run)
Write PROTOCOL.md: the goal prompt (verbatim), arms, metrics (outcome/turns/walltime/net-cost), the
decision rule (when does the curator "earn its keep"), and INVALIDATION conditions (all arms fail =
task too hard; all one-shot = too easy; upstream/rate-limit failure = re-run). Fix the rule now so
the result can't be rationalized post-hoc.

### 1. Wire the upstream + route
- Proxy `.env`: `UPSTREAM_BASE_URL` + `UPSTREAM_API_KEY` + `BENCHMARK_MODEL` -> the chosen upstream
  (a fresh/cheap account like wafer deepseek-v4-flash avoids burning prod credit). Back up `.env`
  first (`.env.pre-<x>-bak`).
- opencode `archolith` route -> proxy port (`:9800`), models `deepseek-v4-flash` +
  `deepseek-v4-flash-passthrough`. This is a GENERATED config: edit
  `cth.agentsmith/mcp-registry.json` -> `python sync.py validate && diff && generate`. Never
  hand-edit opencode.json.
- Set curator state for the arm: full = CURATOR_ENABLED=true (+ BACKGROUND_PASS_ENABLED=true);
  mechanical = false. `python scripts/proxy_restart.py`. Keep `.env.curator-on-bak` to revert.
- Smoke each route: one chat call returns content + `usage` (prompt/completion/cached tokens).

### 2. Launch the arms (harness, side-by-side)
- `harness_health` (start the harness if down: `cth.harness/restart.ps1`).
- One clean cwd per arm under `experiments/context-quality/oc/<arm>/`.
- `harness_start_session` per arm: agent=opencode, the route model, cwd=the arm dir, the verbatim
  goal as task. opencode has no auto-approve flag in the harness -- omit autoApprove (it uses the
  first-message `--auto-approve-all`). The 2nd arm trips the duplicate-task guard -> `forceNew=true`.
- `harness_show_comparison(left, right)` -> side-by-side dashboard so the operator can watch.
- Confirm both progress (not stuck on an MCP-consent dialog; proxy `total_requests` climbing).

### 3. Judge (after both finish)
- Functional probes: run each `kanban.py` (or whatever the goal was) through identical happy-path
  commands. Edge cases: missing entities, invalid inputs -- check OUTPUT and EXIT CODE.
- Score each arm: built a working app? feature-complete? error-handling correct? code quality?
- Cost: sum each arm's trace (upstream in/out, helper curator/extractor/embedding tokens); price
  across the ladder. passthrough/mechanical have ~0 helper; full is nonzero.
- Head-to-head -> RESULT.md: quality (which product is better + why), efficiency (turns/walltime),
  net cost (incl. helper), and the verdict against the pre-registered rule.

## Gotchas (observed)
- **Windows console UnicodeEncodeError** on agent output with arrows/box-chars: set
  `PYTHONIOENCODING=utf-8` and wrap stdout, or read replies from a sidecar file.
- **opencode auto-rejects reading outside its cwd** ("external_directory ... auto-rejecting"). Put
  the task files IN the session cwd; tell the agent to work entirely within it.
- **Harness down after an OOM/reboot** -> MCP "Unable to connect." Restart via `restart.ps1`, then
  `harness_health` to reconnect. (A vmmemwsl WSL memory leak OOM'd a prior long run -- watch memory.)
- **opencode `run` (raw CLI) buffers all output to the end** and gives no live progress -- another
  reason to use the harness PTY session, not raw `opencode run`.
- **Trace files are per-session** (`ses_*.jsonl` for opencode sessions); passthrough mode may not
  write a `turn_number`-keyed trace -- fall back to the chat-response `usage` for token counts.

## Artifacts
- `experiments/context-quality/PROTOCOL.md` (pre-registered), `RESULT.md` (verdict),
  `oc/<arm>/` (each arm's deliverable + agent.log).
- Cost model + pricing ladder: `archolith_bench/core/metrics.py`, `pricing/*.json`.

## CRITICAL: exactly when the curator fires (and why naive runs see curator_tokens=0)

CORRECTED 2026-06-14 (an earlier version of this note wrongly concluded "the curator never runs for
agentic clients" -- that was a misdiagnosis: those runs simply never cleared COLD START).

The curator fires on a request only when ALL of these hold (chat.py):
1. **is_user_turn** -- the request's LAST message is a user message (line 430/488). opencode's
   tool-CONTINUATION requests end in a tool result -> is_user_turn=False -> they take the
   agent-solo/mechanical path (line 459), NOT the curator. That is correct and expected.
2. **past cold start** -- `user_turn_count >= COLD_START_TURNS` (default 3, line 537). The first 3
   USER turns of a session always passthrough (`_curator_skip="cold_start"`), regardless of size.
3. **input >= ASSEMBLY_MIN_INPUT_TOKENS** (default/bench 5000, line 490). Below the gate -> passthrough.

So a real agentic session DOES exercise the curator -- on its USER turns, once past the 3-turn cold
start with >=5k input. The tool-continuation turns in between still get the mechanical path (the
realistic mix). What fooled earlier runs: a one-shot autonomous task = only 1-2 user turns total
(all inside cold start) + many tool turns -> curator_tokens=0, NOT because "agents bypass the curator"
but because **we never reached user turn 4**.

### How to actually exercise the curator via the harness (the proper method)
- Use a harness opencode session and **LEAD it page-by-page**: each `harness_resume_session(message=...)`
  is a fresh USER turn. Direct ENOUGH steps (>=4-5+ user turns) to clear cold start.
- From user turn 4 onward, with accumulated history >=5k, the curator fires on each directed user
  turn. Verify: the session's `ses_*.jsonl` trace should show `assembly_mode=curator` +
  `curator_prompt_tokens>0` on the later user turns (early ones show passthrough = cold start).
- Don't bail after 1-3 turns and conclude the curator "doesn't run" -- that is just cold start.

### Always verify the path
Check `assembly_mode` counts + `curator_prompt_tokens` in the trace before trusting an arm label.
curator_tokens=0 on a SHORT session = cold start (expected), not "curator broken." Passthrough mode
skips detailed per-turn tracing -> fall back to chat-response `usage` for that arm's tokens.

### CONFIRMED 2026-06-14 (mobile-build run): the harness DOES exercise the curator
Lead-directed opencode session `ses_1379d1f4e`, verified via `proxy_status.py turns <ses>`:
```
turns=23  max_user_turns=4  modes={passthrough:3, agent_solo:18, curator:2}
USER 0,1,2 -> passthrough   (cold start, COLD_START_TURNS=3)
USER 3     -> curator        (14,047 input tokens: past cold start AND > 5000 gate)  <-- curator fires
```
Each `harness_resume_session(message=...)` = one new USER turn (the USER counter climbs); opencode's
tool-loop requests inside each turn are agent_solo. The curator engages from user turn 3 onward once
input exceeds the gate. KEY: a one-shot `opencode run` autonomous task registers only ~2 user turns
total (e.g. ses_138b368b9: 20 turns but USER=2) -> never clears cold start -> 0 curator. To exercise
the curator you must LEAD many separate resume turns. VERIFY with `proxy_status.py turns <ses>` (look
for mode=curator rows), not just curator_tokens in the raw jsonl.

---

## RESUME / HANDOFF (2026-06-15 00:15Z) — two_curator seeded recall test IN PROGRESS

### The big correction (read first)
All curator runs through Run-4 tested the WRONG mode. `curation_mode` defaulted to **`two_pass`**
(the turn-curator does its OWN 6-iteration tool-calling per turn -> hit `max_iterations(6)` and fell
back to passthrough). The intended architecture is **`two_curator`**: a background **prepper**
(`run_prepper`, generous iteration budget) pre-builds a `SessionBriefing`; a lightweight per-turn
**assembler** (`run_assembler`) just SELECTS from the briefing (shouldn't re-fetch). Set
`CURATION_MODE=two_curator` in archolith-context/.env. Verified registered in
data/proxy_latest_err.log: `curation_mode_configured mode=two_curator prepper/assembler=gpt-4.1-mini`.
STILL TODO: verify the prepper background pass actually FIRES on a curated turn (look for
prepper/briefing events in the trace/err-log once a session is past cold start), not just registered.

### Current proxy config (archolith-context/.env) — all verified
- CURATION_MODE=two_curator, CURATOR_ENABLED=true, BACKGROUND_PASS_ENABLED=true
- COLD_START_TURNS=3, ASSEMBLY_MIN_INPUT_TOKENS=5000, SESSION_RECALL_TOOL_ENABLED=false
- CURATOR_MODEL=EXTRACTOR_MODEL=gpt-4.1-mini (OpenAI); EMBEDDING_MODEL=text-embedding-3-small (OpenAI)
- Upstream = wafer deepseek-v4-flash. (User: wafer deepseek is SUBSTANDARD vs direct API — quality floor.)
- Backups to revert: .env.pre-twocurator-bak, .env.pre-testkey-bak, .env.curator-on-bak, .env.pre-wafer-bak
- Proxy on :9800. Restart: `python scripts/proxy_restart.py`. Logs: data/proxy_latest{,_err}.log
- Verify curator engagement: `python scripts/proxy_status.py turns <ses>` (mode=curator rows) and
  `proxy_status.py sessions` (USER/CURATOR counts). assembly_reason=max_iterations(N) = assembler fell back.

### COST: metered key + how to calculate (validated)
A DEDICATED OpenAI key (project proj_HarxQbRu) is set on EXTRACTOR_API_KEY + CURATOR_API_KEY +
EMBEDDING_API_KEY so ALL helper spend lands on one project = ground truth. VALIDATED: trace token
counts MATCH the OpenAI dashboard (trace ~54-60k vs dashboard 53.5k). The earlier "$0.11" estimate was
a STALE-KEY artifact (old key wasn't billing); real cost is ~$0.02/partial-run. Pricing gpt-4.1-mini:
$0.40/M input, $0.10/M CACHED input (curator prefix ~85% cached), $1.60/M output; text-embedding-3-small
$0.02/M. **Meter baseline before the seeded test = 75.001K input tokens** (read the dashboard delta after).
SECURITY: the metered key was pasted in plaintext in chat — user should ROTATE it after testing.

### The SEEDED recall test (the clean design, fixes all prior confounds)
WHY: prior runs were confounded — (1) each arm coined a DIFFERENT row convention at turn 2 in
cold-start passthrough (variance, not curator effect), then stayed self-consistent; (2) the two_pass
curator fell back to passthrough mid-test. FIX: seed BOTH arms with byte-identical starting files so
the recall target is the same; only context management varies.
- Files: experiments/context-quality/seeded/_seed/ = canonical mobile.css (.list-row + tokens
  --accent/--muted), api.js (named helpers setsMatrix/cardSearch/sealedList/...), cards.html (USES
  .list-row + cardSearch), card-detail.html (back-header pattern). Copied into seeded/full and seeded/pass.
- Arms: full = `archolith/deepseek-v4-flash` (two_curator), pass = `archolith/deepseek-v4-flash-passthrough`.
- METHOD (lead page-by-page via harness_resume_session; each resume = 1 USER turn):
  - Turn 1: "Read the 4 existing files, confirm conventions, write nothing." (loads conventions into history)
  - Turns 2-3: under-specified pages (cold-start passthrough on BOTH arms — build history, not differentiating)
  - Turn 4+: under-specified pages -> full=curator, pass=passthrough = THE comparison. Run ~4-5 curated pages.
  - Under-specified prompt style (NO anchor names): "Now add the Sealed products browse screen,
    consistent with the rest of the app. It lists sealed products, each showing its expected value (EV)."
    NEVER name .list-row / --accent / the api helper / the file — force RECALL from context.
- RECALL METRIC per page (grep each new screen): reused .list-row? used --accent token? used the
  correct named api helper? reused back-header (detail screens)? Compare full vs pass on the SAME page.
- HYPOTHESIS to test: passthrough keeps RAW code so exact .list-row/--accent survive verbatim;
  curator DISTILLS -> may keep "use api.js helpers" but lose exact class names. Two_curator (prepper
  briefing) may preserve more than two_pass did. Measure, don't assume.
- ACTIVE SESSIONS (started, may be alive): seeded-full-20260615 (turn 1 sent, reading files).
  seeded-pass NOT yet started — start it with the same turn-1 file-review task, forceNew=true.

### Status at handoff
two_curator enabled+registered, embedding confirmed OpenAI, both arms seeded identically, full arm
turn-1 (file review) sent. NEXT: confirm full turn-1 done, start the pass arm (same turn-1), then lead
both through identical under-specified pages past cold start, verify the prepper fires on full,
recall-audit each page head-to-head, pull cost delta off the meter. Prior results: RESULT.md Runs 1-4
+ DESIGN ANALYSIS (all on the degraded two_pass mode — re-interpret in that light).

---

## RESOLVED (2026-06-15) — event-driven curator worker landed; prepper FIRES reliably

The handoff's open question ("verify the prepper background pass actually FIRES on a curated turn,
not just registered") is ANSWERED, and the firing was made reliable by the event-driven worker.

- **Phases 0-1 of the event-driven-worker plan are implemented** on
  `archolith-context` branch `feat/event-driven-curator-worker`:
  - Phase 0 instruments the failure: `/metrics` now has a `curator_worker_diag` block —
    `prepper_fires`, `prepper_starved` (skipped on tool-call/non-user turns), `prepper_cancels`
    (killed by next turn), `hot_path_llm_calls`, `avg_briefing_lag_turns`.
  - Phase 1 adds a long-lived per-session worker (`curator/worker.py`), flag-gated by
    `CURATOR_WORKER_ENABLED=true`, that feeds the prepper on EVERY turn boundary, debounced and
    with no cancel-on-next-turn.
- **The gate caught a real wiring bug first**: the worker enqueue was initially left behind the
  same `is_user_turn/tool_calls` guard that starves the legacy prepper, so an agentic opencode
  session reproduced the starvation (`prepper_fires=0, prepper_starved=2`). Fixed by decoupling
  the enqueue (commit `0f28897`); the legacy guard only applies in worker-off mode.
- **Live result** (led opencode session `gate-full-20260615`, route `deepseek-v4-flash`,
  `CURATION_MODE=two_curator`): after the fix the worker fires reliably —
  `prepper_fires` climbs 1:1 with completed turns, `prepper_starved=0`, `prepper_cancels=0`,
  the prepper pass completes (`prepper_complete` in the err-log, `background_pass_successes`
  increments), and the hot path consumed a briefing (`briefing_reads=1`, `avg_briefing_lag_turns=1.0`
  fresh). This is the steady-state win the plan predicted.

### Metrics now work for the two_curator + worker setup (same session)
Three `/metrics` gaps this run exposed are fixed:
- `record_assembly_mode()` was never called in chat.py, so `assembly_modes` was permanently 0.
  Now counted for curated AND passthrough requests.
- Helper-LLM token totals (`extractor_*`, `curator_*`, `embedding_tokens`) and
  `background_pass_successes` were recorded but never returned by `/metrics`. Now surfaced under
  a `helper_tokens` block + `background_pass_successes`.
- The background prepper's curator-model token spend is now recorded into `curator_*_tokens_total`,
  so two_curator cost is visible (was 0 despite the prepper running the curator model).

### Passthrough is now recorded like a non-passthrough session
Passthrough requests count in `assembly_modes` (`passthrough`) and record
`total_input_tokens_seen`, so the A/B passthrough arm is recorded symmetrically. (Note: passthrough
still uses the synthetic benchmark session id with `turn_number=0` by design — per-turn token totals
still aggregate under that session in the trace store; the chat-response `usage` fallback noted above
is no longer required just to see passthrough traffic in `/metrics`.)

---

## Broader thread (umbrella record + architecture direction)

This A/B work is one strand of the archolith **Curator Economics & Architecture Investigation**. The
consolidated cross-project record lives at the umbrella:
`projects/archolith/.agent/RESEARCH-FINDINGS.md` (section "Curator Economics & Architecture
Investigation"). Key downstream conclusions that reframe this workflow:
- The curator's `max_iterations` fallbacks are a **request-coupled SCHEDULING failure** (prepper starved
  + cancelled), not a curator-logic bug. Mode was `two_pass` (default), not the intended `two_curator`.
- Direction: an **event-driven curator worker + deterministic session ledger** (plan:
  `projects/archolith/.agent/plans/archolith-context-event-driven-curator-worker-plan.md`). Once it
  lands, the curator reliably has a briefing and THIS A/B finally yields a fair curator-vs-passthrough
  answer. **UPDATE 2026-06-15: Phases 0-1 landed** (worker fires reliably — see the RESOLVED section
  above); Phases 2-5 (deterministic LLM-free hot-path read, WAL durability, ARC eviction, the seeded
  recall measurement) remain. The fair A/B is now unblocked once a fresh briefing is reliably present.
- `cth.mcp.memory` (-> `archolith.memory`) already runs the background-maintenance pattern (scheduler
  lease, enrichment queue, decay/lifecycle); the two projects live in tandem with intent to extract
  shared tooling. Reuse, don't reinvent.
- COST: trace token accounting is validated against a metered OpenAI key; helper cost is ~$0.02/run
  (cheap) -- the real costs are latency + upstream bloat, not dollars.
