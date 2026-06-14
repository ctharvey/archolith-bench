# Context-Quality Experiment -- PRE-REGISTERED PROTOCOL

**Question:** Does a curated/compressed context make a real agent produce an equal-or-better
product, FASTER, at lower net cost -- because of higher-quality context -- on a long autonomous
agentic task? This tests what the Phase-4 cost bench could NOT: the second-order effect of context
quality on agent BEHAVIOR (wasted turns, re-reads, losing the thread, reaching the goal).

Pre-registered before any run, so the result cannot be rationalized post-hoc.

## Arms (agent held constant; only the context layer varies)

All three route the SAME agent through the proxy at localhost:9800; the proxy forwards to the same
upstream. The arm is the proxy's context mode:

| arm | proxy mode | isolates |
|-----|-----------|----------|
| **direct** | passthrough (no manipulation) | baseline: raw context, but TRACED for tokens |
| **mechanical** | curator OFF, levers ON (shrink/dedup/compress-middle + filter) | deterministic compression only |
| **full** | curator ON + levers | + LLM curator |

`direct` is measured via passthrough mode (byte-identical tokens to true no-proxy direct, but the
proxy trace captures usage -- solves the \"no token count on direct\" problem). The **mechanical->full
delta is the curator's marginal value**.

## Fixed (held constant across arms)

- **Agent:** one opencode agent, deepseek-v4-flash, same system prompt, same tool set, same turn/
  time budget.
- **Upstream:** wafer deepseek-v4-flash (fresh account) -- same for all arms.
- **Task:** `task-microtemplate/` -- implement `microtemplate.render()` to pass the 26-test
  acceptance suite (`tests/test_microtemplate.py`). The agent sees SPEC.md + the failing tests; goal =
  all green. Long-horizon, iterative (build -> run tests -> fix), objectively scored. Repo is RESET
  to the stub between runs.
- **N:** >= 3 runs per arm (agentic runs are high-variance; median across runs).

## Metrics (pre-registered -- all three reported per run, median per arm)

1. **Outcome** (primary): acceptance tests passing / 26 at the agent's stop. Binary \"reached goal\" =
   26/26.
2. **Efficiency:** turns (agent steps) and wall-clock to goal (or to budget exhaustion).
3. **Net cost:** upstream prompt+completion tokens + helper tokens (curator/extractor/embedding from
   the proxy trace), priced across the v4-flash / v4-pro / opus-4-8 ladder. (Helper tokens are 0 on
   direct + mechanical; nonzero on full.)

## Pre-registered decision rule

The curator (full) earns its keep IFF, on the median of N>=3 runs, it BEATS mechanical on the
**composite**: reaches the goal at >= the pass rate, in <= the turns, at a total cost whose premium
(helper + cache-bust) is justified by the outcome/turn improvement. Concretely:

- If **full** reaches 26/26 where **mechanical**/**direct** do NOT (or in materially fewer turns),
  the curator's context quality is a real win even at higher per-turn cost -> the Phase-4 \"drop the
  curator\" conclusion is OVERTURNED for agentic work.
- If **full** matches mechanical on outcome+turns but costs more -> curator is dead weight; Phase-4
  stands.
- If **mechanical** matches **direct** on outcome+turns -> even deterministic compression buys no
  quality; the whole context layer is cost-only (Phase-4 stands, strongly).

This rule is fixed now. Whatever the numbers say, we apply it.

## What would make a run INVALID (discard, don't rationalize)

- Task too hard: all three arms score ~0/26 -> no signal (re-pick an easier task).
- Task too easy: all three one-shot 26/26 in ~equal turns -> no context pressure (re-pick harder).
- Upstream/rate-limit failure mid-run (note and re-run).
- Agent crash unrelated to context (harness fault).

## Setup gate (NOT yet done -- see SETUP.md / status)

1. Point the proxy upstream at wafer deepseek-v4-flash (credential handled operator-side).
2. Fix the opencode `archolith` route: currently -> dead :9801; must -> :9800. Generated config ->
   edit mcp-registry.json + regenerate via agentsmith (NOT hand-edit opencode.json).
3. Proxy config per arm: passthrough (direct), curator-off (mechanical), curator-on (full).
   `.env.curator-on-bak` reverts to curator-on.
4. Per-run: reset task repo to stub; launch agent on the route; capture trace (tokens) + turns +
   wall-time; then run the hidden suite for the outcome score.
