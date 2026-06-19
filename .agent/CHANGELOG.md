# archolith-bench Changelog

## 2026-06-19 — Industry Benchmark Coverage Matrix

**feat(industry):** Added executable industry benchmark registry mapping Archolith products to trusted benchmark families: RULER, LongBench v2, SWE-bench, BigCodeBench, HELM, MTEB, CyberSecEval, AgentDojo, and OWASP LLM/application security checks.

**feat(cli):** Added `archolith-bench industry` with product/suite filters, markdown/JSON output, launch-only filtering, and tracked artifact support via `--out`.

**feat(report):** `BENCHMARKS.md` generation now includes industry benchmark coverage when `results/industry_benchmarks.json` exists.

**docs:** Updated README, agent docs, architecture, data models, benchmark evidence README, and launch readiness tracker to treat industry benchmark coverage as a launch gate rather than completed evidence.

**tests:** Added industry registry and CLI smoke coverage.

## 2026-06-10 — Cache-Aware Effective-Cost Model

**feat(metrics):** `PricingModel` dataclass with per-provider rates (DeepSeek, OpenAI, Anthropic), `compute_turn_cost()` with cache-hit/miss pricing, `compute_arm_cost()` aggregation, and helper-LLM spend support.

**feat(proxy-suite):** Per-turn `effective_cost_usd` attached to every result; `total_effective_cost_usd`, `cache_data_available`, and cost breakdown fields in run summary.

**feat(stack-suite):** Pricing model threaded through to four-way comparisons.

**feat(cli):** `--provider` and `--pricing-file` flags on `proxy` and `stack` subcommands.

**feat(display):** Cost column in per-turn table, effective cost line in print_summary, cost columns in cross-scenario and four-way comparison tables.

**feat(report):** BENCHMARKS.md proxy section gains effective cost, cache availability, and cost-verdict rows (PROXY CHEAPER / PROXY MORE EXPENSIVE / INCONCLUSIVE).

**tests:** 13 new tests covering cache-split pricing, no-cache fallback, helper spend, zero-token turns, arm aggregation, pricing file overrides, and Anthropic write asymmetry.
