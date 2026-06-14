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

---

# RUN 2 (2026-06-14): VALID multi-turn curator test

Fixed the Run-1 flaw. This is a **12-turn complex task, lead-driven** (I send each user turn; later
turns CALL BACK to decisions/field-names the model made earlier -- testing cross-turn coherence).
Identical turn-script for both arms; only the proxy context mode varies. Recall TOOL disabled
(SESSION_RECALL_TOOL_ENABLED=false) so a plain driver works; CURATOR_ENABLED=true.

**This time the curator ACTUALLY RAN** (verified): full arm = 10/12 turns `curator` mode,
**108,804 curator tokens + 41,065 extractor tokens**. A real curator-vs-passthrough comparison.

## Result

| metric | passthrough | full (curator) |
|---|---|---|
| product works (__main__ runs) | yes | yes |
| cross-turn callbacks honored (8 structural) | 8/8 | 8/8 |
| Item contract (functional, 5 checks) | 5/5 | 5/5 |
| upstream input tokens | 33,253 | **37,188 (+12%)** |
| upstream output tokens | 8,222 | 8,966 |
| helper tokens (curator+extractor) | 0 | **149,869** |
| walltime | **80s** | 210s (2.6x) |

## Verdict: on this task the curator is strictly worse -- equal quality, higher cost

- **Zero quality gain:** both products are functionally equivalent. Every cross-turn decision (uuid
  string ids, integer-cents money, exact field names id/sku/name/quantity/unit_price/reserved,
  available(), to_dict with all keys, transfer-logging, from_json) was honored by BOTH arms. The
  curated context did not make the weak model more coherent than raw history did.
- **Higher cost:** the curator did not even COMPRESS here -- it sent +12% MORE upstream tokens
  (it injects recalled context), plus ~150k helper tokens, at 2.6x the walltime. Net strongly
  negative.

## The load-bearing caveat (why this isn't the curator's death knell)

At 12 turns the raw history maxed at ~7-9k input tokens -- **well within deepseek's context window**,
so passthrough never suffered lost-in-the-middle / overflow. With no context PRESSURE, curation has
nothing to fix, so it can only add cost. The curator's value proposition only kicks in when the
session is long enough that raw history DEGRADES the model (overflow, or attention dilution at much
greater length). This task did not reach that regime.

**So the honest finding:** for short-to-moderate sessions (within the model's comfortable context),
curation is pure overhead -- equal output, +cost, +latency. To find where (if) it wins, the next test
needs a session long enough to put real pressure on raw history (e.g. 40+ turns, or a deliberately
small-context model, or huge per-turn tool outputs). N=1; coherence checks are structural+functional
but not exhaustive.

## Combined Phase-4 + Run-1 + Run-2 picture

1. **Cost bench (Phase-4):** curator more expensive at every rung (cache-bust + helper).
2. **Run-1 (agentic build):** curator structurally bypassed (agent turns -> mechanical path).
3. **Run-2 (multi-turn chat, curator engaged):** equal quality, +12% upstream, +150k helper, 2.6x
   slower -- because the session never pressured the context window.

Across all three, the curator has yet to demonstrate a NET win. Its plausible niche narrows to:
long sessions that overflow raw history, in front of an expensive upstream, where a frozen
front-loaded prefix (per the strategy plan) -- not per-turn re-curation -- is the cache-friendly form.

---

# DESIGN ANALYSIS (2026-06-14): why the curator cost what it did, and the levers

Looked hard at the curator implementation + the Run-2 trace. The "108k curator tokens / strictly
worse" headline is misleading; the real cost structure is fixable. Findings:

## What actually drives curator cost (from the Run-2 trace)
- **It made ZERO tool calls** this run (`curator_tool_log` empty every turn). The multi-iteration
  tool-calling loop is NOT the cost here -- it ran as a single LLM pass per turn.
- **It is already 85% prompt-cached** (`curator_cached_tokens` = 78-93%/turn). The stable prefix
  (system prompt 1111 tok + 15 tool schemas) is cached at the provider; only ~14.6k of 101.5k prompt
  tokens were uncached.
- **Real dollar cost is small:** curator+extractor = **$0.05** total on gpt-4.1-mini (85% cached);
  **$0.011** if the curator ran on deepseek-v4-flash. The token COUNT is scary; the dollars are not.
- **The actual costs that hurt:** (1) **latency 2.6x** (210s vs 80s -- a serial gpt-4.1-mini round
  trip before each upstream call), and (2) **+12% upstream tokens** -- on this no-pressure task the
  curator INJECTED context instead of compressing.

## THE smoking gun: the size gate is effectively disabled
`ASSEMBLY_MIN_INPUT_TOKENS=100`. The curator eligibility gate EXISTS (chat.py:490 skips assembly
below the threshold) but is set to 100 tokens -- so the curator fires on basically every user turn.
On Run-2 (max ~9k raw history) it should never have run. **Raise the gate to ~15-20k and the curator
becomes a no-op on any session that fits comfortably in context** -- removing the +12% upstream, the
$0.05, AND the 2.6x latency. The curator only engages once raw history is genuinely large enough that
it might help. This single tuning change removes the universal downside.

## Concrete levers (ranked) to make the curator worth investigating
1. **Raise ASSEMBLY_MIN_INPUT_TOKENS 100 -> ~15-20k (trivial, biggest win).** Makes "curator on"
   strictly <= passthrough on normal sessions (no-op when it can't help). The gate already exists;
   it's just mistuned. After this, the curator only costs anything when there's real context pressure.
2. **Cheaper curator model (deepseek-v4-flash vs gpt-4.1-mini): 4.6x cheaper helper $, same-provider
   = lower latency.** Verify curation quality holds on the weaker model.
3. **Net-reducer injection gate.** The curator ADDED 12% upstream here. Only inject curated context
   when it DROPS more tokens than it adds (it should be a net reducer, not adder) -- else passthrough.
4. **Trim the tool surface.** 15 tool schemas re-sent (cached, but they bloat the cache-write +
   uncached churn); it made 0 tool calls this run. A leaner schema set shrinks the prefix.
5. **Extractor: ~30% of helper cost, runs EVERY turn** (incl. cold-start passthrough turns). Confirm
   extraction-batching actually batches (it fired every turn here); batch to user-turn boundaries.
6. **Run curator in background/parallel** to hide the latency (it currently blocks the upstream call).

## Revised conclusion
The curator is NOT fundamentally a loser -- on Run-2 it was mostly a TUNING ARTIFACT: an eligibility
gate set to 100 tokens made it run where it had nothing to do, adding latency + a little upstream
bloat for $0.05. **Fix the gate (lever 1) and it has no downside on normal sessions.** The genuinely
worthwhile, scoped investigation: with the gate raised, a cheaper curator model, and a net-reducer
injection rule, does the curator net POSITIVE on the regime it's actually for -- long sessions
(40+ turns / >20k raw history) that pressure the context window, in front of an expensive upstream?
That is now a clean experiment with the downside engineered out first.
