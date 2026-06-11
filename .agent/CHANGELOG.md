# archolith-bench Changelog

## 2026-06-10 — Cache-Aware Effective-Cost Model

**feat(metrics):** `PricingModel` dataclass with per-provider rates (DeepSeek, OpenAI, Anthropic), `compute_turn_cost()` with cache-hit/miss pricing, `compute_arm_cost()` aggregation, and helper-LLM spend support.

**feat(proxy-suite):** Per-turn `effective_cost_usd` attached to every result; `total_effective_cost_usd`, `cache_data_available`, and cost breakdown fields in run summary.

**feat(stack-suite):** Pricing model threaded through to four-way comparisons.

**feat(cli):** `--provider` and `--pricing-file` flags on `proxy` and `stack` subcommands.

**feat(display):** Cost column in per-turn table, effective cost line in print_summary, cost columns in cross-scenario and four-way comparison tables.

**feat(report):** BENCHMARKS.md proxy section gains effective cost, cache availability, and cost-verdict rows (PROXY CHEAPER / PROXY MORE EXPENSIVE / INCONCLUSIVE).

**tests:** 13 new tests covering cache-split pricing, no-cache fallback, helper spend, zero-token turns, arm aggregation, pricing file overrides, and Anthropic write asymmetry.
