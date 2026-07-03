# D0 entropy delta on the counting slice — does query-sufficient state collapse retrieval entropy?

**Status: READY TO EXECUTE (planned 2026-07-02).** The concrete run of the locked build order in
`menhir-frontier/.agent/plans/aggregation-as-consolidation.md` (D0 instrument → D1 pass → entropy
delta). Everything upstream now exists; this plan is the measurement. **archolith-bench session**
(instrument + dataset + graph live here); writes state facts via menhir-frontier's `ViewRepository`.

## What already exists (so this is just the run)

- **D0 instrument** — `scripts/longmemeval/analysis/entropy.py` (+ `.sh`, `lme.sh entropy`).
  FLOOR (intrinsic evidence dispersion) vs DELIVERED (retriever walk to first gold hit), per-type
  vectors, deterministic sufficiency = "set touches an entity MENTIONED by a `has_answer` episode".
  No GPT.
- **Baseline FLOOR captured** — a prior floor-only run (rows json) over 90 Qs. The counting slice
  falls out deterministically: **14 numeric-answer Qs**, all `gold_resolved=True`, answer scattered
  across 4–8 episodes / 2–4 sessions. This is exactly the aggregation doc's ~14.
- **The D1 write primitive is built** — the counter View. `ViewRepository.record_counter(subject,
  counter, value, namespace, episode_uuids, name_embedding)` IS a supersedable `(subject, measure)→
  value` state fact, MENTIONS-linked to its source episodes. (This session's Event→Fold→View work.)

**Missing, and the whole point of this plan:** (a) the DELIVERED baseline (never measured), (b) the
consolidation *write* onto the counting-slice namespaces, (c) the before/after DELIVERED delta.

## The counting slice (14 qids, namespace `lme-<qid>`, baseline FLOOR eps/sess)

```
multi-session:      0a995998(3, 7/3)  6d550036(2, 8/4)  3a704032(3, 4/2)  gpt4_d84a3211($185, 8/4)
                    c4a1ceb8(3, 8/4)  46a3abf7(3, 6/3)  36b9f61e($2,500, 6/3)
knowledge-update:   852ce960($400k, 3/2)  89941a93(4, 4/2 ← bikes)  184da446(220, 5/2)  4d6b87c8(25, 4/2)
single-session:     7527f7e2($800, 2/1)  c960da58(20, 2/1)  18dcd5a5(4, 1/1)
```
Derive programmatically (don't hardcode) by filtering the instrument rows where `answer` is numeric
(`$`/`,` stripped → digits), so the slice regenerates if the sample changes.

## The methodological move: TWO arms — separate representation from perception

The honest risk (raised repeatedly): LME object-counting needs *perception* (detect the stated
total from prose), which is the fuzzy ~8% end. But D0 measures *organization*, deterministically.
So split the two variables and front-load the free, deterministic one:

- **Arm A — ORACLE consolidation (representation ceiling).** For each counting Q, write the counter
  View using the **dataset's gold answer** (perfect perception), MENTIONS-linked to that Q's
  `has_answer` episode(s). Answers: *if consolidation were perfect, does a query-sufficient state
  fact collapse retrieval entropy?* Zero GPT, deterministic, uses `record_counter` directly.
- **Arm B — REAL detector (perception + representation).** An LLM consolidation step that DETECTS
  the stated total from the episodes and writes the fact. The honest end-to-end, including the
  false-positive risk. Only worth building if Arm A shows a real collapse.

Arm A is the sharp first result. If it collapses DELIVERED to rank≈1 / 1 memory / ~40 tokens, the
representation thesis is **proven at the ceiling** and perception becomes the only remaining
variable — with a known dollar value (the A→baseline gap). If Arm A does NOT collapse, we've learned
the *representation itself* needs work (surface/ranking/sufficiency) before any perception effort —
a cheap, valuable negative that saves building Arm B.

## Steps

1. **Baseline DELIVERED (fills the gap).** Run the instrument `MODE=both` with `MENHIR_URL` set
   (benchmark server, scheduler OFF), `LME_ENTROPY_TYPES` restricted to the slice's types, over the
   counting slice. Record per-Q DELIVERED (rank to first gold hit, memories, tokens, %reached).
   Expect: high rank / many memories (the answer is scattered; that's the baseline entropy).
2. **Arm A oracle write.** For each counting qid: resolve the `has_answer` episode uuid(s) in
   `lme-<qid>` (same `_evidence_prefixes` + `_norm` match the instrument uses), then
   `record_counter(subject=<measure>, counter=<measure>, value=<gold>, namespace="lme-<qid>",
   episode_uuids=[has_answer uuids], name_embedding=embed(surface))`. The MENTIONS link is what makes
   the View a *gold entity* (sufficiency credits it); the embedding is what makes it *rank* for the
   query. Idempotent + supersedable, so re-runnable.
3. **Delta.** Re-run `MODE=both` on the slice; diff DELIVERED vs step 1 (and FLOOR vs the captured
   baseline). **Target: rank→1, memories→1, tokens→~40** on the stated-total Qs.
4. **Only if Arm A wins → Arm B.** Build the detector (LLM perception over episodes → `record_counter`),
   re-run the delta. Report false-positive rate.
5. **Precision guard (with Arm B).** Run the detector over a held-out NON-counting slice; a wrong
   state fact drops gold support out of the low-entropy set → sufficiency fails / entropy does NOT
   drop. Confirm no regression. (D0 catches this for free — the Goodhart guard.)

## Watch item — surface phrasing may motivate a third ViewKind

The counter View's surface is `"how many times {subject} {counter}: {value}"` — agent-event flavored,
not object-count flavored. For "how many bikes do I own", a `"{subject} {measure} = {value}"` surface
(e.g. `"bikes owned = 4"`, `"total spent on bikes = $185"`) likely ranks better. **The DELIVERED
number in step 3 will tell us deterministically whether it matters.** If the counter surface
under-ranks, that is the empirical justification to add a `CurrentValueKind(ViewKind)` (the "third
kind" already on deck) with a count/total-aligned surface — earned by data, not speculation. This
ties the D0 experiment back to the Event→Fold→View SSOT work: a new query class → a new fold + a new
value slot, measured into existence.

## What each outcome teaches (all deterministic, no GPT)

- **Arm A collapses (rank→1):** representation thesis proven; perception is the only remaining
  variable; its worth = the A→baseline gap. Green-light Arm B.
- **Arm A collapses only with a count-aligned surface:** build `CurrentValueKind`; the counter
  surface was the blocker, not the node.
- **Arm A does NOT collapse:** retrieval can't privilege even a perfectly-placed state fact — the
  problem is ranking/sufficiency, not consolidation. Redirect there before any perception work.

## RESULT — Arm A (oracle) run 2026-07-02: representation ceiling CONFIRMED (with a proxy caveat)

Ran step 1 (baseline DELIVERED, never before measured) + Arm A on all 14 counting qids via the
instrument's own functions. Wrote the gold state fact with `record_counter` (auto-derived
subject/counter, MENTIONS-linked to `has_answer` episodes, embedded), diffed DELIVERED, cleaned up.

```
                reached   median rank   median memories   median tokens
baseline         12/14        2.0             2.0              133
arm A (oracle)   14/14        1.0             1.0               21.5
```
- **12/14 collapse to a single-node lookup (rank 1, 1 memory).** 0 regressions.
- **Both previously-censored Qs (unreachable in top-20) recovered** (852ce960 →rank 2, c960da58 →1).
- **Token footprint 133 → 21.5 (~6×).** The state fact replaces a multi-episode reach with one node.
- Biggest collapses were the dispersed ones (rank 6/7 → 1: `3a704032`, `46a3abf7`; rank 5 → 1: bikes-$
  `gpt4_d84a3211`).

**Finding 1 — the counter surface is good enough; CurrentValueKind NOT yet justified.** Despite rough
auto-derived measures (`"how many times items of clothing need to pick: 3"`), the counter View ranked
**#1 in 12/14**. The watch-item's predicted under-ranking did not materialize, so a count-aligned
`CurrentValueKind` is not earned by this data. Defer it.

**Finding 2 — the honest caveat: the sufficiency proxy is lenient.** D0 sufficiency = "retrieval
touches ONE entity mentioned by a `has_answer` episode" = *distance to first gold-provenance touch*,
NOT assembling the correct count/dedup. So: (a) baseline was already median rank 2 (5 Qs were already
rank 1 — e.g. the bikes case `89941a93`), meaning this proxy does NOT capture the harder failures;
(b) reaching a superseded gold-adjacent entity ("three bikes") counts as sufficient even though it's
the wrong value. **D0-retrieval measures whether the answer's evidence is privileged in retrieval —
it does NOT measure current-vs-superseded correctness or perception accuracy.** Those are separate
axes (belief-gate; Arm B).

**Verdict:** representation ceiling is real on the retrieval-footprint axis — a single query-sufficient
state fact becomes the rank-1 / 1-node / ~21-token sufficient hit, recovering the unreachable ones.
Green-light **Arm B (perception detector)**, with expectations scoped by Finding 2: the remaining
value is in *perceiving* the right (current, not superseded) total, which this proxy can't score —
pair Arm B with an end-answer or current-value check, not D0-retrieval alone.

## Guardrails
- API-rate protocol: Arm A + all D0 runs are **GPT-free** (embeddings only for the View surface,
  optional). Only Arm B's detector calls an LLM — stop on 429, report.
- Benchmark graph hygiene: write only into `lme-<qid>` namespaces; the writes are supersedable and
  namespaced, so cleanup is `MATCH (x {group_id:'lme-<qid>', is_view:true}) DETACH DELETE x`.
- Never run a non-benchmark server against the shared graph (turns on the mutating scheduler).
```
