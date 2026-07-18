# Typed Value Recall Arm

`menhir_value_recall` is a bench-only experiment for testing first-class `Value`
nodes before changing Menhir's graph schema.

The arm builds a deterministic sidecar graph from user haystack turns only. A
single `Value` abstraction carries an explicit kind: boolean, status, count,
duration, frequency, money, measurement, clock time, or weekday. Values are
immutable and assertion-scoped. Relevant value assertions are combined with
ordinary Menhir recall while preserving the same total recall limit.

Extraction is question-blind and gold-blind. It does not write to Neo4j or alter
Menhir. Equal values in unrelated facts remain separate nodes and skip entity
resolution. Boolean nodes require explicit polarity; absence or failure to
mention something remains unknown rather than becoming `false`.

## Fixture preflight

The original scalar-only prototype put an answer-supporting assertion in the
typed top-4 for 27 of the 29 adaptive-run cases with genuinely absent answer
support. The generalized arm adds explicit status and boolean values for the two
state misses: finishing a book and owning a spare screwdriver. With question-blind
extraction, a fixture rerun now puts answer support in the typed top-4 for all 29
cases.

Candidate-support coverage is not answer accuracy. A three-arm answer/judge run
is still required before proposing a production schema change.

## Run the answer comparison

Run the three-way comparison only against a completed, verified throwaway graph:

```powershell
$env:LONGMEMEVAL_VARIANT = "oracle"
archolith-bench harness longmemeval-menhir `
  --menhir-url http://localhost:8134 `
  --recall-only `
  --subset knowledge-update `
  --limit 78 `
  --arms no_memory,menhir_recall,menhir_value_recall `
  --recall-limit 10 `
  --scorer llm-judge `
  --judge-model gpt-4o-mini `
  --model gpt-4o
```

The experimental question is whether `menhir_value_recall` improves accuracy on
the 29 extraction-loss cases without reducing accuracy elsewhere. Treat this as
a representation simulation, not a production Menhir result: the sidecar uses
deterministic extraction and lexical retrieval rather than Menhir's eventual
value-node implementation.

## Answer-level results (2026-07-17)

Three-arm recall-only run against the completed adaptive graph
(`menhir-lme-ku-adaptive-full-20260717`, bolt 7698, recall server 8133), oracle
variant, gpt-4o answers + gpt-4o-mini judge, recall-limit 10, 78 knowledge-update
items. Independent verification run; artifacts in
`results/lme-ku-buildout/value-arm-verify-20260717/`.

| Arm | Overall (78) | 29 extraction-loss | Other 49 | Abstention (6) |
|-----|--------------|--------------------|----------|----------------|
| `no_memory` | 0.064 (5/78) | 0.000 (0/29) | 0.102 (5/49) | 5/6 |
| `menhir_recall` | 0.333 (26/78) | 0.000 (0/29) | 0.531 (26/49) | 4/6 |
| `menhir_value_recall` | **0.679 (53/78)** | **0.724 (21/29)** | **0.653 (32/49)** | 5/6 |

Per-item `menhir_recall` -> `menhir_value_recall`: 28 wrong->correct, 1 correct->wrong
(`50635ada`), 49 unchanged. No regression on the 49-set (26->32). `menhir_recall`
scored 0/29 on the loss set *with the same recall context*, so the gain is
attributable to the typed representation, not to more context (input tokens +5.7%
only; typed snippets displace ordinary snippets under the same top-10 cap, max 3
typed snippets/item). Reproduced across two runs (value arm 0.679 both times;
`menhir_recall` 0.346/0.333).

Abstention safety held: all 6 `_abs` items produced safe "I don't know" answers
under the value arm (zero confident-wrong); the near-miss typed values did not
flip abstentions to misses.

Residual value-arm failures are concentrated in stale/current ambiguity: when a
later value supersedes an earlier one for the same subject but the two source
sentences differ in wording, both survive as `current` (supersession keys on exact
subject text). 5 of the 8 remaining 29-set misses are this pattern (37 vs 38 coins,
4 vs 5 MCU films, 8:30 vs 7:30 wake time, three vs five sessions, and a
three-way-current gym clock time). Tightening supersession/recency labeling is the
top follow-on bench iteration before a production ingestion design commits schema.

## v2 supersession arm result (NEGATIVE, 2026-07-18)

A pre-registered supersession-aware iteration (`menhir_value_recall_v2_current`,
`menhir_value_recall_v2_history`; `SupersededValueGraph`, clustering by
entity/attribute/scope/kind with per-assertion correction markers then latest-learned)
was implemented (v1 untouched) and run as a 5-arm comparison on the same graph.
Artifacts: `results/lme-ku-buildout/value-arm-v2-verify-20260717/`.

| Arm | Overall | 29-loss | Other 49 | Abstention (6) |
|-----|---------|---------|----------|----------------|
| menhir_value_recall (v1) | 0.679 (53/78) | 21/29 | 32/49 | 5/6 |
| menhir_value_recall_v2_current | 0.667 (52/78) | 20/29 | 32/49 | 5/6 |
| menhir_value_recall_v2_history | 0.679 (53/78) | 21/29 | 32/49 | 5/6 |

**The hypothesis did not validate. Acceptance was not met (required >=3/5 supersession
targets recovered; got 0/5).**

- v2 clustering changed the typed context on only 6/78 items, and changed the outcome on
  none of them. On all 5 supersession targets the v2 typed context was byte-identical to
  v1 (clusters never merged).
- The one apparent regression (`5831f84d`, v2_current) is answer-model variance, not v2:
  the recalled context is byte-identical to v1; gpt-4o answered 12 vs 15 stochastically.
  Zero real v2-caused regressions. v2_history == v1 exactly (0 wins, 0 losses).

