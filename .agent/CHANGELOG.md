# archolith-bench Changelog

## 2026-06-19 — LongMemEval Mode B: persistent-memory (ingest-then-recall) driver

**feat(harness):** Added a third adapter shape for memory benchmarks. `harness/memory_ab.py` `run_memory_ab` drives ingest -> recall -> answer per item: for memory arms it isolates a `group_id`, ingests the haystack sessions, recalls against the question, and answers from recalled memory (not the raw history); the `no_memory` arm is the floor. Reports the memory-QA accuracy lift. `assert_not_production` refuses prod-looking targets before any write.

**feat(harness):** `LongMemEvalMemoryAdapter` (`longmemeval-menhir`) implements the memory-QA contract, reusing the shared LongMemEval loader + scorer. `harness/menhir_client.py` provides `StubMenhirClient` (deterministic in-memory, offline) and `HttpMenhirClient` (configurable, for a throwaway menhir). CLI dispatches in-process / external-cli / memory; `--menhir-url` for real runs.

**note:** Mode A (`longmemeval`, in-context) tests the proxy; Mode B (`longmemeval-menhir`) tests menhir's persistent graph memory and is what the registry maps to menhir. Real Mode-B run (throwaway menhir+Neo4j) deferred; offline-runnable now with the stub.

## 2026-06-19 — Memory benchmark: LongMemEval for menhir (MTEB reclassified)

**feat(harness):** Added `LongMemEvalAdapter` (in-process) — the official LongMemEval long-term memory QA benchmark, run as a direct(no memory)-vs-proxy A/B. This is menhir's CAPABILITY benchmark: menhir is built on Graphiti (the temporal-KG engine Zep reports on LongMemEval/DMR), so it's the apples-to-apples industry standard for a memory system. Deterministic normalized-containment scorer offline; official GPT-4 judge can be added behind a flag.

**docs(registry):** Re-mapped menhir's memory benchmark from MTEB to **LongMemEval** (primary) + **DMR** (candidate). MTEB reclassified as an embedding-COMPONENT diagnostic (embedder-selection data), not the memory capability claim. Rationale: MTEB measures the embedding sub-component, not the memory system end-to-end.

**evidence:** Earlier MTEB embedding head-to-head retained as a component diagnostic — local nomic 0.681 vs OpenAI text-embedding-3-small 0.730 on SciFact (`benchmarks/mteb-embedding-baseline-2026-06-19.md`).

## 2026-06-19 — External Benchmark Harness (real-harness A/B)

**feat(harness):** New `archolith_bench/harness/` package houses official external benchmarks under one roof behind `ExternalBenchmarkAdapter`. `run_ab()` runs an adapter across arms (direct vs proxy family), reusing `core.api.send_chat`, `apply_arm_config`, and the cost model, and reports the proxy-vs-direct delta (official score preserved + tokens/cost reduced) — the only honest, advertisable Archolith claim, since Archolith is middleware, not a model.

**feat(harness):** Two adapter shapes under one roof — in-process (`ExternalBenchmarkAdapter`, driven by `run_ab`) and external-CLI wrappers (`HarnessBenchmarkAdapter` + `ExternalCliAdapter`, driven by `run_external_ab`, which invoke the official tool per arm and parse its results file).

**feat(harness):** All candidate benchmarks wired:
- `longbench-v2` (in-process) — official THUDM/LongBench-v2 multiple-choice accuracy.
- `bigcodebench-hard` (in-process) — official bigcode/bigcodebench-hard pass@1; generated code executed in a sandboxed subprocess with a timeout.
- `swe-bench`, `cyberseceval-4`, `agentdojo`, `mteb-retrieval` (external-CLI wrappers) — scaffolded: documented official command + env injection (direct/proxy base URL) + results parser, tested offline against sample results fixtures. Real runs deferred to step 3 (need the tools, datasets, agent scaffolds, API budget).

**feat(cli):** `archolith-bench harness <id>` with `--list` (shows in-process vs external-cli), `--arms`, `--subset`, `--limit`, `--offline-fixture`, markdown/JSON evidence.

**docs:** Registry updated — every candidate points at its real adapter; RULER relabeled a `-style` smoke test. MTEB caveat recorded: chat proxy is not in the embeddings path, so its proxy-arm delta is a no-op until an embeddings layer exists.

**tests:** Offline harness coverage for all six adapters (load/score/exec/parse/A-B/deltas/evidence + CLI smoke), no network or API spend.

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
