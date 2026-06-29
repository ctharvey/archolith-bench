# IntentOracle benchmark — demo run notes

**Date:** 2026-06-29 · **Rung:** menhir IntentOracle (Phase 4 of `menhir-intent-oracle-plan.md`)
**Package:** `archolith_bench/intent/` · **Fixture:** `fixtures/intent_floor_corpus.json`
**Run:** `python scripts/run_intent_bench.py` -> `results/intent_run.json` (gitignored)
**Design:** menhir `docs/research/intent-warden.md`

## What this tests

Whether a deterministic (no-LLM) task-intent signal changes *which* artifact surfaces
first — for the right reason — over a corpus where the topic is held constant and only the
query's task intent varies. Four arms:

- **baseline** — semantic-only (no task intent). Top-1 cannot track intent.
- **intent_on** — default oracles + `IntentOracle` through the log-space combiner.
- **shuffle** — intent_on with a deliberately WRONG intent, averaged over *every* wrong
  intent (the expected accuracy of a random wrong label). Isolates the intent signal from
  topic leakage.
- **no_harm** — orientation queries ("how does X work"); full stack WITHOUT intent vs full
  stack WITH intent. Adding the oracle must not drop nDCG. (Held the stack constant so this
  measures *intent*, not the whole oracle stack.)

## Headline (lexical stand-in — harness sanity, NOT a promotion decision)

```
intent-correct@1   baseline=0.143  intent_on=1.000  shuffle=0.691
no-harm nDCG@5      no_intent=0.387 intent_on=0.431
determinism        1.0
promotion gate:    GRADUATES
  intent beats baseline: True (lift +0.857)
  shuffle collapses:     True (lift vs shuffle +0.309, margin 0.15)
  no-harm holds:         True
```

All 7 intent queries land on a top-1 artifact carrying a PREFERRED role for the classified
intent. The metric is **role-based** (top-1 carries a preferred role for the true intent),
not exact-id — which is the design's principle made measurable: *intent lifts the relevance
band; the other oracles order within it.*

## Honest reading / caveats

- **The shuffle collapse is the real proof**, not the 1.000. baseline->intent_on rising is
  expected once any signal is added; the load-bearing result is that a *wrong* intent loses
  most of the lift (0.691 vs 1.000, a 0.309 drop). If the gain were topic leakage, shuffle
  would stay near intent_on. Residual shuffle accuracy (~0.69) is expected because some
  roles (TEST/EVIDENCE/BENCHMARK) are broadly task-useful, so a wrong intent still sometimes
  lands a preferred role — hence the gate uses a *margin*, not zero.
- **no-harm is isolated correctly:** comparing semantic-only to full-stack+intent would
  conflate intent with the rest of the oracle stack (the first draft did this and the arm
  failed spuriously). Holding the stack constant, intent does **not** harm orientation
  queries (0.431 >= 0.387 — it nudges up).
- **Lexical semantic stand-in + a 7-memory single-topic fixture.** This is a harness
  sanity check, not a promotion decision. Swap a real embedder and grow the fixture
  (multi-topic, more roles, contested per-intent golds) before quoting absolute numbers.