Root causes (from paired snippet evidence):
1. **Scope fragmentation.** Deterministic full-sentence scope derivation is too brittle for
   real multi-clause turns: incidental tokens (jog/coffee/yoga; bereavement/remember)
   fragment the cluster so the same attribute across turns does not merge. Unit tests on
   short clean sentences passed, but fixture sentences do not cluster.
2. **Structural ceiling.** The sidecar governs only ~3 of 10 slots; the untyped Menhir
   recall backfill reintroduces the stale value regardless of sidecar supersession.
3. **Target misclassification.** Not all "supersession" misses are supersession:
   `69fee5aa` needs arithmetic inference (37 stated + "added a new coin" -> 38; 38 is never
   stated literally), which no CURRENT-selection rule can fix.

Implication: canonical entity/attribute resolution needs the graph's real entity nodes
(Menhir's View/episode layer), not lexical sentence tokens, and a typed-value system must
control the whole recalled context (or rank authoritatively) rather than add a sidecar
alongside untyped recall. Do NOT commit a production supersession/schema design on this arm;
the supersession lever is unconfirmed at the answer level.

### Residual v1 miss reclassification (by mechanism)

Grounded in each item's question + typed context (checkpoint evidence):

| ID | Question | Gold | Mechanism |
|----|----------|------|-----------|
| `b6019101` | MCU films last 3mo | 5 | direct supersession (4 vs 5) |
| `f9e8c073` | sessions attended | five | direct supersession (three vs five) |
| `dad224aa` | wake time Saturdays | 7:30 | direct supersession (ambiguous: 7:30 preference vs 8:30 actual) |
| `69fee5aa` | coins owned | 38 | delta / arithmetic (37 + "added a new coin") |
| `c4ea545c` | gym more frequent than before? | Yes | comparative reasoning |
| `6071bd76` | coffee ratio more/less water | less (5 oz) | relation-direction (6->5 oz = less) |
| `6aeb4375` | Korean restaurants tried | four | elided referent ("four different ones") |
| `59524333` | usual gym time | 6:00 pm | answer-model/context competition (7:00/2:00 co-present) |

**True direct-supersession headroom is ~2-3 of 8.** The remaining 5-6 are delta/arithmetic,
comparative, relation-direction, elided-referent, or context-competition failures that no
CURRENT-selection rule can address. Conclusion: stop iterating on lexical supersession; a
production typed View must be authoritative during recall composition (suppress/demote
overlapping untyped snippets for an attribute family when the View has a confident current
value) and should carry two claim forms - **absolute** (`collection_size = 37`) and **delta**
(`collection_size += 1`) - so it can derive 38 while preserving both supporting episodes.
The narrowed production question: can Menhir derive entity-linked scalar state from episodes
and make that state authoritative during recall?

## v3 authoritative-composition result (MIXED - mechanism works, net-negative as-is; 2026-07-18)

Bench simulation of an authoritative typed View: coarse (near-oracle, within-item) grouping
to fix v2's clustering fragmentation, then `_v3_coarse` (current-only typed) and
`_v3_authoritative` (current-only + suppress untyped snippets carrying a superseded value).
Artifacts: `results/lme-ku-buildout/value-arm-v3-verify-20260718/`.

| Arm | Overall | 29-loss | Other 49 | Abstention (6) | 5 targets |
|-----|---------|---------|----------|----------------|-----------|
| menhir_recall | 0.359 | 0/29 | 28/49 | 5/6 | 0/5 |
| menhir_value_recall (v1, additive) | **0.705** | 22/29 | 33/49 | 5/6 | 1/5 |
| v3_coarse (grouping only) | 0.641 | 22/29 | 28/49 | 4/6 | 3/5 |
| v3_authoritative (grouping + suppression) | 0.679 | 23/29 | 30/49 | 5/6 | 4/5 |

(Same-run paired baseline; v1 ran 0.705 here vs 0.679 prior = answer/judge variance.)

**The mechanism is validated but nets negative as an unconditional rule:**
- v3 recovers the targeted misses: v3_coarse 3/5, v3_authoritative **4/5** supersession/competition
  targets (`b6019101`, `dad224aa`, `f9e8c073`, `59524333`) that additive v1 missed.
- The suppression lever is net-positive: v3_authoritative (0.679) > v3_coarse (0.641) - suppressing
  stale untyped snippets helped (also won `852ce960`, a money item).
- But coarse GROUPING over-merges distinct series, and authoritative single-pick then selects the
  WRONG current value and suppresses the right one. v3_authoritative: +4 wins, **-6 real regressions**
  (all v1-correct this run): `71315a70` (5-6h picked over gold 10-12h), `dfde3500` (Thursday/Maria
  over gold Wednesday/Juan), `e66b632c` (26:30 over gold 27:45), `89941a93`/`89941a94` (bike
  count/compose), `945e3d21`.

**Key lesson: authoritativeness is double-edged.** Additive v1 is robust because it shows multiple
candidates and lets the answer model choose; authoritative composition removes that safety net, so a
wrong current-pick is *worse* than additive (`71315a70` is the poster child: v1 showed 5-6h AND 10-12h
-> model answered 10-12; v3 showed only 5-6h -> model answered 5-6). `69fee5aa` (arithmetic) and the
bike-count items remain unreachable - selection can't derive unstated values.

**Refined design principle (next iteration): confidence-gated authoritativeness.** Collapse to a single
current value + suppress competitors ONLY when the View is confident (clean cluster, unambiguous recency
or explicit correction marker); otherwise fall back to additive candidate display. That keeps the 4 wins
while avoiding the 6 wrong-pick regressions. This is the same confidence-tiering the derivation
(assumptions/delta) layer needs. Arithmetic/filtered-count/coreference remain out of scope for any
selection mechanism and require reducer/aggregation/coref primitives.