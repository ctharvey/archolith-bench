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

## CRITICAL GOTCHA (learned 2026-06-14): the curator does NOT run for agentic clients

An autonomous tool-using agent (opencode building something) produces almost entirely
TOOL-CONTINUATION turns, not user turns. Dispatch is `is_agent_solo = ... and not is_user_turn`
(chat.py:459) -> every tool-loop turn routes to the agent-solo/mechanical path and **bypasses the
LLM curator**. Observed: a "full curator" arm ran 18/20 turns agent_solo, **0 curator turns,
curator_tokens=0**. So for an agentic task, "full" and "mechanical" collapse to the SAME path.

Implications:
- To test the **curator's** value, use a **CHAT-style task with many real user turns**, NOT an
  autonomous agent build. Otherwise you're testing the mechanical levers and mislabeling it "curator."
- For the **agent use case**, the curator is structurally moot; the only meaningful arms are
  **passthrough vs mechanical**. Confirm by checking curator-on vs curator-off traces are
  near-identical for an agentic client.
- Always VERIFY the intended path actually ran: check `assembly_mode` counts + `curator_prompt_tokens`
  in the arm's trace before trusting an arm label. A "full" arm with curator_tokens=0 did not test
  the curator.
- Passthrough mode skips detailed per-turn tracing -> log the chat-response `usage` to get that arm's
  tokens.
