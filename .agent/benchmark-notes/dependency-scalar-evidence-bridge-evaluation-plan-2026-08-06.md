# Dependency Scalar Evidence Bridge Evaluation Plan

**Status:** DESIGN/RESEARCH
**Date:** 2026-08-06

**Runner status (2026-08-06):** `scripts/measure_dependency_scalar_bridge.py` implements the
offline 48-case measurement contract against an explicit `MENHIR_ROOT` and paired guarded
JSON/Markdown outputs (`--json-out` / `--markdown-out`). The authoritative r2 evidence is
`results/dependency-scalar-bridge/phase-a-v1-20260806-r2/report.{json,md}` for fixture SHA
`bde118508cf55c94bbd10fc88fbc625a0f465859a545f3ca79deb391a25ba57b` (JSON SHA256
`53aff17ecd1d758f2d808050e9ac8e2512f269a3254ae2fee99f25d2696fc412`; Markdown SHA256
`3284c6d81d47e22907c7fcd6fe79993ca65fa386a7206366d9d079ac78999287`). Across 48 cases: supported
identity/provenance exact 5/6, unsupported composed 0/14, false-current 0/28, evidence provenance
45/45, Menhir bridge provenance 45/45, cue exact 179/192, and edges 135 TP / 180 predicted / 144
gold (P .75/R .9375/F1 .8333). Proposal parity is 45/48 because three history candidates fail
closed at canonical adapter `temporal_past_only`; composer replay is stable 45/45; baseline
composition is 2/48 (43 abstentions, 3 adapter drops). R1 was the historical first execution with
incomplete git provenance; r2 changed instrumentation only and aggregates/cases are identical.
The one supported miss is bare `retain`; it is not added post-hoc because that would tune to holdout
and open non-possession senses, so broader support requires a separately authored independent policy
panel. Span recognition, role/operation classification, performance, cache, and full
adapter/parser/emission replay remain `not_measured`; promotion is `not_evaluable`. The runner has
no bridge-to-baseline fallback or runtime/LLM/network/Neo4j/cache claims.

## Purpose and non-goals

This plan measures a source-bound dependency-evidence bridge at the seam between
text evidence and Menhir's canonical scalar parser. It is deliberately generic:
the fixture uses invented entities, relation nouns, values, and templates rather
than team-size language or benchmark records.

The bridge is evaluated as evidence plumbing, not as a replacement grammar. The
semantic comparison has intentionally different composers:

1. **Canonical baseline:** the existing canonical/isolated research adapter
   plus its existing regex composer.
2. **Phase-A evidence bridge:** Bench-only dependency evidence, then the same
   `parse_scalar_row`/value validators/domain-identity invariants, followed by
   Menhir's new absolute-only dependency-rule composer.

The current `compose_structural_scalar_identity` path is absolute-only and
therefore legitimately abstains on `delta` and `expire`. Bench owns evidence
recognition and measurement only; it must not implement semantic composition.
Phase B extends Menhir's dependency-rule composer with separately reviewed
`delta`/`expire` rules. Transport/provenance parity is a separate check; the two
semantic arms are not required to use the same composer.

The independent 48-case authoring and scored panel has no LME, LLM, network, or
Neo4j dependency. The separately labelled frozen replay may use its existing
LME context, but it is never pooled with the independent panel. The bridge must
not use a fallback to the baseline arm during measurement.

## Lean independent panel

The proposed fixture is `dependency_evidence_bridge_ops_v1.json`, with **48
cases**: 24 train and 24 holdout. Each split uses disjoint invented entities,
literal target nouns, numeric values, and template banks; relation labels come
only from Menhir's frozen `RELATION_TYPES`. No benchmark text,
benchmark IDs, or frozen-78 records may be copied.

Three source topologies are balanced in each split:

- direct local dependency;
- coordinated or prepositional attachment with a numeric distractor;
- multi-clause distractor with the canonical-self target clause explicitly
  marked (any third-party clause is negative attribution/distractor evidence).

Topology is orthogonal to semantics: a positive remains a canonical-self claim
in every topology. A multi-clause or coordinated distractor must never turn a
positive into attribution, subset, or a different target. All positive subjects
are the canonical source subject; invented third-party entities occur only in
negative attribution/distractor clauses. The holdout repeats this structure
with disjoint names and relation/target vocabulary.

The semantic-role matrix is intentionally small but operation-complete. Each
split contains:

| Semantic role | Cases/split | Operation and admission contract |
| --- | ---: | --- |
| `current_total` | 3 | `absolute`; admit |
| `delta` (holding-changing add/remove) | 3 | signed `delta`; admit. Removal is a partial change, e.g. `I sold 2 bikes`. |
| `event` — one-off/non-holding | 3 | no Menhir operation; abstain with `non_holding_event` |
| `event` — standing scalar expiry/removal | 3 | `expire`; admit only when the old standing value ends entirely, e.g. `my 9 permits expired` |
| `history` | 3 | `absolute` but past-only; reject with `past_only` |
| `subset` | 3 | two non-authoritative `absolute` totals reject; one explicitly grounded add/remove `delta` admits |
| `modality` | 3 | no operation; abstain with `modal` |
| `attribution` | 3 | no operation; abstain with `attributed_source` |

