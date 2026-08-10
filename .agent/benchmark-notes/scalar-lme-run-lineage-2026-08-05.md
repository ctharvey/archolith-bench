# Scalar LME run lineage — 2026-08-05

## 2026-08-09 canonical update

`scalar-event-activity-ku78-v6-20260809` is now the best canonical KU78 result at
**71/78 (0.910256; displayed 0.910)**. It was a fresh, non-resumed 78-item build with clean pinned
Menhir `1fa57955b24f90d08550c911f26133e5b14cbb89` and Bench
`d5e97cc4fc322564c624a749e2cb25dccdf9c2ea`, a passing two-item checkpoint, 78/78 manifest rows,
zero cumulative failed episodes, zero final PENDING/ENRICHING/FAILED episodes, and harness exit 0.
The scored Menhir arm used 117,933 input and 1,376 output tokens for `$0.308592`; provider-reported
combined run usage was 17,516,332 tokens.

The immediate clean predecessor, `scalar-event-activity-ku78-v4-20260809`, scored
**69/78 (0.884615; displayed 0.885)** at Menhir `9d9675c` / Bench `b7a2754`. V6 gained five passes
and lost three relative to v4, for a net +2. It is also +3 correct versus the previous canonical
`scalar-canonical-ku78-v1-20260806` at 68/78 (0.872). The seven v6 failures were
`f9e8c073`, `c4ea545c`, `e61a7584`, `a2f3aa27`, `26bdc477`, `031748ae_abs`, and `07741c45`.
Only `26bdc477` exposed a clear deterministic Menhir defect: possessive `my camera` did not bind
to the co-mentioned `Canon EOS 80D camera`. The other misses do not justify broad benchmark-driven
production changes.

This updates the canonical comparison point; it does not turn the result into an approved launch
headline or establish a scalar-only causal effect. The exact campaign record, per-item outcomes,
settings, infrastructure, and artifact hashes are in
[`results/lme-ku-buildout/LEDGER.md`](../../results/lme-ku-buildout/LEDGER.md).

## Correction and decision

The `58/78` score in [scalar-spend-attribution-2026-08-05.md](scalar-spend-attribution-2026-08-05.md)
is **not** the best scalar run. It is the older source-attribution checkpoint bundled with source
ingestion `scalar-duration-completeness-candidate-v2-20260730`, selected because it has a full
manifest, telemetry, a `no_memory` arm, and the accounting inputs needed by the offline attribution
instrument.

The best historical noncanonical scalar development result in the July ladder is
`scalar-write-repair-targeted-v1-20260730` at
**70/78 (0.897436)**, with 115,490 input tokens, 1,448 output tokens, and estimated answer cost
`$0.303206`. Use 70/78 only for that development ladder and 58/78 only as the accounting source.
Neither July result is canonical acceptance evidence; the current canonical comparison is the
71/78 v6 run above.

| Run | Result / economics | Decision use | Scope warning |
| --- | --- | --- | --- |
| `scalar-duration-completeness-candidate-v2-20260730` | Source attribution checkpoint: `58/78`; `no_memory` `5/78`; 35,357 input / 1,118 output / `$0.0995725` | Accounting source only | Older resumed source-ingestion checkpoint |
| `scalar-authority-recall-v1-20260730` | `63/78` | Run-ladder evidence | Richer scalar-authority serialization on a reused graph |
| `scalar-temporal-evidence-recall-v2-20260730` | `65/78` | Immediate reference for targeted run | Added source-time and current-vs-superseded evidence on a reused graph |
| `scalar-write-repair-targeted-v1-20260730` | **`70/78 (0.897436)`**; 115,490 input / 1,448 output / `$0.303206` | Best observed scalar development result | Intentionally noncanonical isolated-clone development run |

## Run ladder

1. Source attribution checkpoint: `58/78` from the historical scalar-duration-completeness
   source-ingestion run.
2. `scalar-authority-recall-v1-20260730`: `63/78`, using richer scalar-authority serialization
   on the reused graph.
3. `scalar-temporal-evidence-recall-v2-20260730`: `65/78`, adding source-time and
   current-vs-superseded evidence on the reused graph.
4. `scalar-write-repair-targeted-v1-20260730`: `70/78`, on an isolated clone with 74 namespaces
   inherited and exactly four rebuilt: `lme-6a27ffc2`, `lme-59524333`, `lme-e66b632c`, and
   `lme-f685340e`.

The targeted run had four direct write-repair wins (`6a27ffc2`, `59524333`, `e66b632c`,
`f685340e`) plus one judge-variance pass (`d7c942c3`). It had no pass-to-fail regressions versus
`65/78`.

