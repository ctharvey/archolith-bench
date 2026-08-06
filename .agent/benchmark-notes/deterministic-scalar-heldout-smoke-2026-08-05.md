# Deterministic scalar held-out smoke — 2026-08-05

Status: **completed; deterministic bypass not ready**

This is the first bounded, pre-registered, non-LME smoke for Menhir's deterministic typed-scalar
shadow. It is evidence about capture fidelity and comparison behavior only. It is not a population
gate, promotion decision, LongMemEval result, or estimate of production precision.

## Frozen identity

| Item | Value |
|---|---|
| Menhir commit | `ffba4a5c6afd57954acf39f7b93f75a25e0bf175` (clean) |
| Bench commit | `ea35ca308b72cbf4727d49dfbc232083cabc2bcc` |
| Fixture | `fixtures/deterministic_scalar_heldout_v1.json` |
| Fixture SHA-256 | `c6be6f4a20d3646a2271721636727be314455cfaa81950f4e10de7d602dd04cf` |
| Capture SHA-256 | `d78bb2ae92cf13d204cc48d15ce9fb21845effe783d852deb4764d0fd7f880ad` |
| JSON report SHA-256 | `15f65fba293a26c1eb97afcbf836c310f6ad42a24d984d64c37ff8e355cd07b7` |
| Markdown report SHA-256 | `e935002976b728b3c1a199b09ccd946c1994c62c09dc4629f88235e8011db40c` |
| Generated at | `2026-08-06T01:10:47Z` |

The ignored local artifacts are under
`results/deterministic-scalar-shadow/heldout-v1-20260805/`. Their hashes above make accidental
replacement detectable; the capture itself includes the exact dated episode strings and sampling
settings.

## Sampling and gate settings

- Model: `gpt-4o-mini`
- Namespaces: 2
- Samples per namespace: `k=3`
- Calls: exactly 6
- Temperature: 0.7
- Maximum completion tokens: 2048
- Truncated completions: 0
- Gate: 2/3, common-span alignment enabled
- Attribute/scope/subject reconciliation: disabled
- Canonical-self reconciliation: disabled

No graph, Docker, Neo4j, LME fixture, or LME task text was used.

## Result

| Measure | Result |
|---|---:|
| Episodes fully eligible | 3 / 7 |
| Fallback-required episodes | 4 / 7 |
| Deterministic proposals | 3 |
| LLM-gated committed claims | 7 |
| Exact agreement | 0 / 7 |
| Aligned agreement | 1 / 7 |
| Router-missed LLM claims | 2 |
| Theoretical calls after namespace routing | 3 / 6 |

The fallback/adversarial namespace behaved as intended: all four episodes stayed on the LLM path,
so it saved no calls. The fully-covered namespace would save one three-call batch, but only one of
its three claims aligned with the LLM baseline. That fails the plan's zero-router-miss requirement.

## Disagreement classification

| Claim | Deterministic | LLM 2/3 result | Classification |
|---|---|---|---|
| `I have 37 coins` | `attribute=coins`, count 37 | `attribute=count`, count 37 | Attribute/slot identity contract or comparator-normalization gap; numeric extraction agrees |
| `My savings balance is $500` | `attribute=savings_balance`, `unit=usd`, money 500 | `attribute=account_balance`, blank unit, money 500 | LLM attribute variance plus missing global normalization/reconciliation; value extraction agrees |
| `I wake up at 7:30` | `wake_time`, `07:30` | `wake_time`, `07:30` | Aligned agreement; exact mismatch is punctuation/span boundary only |

The money samples themselves were unstable: two emitted `account_balance`, one emitted
`savings_balance`. The smoke therefore exposes a real free-text attribute identity problem; it does
not justify teaching the extractor aliases for these particular sentences.

## Verdict and next gate

Reject deterministic bypass readiness. Keep the existing k=3 LLM gate authoritative.

Before another metered run:

1. Make a global design decision about canonical scalar attribute identity versus gated attribute
   reconciliation. Do not add fixture-specific aliases.
2. Pre-register a larger generic held-out and perturbation/adversarial panel with canonical slot
   labels, known-negative labels, and a minimum sample size/CI contract.
3. Require zero router-missed baseline claims and zero labeled false-positive/false-current
   admissions before considering class-level promotion.
4. Measure token/dollar and latency attribution separately; this capture records calls but not
   token or dollar cost.
5. Run frozen LME recall only after the generic promotion gates pass.