Thus the Phase-B operation-aware target has 10 expected admissions per split
(20 total): six absolute current totals, six holding deltas, six standing
expiries, and two grounded subset deltas. There are 14 true negatives per split
(28 total). Phase A is absolute-only with three strata across the full fixture:
6 in-scope canonical-self absolute positives, 14 semantically valid but
capability-unsupported delta/expiry cases, and 28 true negatives. The 14
unsupported cases must never be relabeled as negatives; they remain
`unsupported_abstain` until Menhir adds separately reviewed dependency rules.

`event` is one semantic role for coarse scoring. The one-off and standing-
expiry variants are also reported as fine role variants because they have
different admissibility contracts. Menhir operation values are only
`absolute`, `delta`, or `expire`; abstention is represented by
`admit=false` plus a role/reason, never by an invented operation name.

The expiry cells are explicit standing-state termination, not future plans and
not partial removals: `I no longer have 9 permits`, `my 9 permits expired`, or
`I used to have 9 permits` are expiry examples. `I sold 2 bikes` is a signed
partial `delta`; `the 9 permits will expire Friday` is future/modality and
abstains; an arbitrary removal count remains a delta, not `expire`.

## Gold record and provenance contract

Every case has one primary scalar evidence span, even when the final answer must
be rejected. The gold record contains:

```text
case_id, split, text
episode_id, source_key
claim_span: {start_char, end_char, text, sha256}
quantity_span: {start_char, end_char, text, sha256}
gold_dependency_path: {node_char_offsets, edges: [{head_char, dependent_char, dependency_label}]}
role_gold: current_total|delta|event|history|subset|modality|attribution
role_variant: one_off_event|standing_expiry|null
operation_gold: absolute|delta|expire|null
abstention_reason: non_holding_event|past_only|subset_non_authoritative|modal|attributed_source|null
relation_type, target_literal, role_scope
value: {magnitude, sign}
temporal_state, totality, grounding
admit_gold: true|false
```

Character anchors and span hashes are authoritative; token IDs are derived from
the pinned tokenizer only for diagnostics. A candidate is valid only when its
`episode_id`, `source_key`, character offsets, and span hash point back to the
source record. Any emitted candidate without exact provenance is a provenance
failure, even if its value is otherwise correct. Rejected cases may emit
source-located diagnostic evidence, but may not emit a source-free canonical
claim.

`relation_type` is one of Menhir's frozen `RELATION_TYPES`; it is not an
arbitrary fixture-defined relation key. The literal target and any explicit
scope are scored separately and must be preserved exactly. Positive records use
the canonical source subject and a relation type that Menhir already recognizes;
third-party names are reserved for negative attribution or distractor cases.

## Arm reporting and capability boundary

The two semantic arms are intentionally narrow but use their appropriate
composers:

1. **Canonical baseline:** existing canonical/isolated research adapter,
   followed by the existing regex composer.
2. **Phase-A evidence bridge:** Bench-only dependency evidence followed by the
   same `parse_scalar_row`/value validators/domain identity invariants and
   Menhir's new absolute-only dependency-rule composer.

Do not prescribe baseline admission counts: measure whatever the current
canonical/isolated adapter actually emits on each topology. Generic topology
differences may legitimately make the regex baseline abstain or choose a
different span. Bench reports those observations rather than labelling them
expected failures.

Phase A is the shippable seam gate: absolute-only, with six canonical-self
`current_total` positives, 14 capability-unsupported delta/expiry cases, and 28
true negatives. Phase B is a future target: after Menhir extends that
dependency-rule composer with separately reviewed `delta`/`expire` rules,
replay the same fixture against the 20/28 operation-aware contract. Bench
remains an evidence emitter and scorer; it does not contain or select those
semantic rules. A separate transport/provenance parity check may compare the
arms' source bindings, but it must not imply semantic-composer parity.

## Measurements and exact denominators

All missing predictions count as errors. Extra candidates are spurious; more
than one admitted candidate per case is an admission/composition error.
The 14 Phase-A delta/expiry cases are the exception for admission scoring:
missing output is recorded as `unsupported_abstain`, not as a false negative.

| Stage | Measurement | Denominator |
| --- | --- | ---: |
| Span recognition | exact claim/evidence span; character/token P/R/F1 | 48 gold spans |
| Dependency attachment | exact subject→predicate→value→target path per case; edge micro P/R/F1 | 48 gold paths; edge denominator is manifest `gold_edge_count` |
| Semantic role | coarse 7-way exact/macro-F1; fine 8-way variant report | 48 labels (6 per fine label; event coarse has 12) |
| Operation | exact `absolute`/`delta`/`expire`/null, with sign for deltas | 48 labels |
| Relation | exact Menhir `RELATION_TYPES` value | 48 payloads |
| Target/scope | exact literal target and explicit scope | 48 payloads |
| Value | exact magnitude and delta sign | 48 payloads |
| Canonical admission (Phase A) | precision/recall/specificity on supported absolute lane; unsupported reported separately | TP=6, unsupported=14, TN=28 |
| Canonical admission (Phase B target lane) | precision, recall, specificity after Menhir rules land | TP=20, TN=28 |
| Identity composition (Menhir-owned operation-aware target lane) | exact `{relation_type,target_literal,scope,value/sign,operation,temporal}` | 20 gold admissions |
| Provenance | exact episode/source/offset/hash integrity | every emitted candidate |

