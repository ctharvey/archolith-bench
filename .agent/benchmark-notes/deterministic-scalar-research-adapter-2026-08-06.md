# Deterministic scalar research adapter — 2026-08-06

Decision: keep the adapter and acceptance panel as research infrastructure, but do not promote the
deterministic path into ingestion, persistence, or scalar authority yet.

## Anchors

- Menhir baseline: `94d8c5e22850b858f22f9e5293d373b43137aed4` plus the uncommitted
  `research-adapter-v1` / `structural-v4` / `research-adapter-isolated-v2` research changes.
- Bench baseline: `4a777e5d7799d4023ecebb378a093cebab6d7d8b` plus the uncommitted acceptance
  panel and measurement changes.
- The replay used the already-frozen 78-task research input. It did not reingest, call an LLM, access
  Neo4j, write graph state, or enter Menhir runtime routing/persistence.

## Independent identity panel

The versioned non-LME panel contains 15 independently labeled cases across totals and subsets,
delta/event amounts, current/history/correction language, contractions, modality/questions, weak
targets, and ambiguous spans.

- Correct: **15/15**
- Parse status: **15/15**
- Composition status/reason: **15/15**
- Relation and target: **15/15**
- Promotion status: `not_evaluable`

The panel initially exposed two unsafe compositions: an `other` subset was treated as a total, and a
generic `things` target was treated as a stable identity. Menhir now fails closed on generic subset
modifiers and semantically empty quantity targets. The fix is generic and has positive coverage for
specific open-world targets such as `extra-large bikes`; it contains no benchmark task text or IDs.

## Frozen 78-task replay

The dependency-clause research candidates were passed through the pure Menhir adapter, canonical
typed-row parser, grounding checks, and structural composer.

- Input candidates: **36**
- Parser admitted: **33**
- Parser rejected: **3**
- Structurally composed: **0**
- Structural abstentions: **33**
- Tasks with a composition: **0**
- Answer-bearing tasks with a composition: **0**

Abstentions were dominated by `struct.unsafe_list` (22). The remaining reasons were
`struct.target_unresolved` (4), `struct.unsafe_hypothetical` (3), `struct.relation_unknown` (2),
`struct.unsafe_one_off` (1), and `struct.unsafe_past_only` (1). Parser-side rejections were two
`hedged_value` cases and one `temporal_past_only` case.

## Interpretation

The adapter solves the provenance and authority boundary: upstream research candidates cannot bypass
Menhir grounding or structural identity, and the experiment has no production side effects. The
non-LME repair also closes two real unsafe identity families.

It does **not** establish useful natural-language coverage. The frozen replay shows that the current
structural grammar rejects multi-clause conversational evidence even when an upstream recognizer can
find and ground a numeric span. The next research increment should improve clause isolation and
structural grammar coverage against a larger non-LME holdout panel. It should not add number patterns,
benchmark aliases, or graph promotion until identity correctness and coverage are both measurable.

Related research: `deterministic-scalar-nlp-binding-spike-2026-08-06.md`.

## Noisy-language extension

A subsequent research increment added a pure clause/evidence isolator and a separate 30-case non-LME
panel containing 15 clean/noisy pairs. The isolator retains exact original offsets and text while
recording a separately normalized view and quote-free rules/role receipts. It fails closed on
ambiguous corrections, competing numerics, and ambiguous conjunctions.

The unchanged panel initially scored clean 15/15 and noisy 14/15 with one false-current-state error:
the adjacent transposition `boosk` was composed as its own literal current target. A generic structural
veto now uses a one-token proposal attribute only as conflicting evidence for an exact adjacent
transposition; it abstains and never autocorrects or derives identity from that attribute. Final panel:

- Clean: **15/15 correct**, 15 composed.
- Noisy: **15/15 correct**, 2 composed and 13 expected abstentions/rejections.
- False-current-state errors: **0**.
- Expected paired invariance: **2/2**.

## Mapped-isolation comparison

The opt-in `research-adapter-isolated-v2` now connects the clause isolator to the offline adapter.
Normalized text is used only as a grammar probe. Any successful identity is rebuilt from the
canonical original proposal and a deterministically mapped literal source target, with distinct
`research_normalized_structural_grammar` provenance. Protected roles, unsupported rules, and
unprovable source mappings abstain.

On the unchanged 30-case panel:

- Canonical baseline: clean **15/15**, noisy **12/15**, noisy compositions **2**.
- Mapped isolated: clean **15/15**, noisy **15/15**, noisy compositions **5**.
- Composition gain: **+3** noisy, **0** clean.
- False-current-state errors: **0/0**.
- Identity differences: the three intended noisy recoveries for cats, records, and plants.

The frozen 78-task candidate replay was then rerun through both paths. The canonical baseline was
**0/36 composed** while the isolated path composed **1/36**, including **1** answer-bearing task.
The isolated outcomes were 5
canonical abstentions, 3 isolation rejections, 12 normalized abstentions, 3 parser rejections, and
13 protected-role abstentions. Propagated normalization rule IDs confirm that normalization was
actually attempted; it unlocked one bounded composition but not the broader conversational structures.

## Cumulative-completion holdout extension

The next source-authored non-LME increment is
`fixtures/scalar_identity_cumulative_v1.json`: 24 cases in 12 clean/noisy pairs, split into six
train and six holdout pairs with disjoint nouns, values, and templates. Positive cases exercise only
present-perfect completion (`have completed`, `have finished`, or `have closed`) with strict `so far`
or `to date` surfaces. Their typed operation is the existing `absolute` operation; no new operation
or benchmark alias is introduced. Adversarial pairs cover simple past, negation, modality/future,
history tails, coordination/second numerics, and subset/empty targets.

Measured with `scripts/measure_scalar_identity_isolated_comparison.py`, the panel scores baseline
clean **12/12** with 6 compositions and baseline noisy **6/12** with 0 compositions. The isolated
path scores clean/noisy **12/12** with 6 compositions each, a **+6** noisy composition gain, and
false-current-state errors **0/0**. The JSON/Markdown reports are source-free and remain
`promotion_status=not_evaluable`; this is regression evidence only and does not promote production
routing, persistence, or scalar authority.

This remains bounded regression evidence, not a coverage or production-promotion gate. The isolator
and mapped adapter are not wired into runtime or persistence. The result narrows the next work:
expand benchmark-agnostic structural grammar over generic conversational forms rather than adding
more spelling cleanup or benchmark-specific patterns.