- **Lens routing finding:** VERIFY_CURRENTNESS must route to the *neutral* lens (`any`), not
  `historical` — routing it to historical made the TemporalOracle BOOST the superseded
  artifact, so "is X still accurate" surfaced the stale experiment. The `any` lens surfaces
  current + superseded together without lifting the stale one (the design's CONFLICT intent,
  expressed in the bench combiner's 3-value lens).

## What graduates to menhir (the Phase 1 spec)

The four producer modules are the contract menhir's pure-domain layer reproduces:
`classifier.py` -> `domain/query_intent.py`; `roles.py` -> `domain/artifact_role.py`;
`matrix.py` -> `domain/intent_affinity.py`; `oracle.py` -> the `IntentOracle` added to
`services/retrieval_oracles.py`. **Not** added to `default_oracles()` in production until a
real-embedder + grown-fixture run re-confirms the gate.

## Fixture validator (`intent/validate.py`) — added

Auto-runs before every ladder run (like `oracle/validate.py`); flags it, does not design the
benchmark. **Errors** (untrustworthy): empty corpus/queries, dup memory/query id, dangling
`expected_top`/support, date-order, bad belief bucket. **Intent-specific silliness warnings:**
- `SINGLE-ROLE-CORPUS` — < 3 distinct content roles, so intent has nothing to re-rank between.
- `NO-PREFERRED-ROLE` — a query's intent prefers no role any memory carries (unrewardable).
- `EXPECTED-TOP-MISMATCH` — the hand-authored gold carries no preferred role for its intent.
- `UNCLASSIFIED-QUERY` — a main query matches no intent cue (LOW confidence).
- `NO-SUPERSEDED` — history-wanting intents present but no superseded memory to exercise the lens.
- `TOPIC-NOT-CONSTANT` — no token shared by half the corpus (a ranking change could be topic
  leakage, the thing this bench design exists to rule out).

The shipped `intent_floor_corpus.json` validates clean. 31 tests (incl. validator tests).

## Real-embedder run (2026-06-29) — the conclusion changed, as the gating discipline predicted

Swapped the lexical stand-in for a real embedder — **`text-embedding-nomic-embed-text-v1.5`
(768-dim) on LM Studio :1234**, via `intent/embedder.py` (`--embedder` flag; nomic
`search_query:`/`search_document:` prefixes, cached, cosine clamped to [0,1]). Ran two
fixtures x two scorers:

| fixture | scorer | baseline | intent_on | shuffle | gate |
|---|---|---|---|---|---|
| floor (1 topic, role-words in prose) | lexical | 0.143 | 1.000 | 0.691 | **GRADUATES** |
| floor (1 topic, role-words in prose) | **embedder** | 0.571 | 1.000 | **0.905** | **does NOT** (shuffle won't collapse) |
| two-topic CONTROLLED (role=metadata) | lexical | 0.571 | 0.714 | 0.429 | **GRADUATES** |
| two-topic CONTROLLED (role=metadata) | **embedder** | 0.571 | 0.714 | 0.429 | **GRADUATES** |

**The load-bearing finding.** On the single-topic floor fixture the artifact text *names its
own role* ("...decision config", "...failure regression"). A real embedder embeds "why did we
choose" near "decision" on its own, so it recovers role-matching without intent — and a
*wrong* intent (shuffle) rides that same floor, so the shuffle does not collapse and the gate
fails. The lexical stand-in could not do this, which is exactly why the lexical run was only
ever a harness sanity check, not a promotion decision.

**The fix is a fixture-design law, not a code change:** carry the content role in **metadata
(`artifact_type`), not in prose.** The controlled two-topic fixture does this — within a topic
all artifact TEXT is identical (the topic phrase), so neither lexical nor embedder can separate
roles by text; the task intent is the ONLY within-topic role signal. Result: it graduates
**identically under both backends** (intent_on 0.714 vs shuffle 0.429, +0.286 margin) — i.e.
the IntentOracle's contribution is **embedder-invariant**, the strongest form of the claim.

Caveats that remain: baseline 0.571 is partly an id-tiebreak artifact (alphabetically-first
`benchmark_*` is a broadly-preferred role), so read the **shuffle collapse** (0.429 << 0.714),
not the baseline delta, as the proof. intent_on 0.714 (not 1.0) because the other oracles
co-decide within a tied-text topic. Determinism 1.0 (embedder cached). The single-topic floor
fixture is kept only as the lexical-era demo; **the controlled two-topic fixture is canonical.**

## Grown corpus + de-biased baseline + three backends (2026-06-29)

Three follow-ups landed together:
1. **De-biased baseline.** The semantic-only baseline tiebroke ties by alphabetical id, which
   systematically picked `benchmark_*` (a broadly-preferred role) and inflated baseline to
   0.571. Now `IntentBenchmarkRunner._tiebreak` hashes the id (role-neutral, deterministic), so
   the baseline sits at the true chance rate (~0.39).
2. **Grown corpus.** `intent_multi_topic_corpus.json` — **4 menhir topics** (source-aware floor;
   hybrid RRF rank-fusion; belief currentness buckets; structural dependency-cone temporal join)
   x 7 roles = 28 memories / 28 queries / 4 no-harm. Controlled design (within-topic text
   identical, role in metadata).
3. **OpenAI embedder.** `OpenAIEmbeddingScorer` (`text-embedding-3-small`, 1536-dim; key from
   `OPENAI_API_KEY`, never hard-coded; 429 surfaced, never silently retried). `--scorer
   {lexical,lmstudio,openai}`.

**Result — identical across all three backends (lexical / nomic-embed / OpenAI 3-small):**

```
intent-correct@1   baseline=0.393  intent_on=0.714  shuffle=0.429   (all three scorers)
gate: GRADUATES    lift vs baseline +0.321 | shuffle collapses +0.286 | no-harm holds | determinism 1.0
```

Because within-topic text is identical, the semantic backend cannot drive within-topic ranking,
so the three scorers produce **byte-identical** intent metrics — the IntentOracle's contribution
is **embedder-invariant**, now demonstrated across a lexical stub, a local model, and a
production OpenAI model. Baseline (0.393) ~= shuffle (0.429) ~= chance; intent_on (0.714) is the
only arm above chance, and the shuffle collapse proves that lift is the intent signal.

**The validator earned its keep:** it flagged `EXPECTED-TOP-MISMATCH` on the blast-topic plan
query — the topic name "structural **blast radius**…" collided with the `CHANGE_ANALYSIS` cue
"blast radius", misclassifying all 7 blast queries. Renamed the topic to "structural dependency
cone…" (no cue collision); intent_on then rose 0.679 -> 0.714. The `TOPIC-NOT-CONSTANT` guard was
also reworked to flag all-distinct-text corpora (the leaky shape), which correctly warns on the
old single-topic floor fixture and passes the controlled multi-topic one.

## Baseline honesty — what we compare against (and what we DON'T)

The gate now compares intent against the **oracle-stack default** (full default_oracles WITHOUT
intent), not the semantic-only strawman. On the 4-topic controlled fixture (OpenAI 3-small):
`semantic_only=0.393 -> oracle_default=0.429 -> intent_on=0.714` (shuffle 0.429). So intent adds
+0.286 over the oracle stack itself — the honest marginal-value-of-intent number.

**Critical caveat — none of these arms is menhir's pre-oracle, pre-frontier SHIPPED recall.**
The shipped recall path is the two-phase `recall_service` + `scoring_service` over Graphiti
hybrid (vector + BM25) search — a different code path that needs a live Neo4j+Graphiti graph and
is NOT run by this pure-stdlib bench. So we have demonstrated that intent improves the **frontier
oracle pipeline** in a controlled harness; we have **NOT** shown intent (or the oracle stack)
beats what menhir actually ships today. That comparison requires wiring the shipped recall as a
bench baseline arm over the same fixtures on a live graph — the long-standing live-graph owed
work (`deferred-verification.md`), still outstanding.

## Open

- Matrix **magnitudes** (PREFER=1.0/NEUTRAL=0.25/PENALIZE=0.05/IGNORE=0.0) are the bench's
  first calibration — the design left them open. Signs (P/N/X/-) are the human contract.
- Gated menhir production integration remains (add IntentOracle to `default_oracles()` + wire
  `task_intents_to_lens` at the recall entry point) — now the embedder gate is met on a real
  OpenAI model, this is unblocked pending an explicit go (it changes production recall).
