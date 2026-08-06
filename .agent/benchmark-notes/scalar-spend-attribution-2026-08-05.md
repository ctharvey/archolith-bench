# Scalar spend attribution — 2026-08-05

## Outcome and limits

The offline historical instrument provides descriptive scalar-spend and recall evidence for
`scalar-duration-completeness-candidate-v2-20260730`. It is not canonical acceptance evidence:
the run is noncanonical, and full canonical acceptance was not evaluated. It does not establish
scalar causality, scalar token or dollar spend, or token/dollar equivalence between pipeline stages.

Correction: the `58/78` recall result in this note is the source-attribution/accounting checkpoint,
not the best scalar result. The best observed scalar development result is `70/78` in
[scalar-lme-run-lineage-2026-08-05.md](scalar-lme-run-lineage-2026-08-05.md); keep `58/78` here
for accounting only. Neither score is canonical acceptance evidence.

## Observed historical accounting

| Measure | Observed value |
| --- | ---: |
| Manifest namespaces | 78 |
| Manifest scalar calls | 234 |
| Typed assertions | 185 |
| Scalar states written | 172 |
| Scalar state Views | 132 |
| History Views | 133 |
| User-founded Views | 132 |
| Paid namespaces with zero assertions | 8 |
| Paid namespaces with zero state/history Views | 9 |
| Completed Graphiti ingest chat calls | 11,669 |

The 11,669 Graphiti calls belong to a different stage. They are not token- or dollar-comparable
to the 234 manifest scalar calls, and must not be treated as a spend conversion or denominator
for scalar cost.

## Recall checkpoint

Recall answer costs below use only persisted recall input/output tokens and explicitly supplied
GPT-4o rates of 2.5 input and 10 output USD per million tokens. Scalar and judge usage were not
persisted; judge usage and cost are `null`/`not_measured`.

| Arm | Correct | Input tokens | Output tokens | Answer cost USD |
| --- | ---: | ---: | ---: | ---: |
| `menhir_recall` | 58/78 | 35,357 | 1,118 | 0.0995725 |
| `no_memory` | 5/78 | 5,552 | 312 | 0.01700 |

Presentation-only signatures in the recalled payload were:

| Arm | State signature | History signature | Correct + state | Correct + history |
| --- | ---: | ---: | ---: | ---: |
| `menhir_recall` | 67 | 17 | 50 | 12 |
| `no_memory` | 0 | 0 | 0 | 0 |

These conservative signatures show only that formatted scalar-state or scalar-history evidence
was present in the recalled payload. They do not show that the answer model used that evidence.
Scalar-attributable corrected answers and cost per scalar-corrected answer are therefore
`null`/`not_measured`: there is no scalar-disabled-memory counterfactual. Only the observed
presentation/intersection counts above are available.

## Negative control

For `lme-6071bd76`, the historical checkpoint records 3 scalar calls, zero assertions, scalar
states, Views, history Views, or user-founded Views; both historical checkpoint arms were
incorrect and neither had a scalar signature. Later rerun claims are deliberately not imported
into this artifact.

## Provenance status

The run is resumed across 4 attempts, mixes Menhir and Bench commit identities, contains 3
interrupted phases, and had a dirty Bench tree on attempt 4. These are observed canonicality
concerns. Their absence in a synthetic or future run would mean only that no such concerns were
observed; full canonical acceptance is not evaluated by this note or instrument.

## Input hashes

| Input artifact | SHA-256 |
| --- | --- |
| `manifest.json` | `f1fe89ed2113d5c1fc53841c1010e2c6a3f286369a6f6aebaf08346fda34cac3` |
| `run_provenance.json` | `1d9d182f530b5d9e7ea4f5119b663fd75394afb1436d1a7f00e175e599962a1b` |
| `mcp_telemetry.db` | `c4d69ad3c5c9a1f2153e3c5a2efef66e4dfd87cad2d3703f94fe2972063c0b2e` |
| Recall checkpoint | `540ccee597ad1f51084468bec8e1e73a0e86c070f9b0966b6c5c0400b667545b` |

## Reproduction

```text
python scripts/measure_scalar_spend_attribution.py \
  results/lme-ku-buildout/scalar-duration-completeness-candidate-v2-20260730 \
  --json-out .tmp/scalar-spend-attribution/report.json \
  --markdown-out .tmp/scalar-spend-attribution/report.md \
  --input-usd-per-million 2.5 \
  --output-usd-per-million 10 \
  --negative-control lme-6071bd76
```

## Next evidence

The next approved evidence should be (a) a fresh frozen scalar capture for held-out
deterministic-vs-frozen-LLM agreement and router gates, and (b) scalar-disabled recall
counterfactual/instrumentation. Neither was run for this closeout. No valid real frozen scalar
capture currently exists, so deterministic-vs-frozen-LLM agreement remains unrun.
