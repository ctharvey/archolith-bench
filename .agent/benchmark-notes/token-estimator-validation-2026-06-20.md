# Token Estimator Validation — 2026-06-20

## Scope

CORR-07 validation for `archolith-bench` token estimation. This does not change `archolith-context`
production token accounting.

The v3 remediation plan referenced `archolith_bench/metrics/costs.py`; that file does not exist in the
current repository. The estimator used by the proxy suite is `archolith_bench/core/metrics.py`.

## Fixtures

Representative shapes added in `tests/test_token_estimator.py`:

| Fixture | Old `len(text) // 4` | `cl100k_base` | Error |
|---------|----------------------|---------------|-------|
| Plain English benchmark prose | 56 | 36 | +55.6% |
| JSON/tool schema | 206 | 196 | +5.1% |
| Python code snippet | 70 | 79 | -11.4% |
| Mixed OpenAI message array | 300 | 293 | +2.4% |

The heuristic error is shape-dependent rather than a single consistent multiplier bias: prose overcounts
substantially, JSON is close, and code undercounts.

## Decision

`archolith-bench` now uses `tiktoken` `cl100k_base` when available and keeps the existing char-divide fallback
when the optional dependency is absent. Tests skip exact tokenizer comparison if `tiktoken` is missing while
still keeping the fixture shapes exercised.

No `archolith-context` production estimator change is recommended from this benchmark note. The proxy already
has its own structural estimator from earlier work, and this validation only proves that `archolith-bench`
should avoid the crude fallback when an exact tokenizer is present.