## Non-apples-to-apples boundary

This is a development ladder, not a controlled scalar-only A/B series. The recall prompt and
serialization changed; recall input context grew from 35,357 source-checkpoint tokens to 115,490;
and four graph namespaces changed. The targeted run is intentionally noncanonical: it used a cloned
graph, dirty Menhir and Bench worktrees with recorded diffs (`menhir-working.diff` and
`bench-working.diff`), only the `menhir_recall` arm, and neither a `no_memory` nor a scalar-disabled
counterfactual. Do not present 70/78 as canonical acceptance or infer scalar causality from the
ladder.

## Remaining eight in the targeted run

The targeted run's [REVIEW.md](../../results/lme-ku-buildout/scalar-write-repair-targeted-v1-20260730/REVIEW.md)
found no clean judge false negative among the eight failures. `lme-26bdc477` is borderline: it
contains the correct total but adds a contradictory breakdown.

| Category | Task | Finding |
| --- | --- | --- |
| Categorical extraction / purchase grounding | `lme-41698283` | Lens use is recalled, but most-recent purchase is not established. |
| Temporal validity fallback | `lme-e61a7584` | The correct nine-month fact is retrieved but marked superseded without a replacement duration. |
| Scalar extraction / consensus | `lme-a2f3aa27` | Authoritative scalar state remains 1250; the later 1300 update is missing. |
| Categorical recency authority | `lme-3ba21379` | Newer Ford F-150 evidence is present, but the answer selects the older Mustang project. |
| Answer generation / contradictory summary | `lme-26bdc477` | Says five, then gives an impossible 3+3+3 trip breakdown. |
| Predecessor / temporal relation | `lme-0977f2af` | Instant Pot and Air Fryer content is present, but “invested in before” is not represented strongly enough. |
| Query scope / negative-control veto | `lme-031748ae_abs` | Accepts unsupported Software Engineer Manager over the stored Senior Software Engineer role. |
| Location-state transition | `lme-07741c45` | Retrieves the later shoe-rack plan but selects the older under-bed location. |

## Exact artifacts and SHA-256

| Artifact | Exact location | SHA-256 |
| --- | --- | --- |
| Source attribution checkpoint | `results/lme-ku-buildout/scalar-duration-completeness-candidate-v2-20260730/harness_recall/.checkpoint_longmemeval-menhir_oracle_gpt-4o.jsonl` | `540ccee597ad1f51084468bec8e1e73a0e86c070f9b0966b6c5c0400b667545b` |
| Authority checkpoint | `results/lme-ku-buildout/scalar-authority-recall-v1-20260730/harness_recall/.checkpoint_longmemeval-menhir_oracle_gpt-4o.jsonl` | `756c9080b097977fe04cb4d792931af11c6bf394c3d2156d3f41fffb0f6a07c8` |
| Temporal checkpoint | `results/lme-ku-buildout/scalar-temporal-evidence-recall-v2-20260730/harness_recall/.checkpoint_longmemeval-menhir_oracle_gpt-4o.jsonl` | `e8896860a17527b732e2a1fb2b4a52699330941b601a14db019f94d535b25d08` |
| Best manifest | `results/lme-ku-buildout/scalar-write-repair-targeted-v1-20260730/manifest.json` | `388dd1983ae15f90d728e756c112a975d84e823b083a241a84d2f8bc8308194d` |
| Best provenance | `results/lme-ku-buildout/scalar-write-repair-targeted-v1-20260730/run_provenance.json` | `0de50fd36995dcb64c57e8220dd708b175b200932d6bd4bc72155c9fd86fa7b5` |
| Best checkpoint | `results/lme-ku-buildout/scalar-write-repair-targeted-v1-20260730/harness_recall/.checkpoint_longmemeval-menhir_oracle_gpt-4o.jsonl` | `987a7c130c6820a6e73a713be34971b5fe03f7f87b5f2c35f3b657f2ddbe4296` |
| Best review | `results/lme-ku-buildout/scalar-write-repair-targeted-v1-20260730/REVIEW.md` | `839587e53c4f4761b093f70f773136268935850e6bc8a9ac5d6b6b11c5899775` |

For the accounting bundle and its limitations, see
[scalar-spend-attribution-2026-08-05.md](scalar-spend-attribution-2026-08-05.md). The campaign
checkpoint is [lme-score-campaign.md](lme-score-campaign.md#measurement-checkpoint-scalar-spend-attribution-2026-08-05).