The operation-aware target admission rule is role-aware: admit only the 20 cases
specified above, but enforce it only after Menhir's reviewed dependency rules
exist. A history total is not current merely because its number is parseable; an
event is not a holding delta; and a subset total is not authoritative unless the
text explicitly grounds an add/remove delta against the current holding.
Phase A measures each composer as-is: the regex baseline and Menhir's
absolute-only dependency composer. Delta/expiry cells are reported as
capability observations, not prescribed baseline outcomes.

### Negative safety gates

- **Phase A false-current:** zero of the 28 true-negative cases may be admitted
  or composed as a current canonical scalar. Report `FP/28` by role, topology,
  and split; report the separate 14-case unsupported stratum.
- **Phase A identity:** all six canonical-self positives must match relation
  type, literal target, explicit scope, value, absolute operation, and current
  temporal state exactly.
- **Phase B false-current:** after Menhir's operation-aware rules are reviewed,
  zero of 28 non-admissible cases may be admitted or composed as a current
  canonical scalar. Report `FP/28` by role, topology, and split.
- **Phase B wrong operation:** zero admitted cases may change `absolute` to
  `delta`, `delta` to `absolute`, or `expire` to either. Report operation
  confusion separately from role errors.
- **Phase B identity:** all 20 expected admissions must match relation type,
  literal target, explicit scope, signed value, operation, and temporal state
  exactly.
- **Provenance:** 100% of emitted candidates must retain source identity and
  exact offsets/hashes.

## Version, repeatability, and cache checks

Every report records fixture SHA, source-authoring revision, tokenizer version,
Menhir parser/validator/composer version, baseline or bridge version, and the
dependency-model version. Run both arms cold and warm twice. For each arm and
version, the serialized per-case outputs must be byte-identical: drift is
`0/48` cases.

An intentional parser-version comparison runs both arms under `vN` and `vN-1`.
It reports field-level changes in span, edge, role, operation, admission, and
identity. No “latest parser” substitution or silent fixture/denominator change
is permitted.

Performance is descriptive until correctness gates pass:

- per-case and total wall time, p50 and p95 latency;
- bridge overhead ratio versus the canonical baseline;
- cold versus warm elapsed time;
- cache hits, misses, invalidations, and hit rate;
- cache-key audit: source hash plus tokenizer/parser/bridge versions.

## Frozen-78 replay

The existing frozen-78 replay remains a separate, unchanged report section. It
must preserve its original case IDs, text, source hashes, and parser context.
The manifest supplies the denominators for spans, edges, role labels,
operations, relation/target/value fields, admissions, and non-admissions; do
not assume every stage has denominator 78. Show baseline and bridge rows
side-by-side and never pool the 48-case independent panel with frozen-78 or
reweight either result.

## Authoring and anti-tuning rules

The train and holdout pools are authored before either arm is run. Holdout
entities, literal target nouns, values, topology templates, and distractor
patterns are disjoint from train. Every positive is canonical-self; third-party
entities are permitted only in negative attribution/distractor clauses. The
fixture is immutable after its SHA is recorded;
any correction creates a new fixture version. No case may be selected,
rewritten, or removed because of an observed baseline or bridge error. Frozen-
78 text and IDs are not available during source authoring. Reports include the
fixture SHA, command line, git revision, and environment versions.

## Stop/go interpretation

Phase A supports an **absolute-only evidence-bridge prototype** when all of the
following hold:

- 6/6 canonical-self identity compositions and 100% provenance;
- false-current `0/28` true negatives, with the 14 unsupported delta/expiry
  cases reported separately and not relabeled as negatives;
- role macro-F1 at least 0.90 and absolute-operation accuracy at least 0.95;
- measured (not prescribed) baseline comparison shows no current-total
  regression and a meaningful span/attachment or safety gain;
- bridge p95 no more than 2x the measured baseline, warm-cache hit rate at least
  0.90, and zero deterministic/version drift.

Phase B is a **Menhir-owned research target**, only after separately reviewed
`delta`/`expire` dependency rules and composer support exist. Then require
20/20 identity, false-current `0/28`, zero wrong-operation admissions, and the
same provenance, role, performance, and drift gates. Bench must report the
baseline's observed behavior; it must not claim a baseline admission count.

This does **not** justify production adoption. The panel is intentionally small
and synthetic, and frozen-78 is a replay rather than new coverage. Production
claims require broader out-of-domain and multilingual text, adversarial and
fuzz coverage, load/concurrency and cache-invalidation tests, parser migration
evidence, operational fallbacks, and security/privacy review.
