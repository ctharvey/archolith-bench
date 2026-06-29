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

## Open

- Matrix **magnitudes** (PREFER=1.0/NEUTRAL=0.25/PENALIZE=0.05/IGNORE=0.0) are the bench's
  first calibration — the design left them open. Signs (P/N/X/-) are the human contract.
- Grow the fixture beyond one topic; add a fixture validator (mirror `oracle/validate.py`)
  if this rung continues.
