# LongMemEval score campaign — what we've tried

_Last updated 2026-07-02. Framework: `scripts/longmemeval/` (`lme.sh`). Plan of record:
`menhir-frontier/.agent/plans/anecdotal-recall-oracle-ladder.md`._

Our LongMemEval work has moved through **retrieval → diagnosis → brief construction**, and
the honest headline is that the biggest gains came from fixing measurement bugs, not from
cleverer ranking.

## Retrieval-side (ranking)

Built an oracle stack (temporal / evidence / scope / intent oracles + wardens), an intent-lens
classifier, and fact-edge retrieval (edge-as-pointer, lens-gated).

- **Ablation verdict: plain node retrieval is strongest (~0.37).** The oracle bells were
  neutral-to-negative; the EvidenceAnchorWarden *zeroed* anecdotal questions (refuses all
  LLM-extracted facts). Menhir recall already beats graphiti-native (28/90 vs 11/90).
- **Provenance classifier (answer-anchored, N=90):** retrieval is strong where the answer is an
  entity — **90% in top-k, 53% at rank-1**. The real gap: **~24% of answers aren't single
  entities** (multi-session counts, synthesized facts) → recall never surfaces them. That is a
  retrieval-coverage problem, not a ranking problem.
- **The TemporalOracle**: under a *historical* lens it correctly promoted a belief-superseded
  answer edge to **rank 1**, where the default current lens had buried it — an elegant mechanism
  ("superseded ≠ useless"). **But isolated A/B says it doesn't earn its place:** enabling only
  `semantic,temporal` (via `MENHIR_FRONTIER_ORACLE_SUBSET`) on temporal-reasoning + knowledge-update
  scored **0.367 vs node-only 0.400** (full stack 0.333). node > sem_temporal > full_stack — the
  same story as the ablation. The GPS #1 promotion was a correct mechanism on one question that
  does not generalize to measurable lift. **Node-only relevance ranking remains the champion.**

## Measurement bugs we fixed (the actual wins)

The "~30% vs Zep's 63.8%" gap was largely artifacts:

- **Sampling trap** — a bare `--limit N` sampled only `temporal-reasoning` (the hardest of 6
  categories, and the file is grouped by type). Fair runs stratify via `--subset`.
- **Scope** — benchmark memories stayed `SESSION`-scoped, so `build_context` and plain recall
  filtered them all out (empty briefs). Now written as regular `PERSISTENT` memories
  (`lme.sh promote`, run at end of every build).
- **Backdating** — menhir dropped `occurred_at` on ingest, stamping **every** episode/edge with
  the build date → fake temporal grounding. Repaired without a re-ingest via
  `lme.sh backfill-dates` (episode/edge `valid_at` ← real session dates). _Menhir ingest fix is
  a tracked follow-up._
- **tiktoken absent** → `build_context` ran in heuristic mode and **halved** the token budget
  (2000→1000), silently truncating briefs. Installed; full budget restored.

## Brief construction

MSC analysis: accuracy plateaus at **k≈5 (~400 tokens)** — the bottleneck is *what to pack*,
not retrieval depth. Built a **BriefBuilder** (flag `MENHIR_FRONTIER_BRIEF_BUILDER`, default off):

- v1 "Timeline-**first**" **hurt (−0.10)** — date-sorting displaced recall's relevance order and
  buried the answer (usually the top-relevance, often-undated memory).
- Redesign "Timeline-**appended below** the relevance list": **safe/neutral (+0.03, within
  N=30 noise)**. No category regressed. Ships default-off pending a larger-N lift verdict.
- Re-testable in one command: `lme.sh brief-ab [--score]` (the recall-only harness can't measure
  this — it feeds `/api/recall`, never `/api/context`).

## Net

Correctness fixes restored a fair baseline; brief formatting is a second-order effect, and even
the isolated TemporalOracle can't beat plain node retrieval (0.367 vs 0.400). Every read-time
lever landed neutral-to-negative — you cannot re-rank or re-format your way to information
candidate generation never assembled. Node-only relevance ranking remains the champion.

## Current direction: aggregation is a consolidation problem, not a retrieval problem

The hardest slice (multi-session counting — "how many bikes" → 4) is being tackled **upstream at
write/consolidation time**, not at read time: maintain quantitative state (stated running totals
as supersedable `(subject, measure) → value` facts; event-log folds for un-stated totals) so the
answer is a lookup, not a fuzzy count. Rationale, failure-mode census, and the first test:
**`menhir-frontier/.agent/plans/aggregation-as-consolidation.md`**. (Research docs incoming will
steer specifics.)

## Measurement checkpoint: scalar spend attribution (2026-08-05)

The historical offline instrument now accounts for the observed scalar calls, artifacts, recall
payload signatures, and explicit recall answer costs for
`scalar-duration-completeness-candidate-v2-20260730`: 78 namespaces, 234 manifest scalar calls,
185 typed assertions, 172 scalar states written, 132 scalar state Views, 133 history Views, 132
user-founded Views, 8 paid namespaces with zero assertions, and 9 with zero state/history Views.
It also counts 11,669 completed Graphiti ingest chat calls, which are from a different stage and
are not token- or dollar-comparable to scalar calls.

This run is descriptive evidence only. It is noncanonical, resumed across 4 attempts, mixes
Menhir and Bench commits, contains 3 interrupted phases, and had a dirty Bench tree on attempt 4.
Full canonical acceptance is not evaluated. See
[scalar-spend-attribution-2026-08-05.md](scalar-spend-attribution-2026-08-05.md) for the exact
recall totals, hashes, negative control, and limitations.

The `lme-6071bd76` historical negative control remains limited to 3 scalar calls, zero scalar
assertions/states/Views/history Views/user-founded Views, incorrect historical arms, and no
scalar signature. Later rerun claims are not imported. Scalar tokens/dollars are unpersisted,
there is no scalar-disabled-memory counterfactual, and scalar-corrected answers and cost per
scalar-corrected answer remain `null`/`not_measured`. No valid real frozen scalar capture exists,
so deterministic-vs-frozen-LLM agreement remains unrun.

Do not approve another full ingest from this checkpoint alone. The next evidence is a fresh
approved frozen capture for held-out agreement/router gates plus scalar-disabled recall
counterfactual/instrumentation; neither is run here.
