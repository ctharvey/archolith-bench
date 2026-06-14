# Context-Quality A/B -- Result (2026-06-14)

**Setup:** opencode agent (deepseek-v4-flash via wafer), same open-ended goal (build a CLI Kanban
app), two arms through the archolith proxy -- `passthrough` vs `full` (curator route) -- run
side-by-side via the harness. N=1.

## THE HEADLINE FINDING: the curator never ran (and structurally can't, for an agent)

The "full" arm's trace (`ses_138b368b9`, 20 turns): **18 agent_solo turns, 2 passthrough, 0 curator
turns.** `curator_prompt_tokens = 0` on every turn. The extractor fired (3,634 tokens) and the
mechanical levers fired on 16 turns (24,032 tokens saved), but **the LLM curator was never invoked.**

Why: dispatch logic `is_agent_solo = ... and not is_user_turn` (chat.py:459). An autonomous coding
agent's conversation is almost entirely **tool-continuation turns, not user turns**, so every such
turn routes to the **agent-solo / mechanical path and bypasses the curator**. The curator only fires
on genuine user turns, which a one-shot agentic build barely has.

**Consequence:** this run did NOT compare curator-vs-passthrough. It compared
**mechanical-levers+extractor vs passthrough** -- because for a tool-using agent, "full" and
"mechanical" collapse to the same path. The clean curator test would require a CHAT-style task
(many user turns), not an autonomous tool loop.

This is the most important result, and it reinforces Phase-4 + the strategy plan: **the curator is a
chat-turn mechanism; agentic work gets the mechanical levers.** For a coding-agent proxy -- the actual
use case -- the curator is largely irrelevant; the meaningful question is mechanical vs passthrough
(Phase-4: break-even on cheap upstreams, win on expensive ones).

## Product quality (with the confound noted)

Both arms produced complete, working apps: all 7 subcommands, JSON persistence, error paths exiting
non-zero. Judged on identical functional + edge-case probes (output + exit codes):

| | passthrough | full (=mechanical path) |
|---|---|---|
| build time | **54.6s** | 2m 28s |
| card IDs | stable integer IDs (`[1] Write tests`) | **none -- addresses cards by title** (fragile; dup titles collide) |
| add-card args | title required; description/priority optional w/ default | description + priority **mandatory positionals** |
| move/delete | by id | by title |
| spec fidelity | higher (ids implied by "delete a card") | lower (no ids) |
| works on own interface | yes | yes |

Passthrough produced the better-designed product (stable ids, sensible optional fields) and was ~2.7x
faster. **BUT:** since the curator never ran, the two arms were NOT mechanically different in a way
that should drive a design-quality gap. The most likely explanation for the difference is **single-run
variance in deepseek's design choices** (it picked a weaker CLI shape on the full run), not a
context-strategy effect. N=1; do not over-read the quality delta.

## Cost (full/mechanical arm, measured)

- upstream input seen: 188,939 tokens; mechanical levers saved 24,032; extractor helper: 3,634;
  curator helper: 0.
- passthrough arm: passthrough mode skips detailed per-turn tracing, so clean per-turn tokens weren't
  captured -- a measurement gap to fix (the chat-response `usage` would need logging for that arm).

## Honest verdict

- **Did NOT answer "does the curator build a better product"** -- the curator didn't engage for an
  agentic client. Methodology gap, now understood.
- **Did reveal something more useful:** for tool-using agents, the curator is bypassed by design;
  context optimization for agents = the mechanical levers. This is structural, not run-variance.
- **Product quality:** passthrough's app was better + faster this run, but with the curator absent the
  arms were near-identical mechanically, so attribute the gap to N=1 variance, not the proxy.

## To actually test the curator's quality value (next)

1. Use a **chat-style task with real user turns** (the curator's regime), not an autonomous agent
   tool loop -- OR accept that for the agent use case the curator is moot and only mechanical matters.
2. N>=3 per arm (the design-choice variance here shows why one run is not enough).
3. Log the passthrough arm's response `usage` so both arms have comparable token counts.
4. If testing the agent case: the real arms are **passthrough vs mechanical** (curator on/off makes
   ~no difference for agents) -- confirm the curator-off vs curator-on traces are near-identical for an
   agentic client, which would close the question.
