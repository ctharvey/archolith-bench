# archolith-bench Changelog

## 2026-07-08 — Repeatable Phase 3 live-characterization tooling

**feat(menhir-phase3):** Made the live consumer characterization reproducible on demand (it had been
ad-hoc). `scripts/probe_phase3_sum_rate.py` — a committed probe that measures the fold-SUM commit rate
(`--fixture sum`) and the `count_vs_spend_partial` receipt (`--fixture count-spend`) against a
throwaway menhir, over N fresh namespaces (no reset needed). Reuses the tested `Phase3MenhirClient`;
tallies abstention vetos so you can see WHICH gate is the SUM bottleneck; exits non-zero on any WRONG
or DUPLICATE current View (doubles as a safety guard). `benchmarks/RUNBOOK-phase3-live-characterization.md`
— the full throwaway bring-up/teardown loop (bench Neo4j via menhir's `docker-compose.benchmark.yml`,
serve on :8099, run suite + probe, teardown) with the safety rules (never `:8090`, delete the
key-bearing env file). Smoke-verified live: both fixtures run, `count_vs_spend_partial` fires, safety
invariants clean, real `:8090` untouched. No consumer or benchmark logic changed.

## 2026-07-08 — Phase 3 arrow-correction gate (consumer-quality-pack v1)

**feat(menhir-phase3):** Promoted a newly-hardened menhir correction phrasing to a permanent gate.
`phase3_scenarios.py` adds the `arrow-correction` gate scenario (`"Changed it to 20 from 25."` ->
supersede 25 -> 20 via menhir's new arrow/reverse connectives), mirroring the negative-correction
promotion precedent. `StubPhase3Client._correction` (offline model of the happy consumer) and the
scenario suite's `ScenarioFakeClient` learned the arrow (`25 -> 20`) and reverse (`to 20 from 25`)
phrasings so the offline smoke models them. `count-vs-spend` stays **characterization** (menhir's
count-vs-spend change was safety-only: a legible `count_vs_spend_partial` receipt, not co-extraction).
Evidence doc updated with the consumer-quality-pack v1 section and honest "pending live 2x" status for
the stochastic items (no throwaway menhir on :8099 this session; real `:8090` untouched).
`tests/test_phase3_scenarios.py`: scenario-set ids + offline scenario count updated to 6 (12/12 pass).

## 2026-07-07 — Menhir command group and launch evidence hygiene

**feat(menhir):** Added a first-class `archolith-bench menhir` command group with `list`, `smoke`, R1/R2/R3/oracle/intent/L4/R5 runners, LongMemEval aliasing, and extraction-model benchmarking under one product-facing surface.

**feat(evidence):** Added a capability registry and shared evidence publisher so suites can emit tracked artifacts with command, commit, source, provider/model, caveats, metric rows, and public-copy gating.

**docs(launch):** Normalized launch copy posture: active headline numbers are removed until refreshed launch evidence exists, historical numbers stay retired, and stack/audit/proxy evidence remains gated by tracked benchmark artifacts.

**test:** Added registry, evidence-publisher, and Menhir CLI smoke coverage. Verification: `python -m pytest -q` => 377 passed, 1 skipped; scoped `ruff` passed; package editable dry-run passed.

## 2026-07-05 — R2 facet: structural-facet extraction decomposed (symbols improved; files need the graph)

**feat(facet):** Added snake_case + SCREAMING_SNAKE identifier rules to the deterministic `FacetExtractor` (it previously caught only PascalCase + `foo(` calls, missing bare `source_aware_floor` / `weighted_rrf` / `FLOOR_EXEMPT_SOURCES`). Symbol-extraction recall on the draft fixture rose **0.11 -> 0.55**, lifting extracted-mode F recall@5 **0.275 -> 0.425**. 60 facet tests green (added `test_extract_snake_and_screaming_symbols`).

**bench(facet):** Diagnosed the Chunk F structural bottleneck (the owed "real derived structural facets" piece). It decomposes cleanly: **symbol facets are text-improvable** (above), but **`file` facets have recall 0.00 — the gold paths are not in the memory prose at all**, so a text extractor fundamentally cannot recover them; in production they come from the code graph's `ANCHORED_TO` edges. Extracted mode still does not graduate (recall_loss 0.425) precisely because file facets are absent, while hybrid mode (gold/graph structural) graduates. Conclusion: hybrid's gold-structural stand-in is the *correct* model for graph-anchored facts; the remaining owed question is **production `ANCHORED_TO` coverage** (graph-gated), not better extraction. Full analysis in `benchmark-notes/facet-r2-structural-facet-decomposition.md`.

## 2026-07-05 — Reusable bench progress harness

**feat(progress):** New `archolith_bench/progress.py` — a stdlib-only, reusable run-progress reporter for the long bench loops (a live R1 recall run over 6 conditions x 155 queries printed nothing for ~10 minutes and looked hung). `ProgressReporter` emits a throttled, flushed heartbeat to **stderr** (stays visible when stdout is piped / `tee`'d, keeps the JSON + table clean on stdout), TTY-aware (`\r` live line on a terminal, one line per tick when piped), with rate + ETA + an optional per-tick `detail` (e.g. the current condition). Convenience wrappers: `track(iterable, ...)` (tqdm-style, sync) and `run_ladder(conditions, items, run_one, ...)` (the common conditions x items loop). Works in async loops via `ProgressReporter.advance()`. Named `progress` to avoid colliding with the existing `archolith_bench.harness` external-adapter package.

**test:** `tests/test_progress.py` — 11 offline cases (format_duration, throttling, disabled-silent, single-final-line, zero-total safety, non-TTY line-per-tick, `track`, `run_ladder`) with StringIO streams.

**refactor(r1):** `scripts/run_r1_dummy.py` now drives a `ProgressReporter` across its async condition x query recall loop — the ~10-minute dummy run shows `[R1 recall] 45/155  29%  ...  eta ...` instead of silence.

**docs:** `.agent/workflows/bench-progress.md` — usage + adoption guide (the three primitives, async example, the "don't pipe through tail" note, API reference); pointer added under README "How to Run".

## 2026-07-05 — R2 facet ladder: real-embedder run (F graduates)

**feat(facet):** `scripts/run_facet_bench.py` gained `--embedder {stub,openai}`; the new `OpenAIEmbeddingScorer` (text-embedding-3-small + cosine, cached by text, ~70 embeddings, no graph) implements the `EmbeddingScorer` protocol and replaces the offline lexical stub in conditions B/C/E. The package stays offline/CI-pure — the real embedder lives in the script behind the flag.

**bench(facet):** Ran the R2 ladder on `fixtures/facet_r2_draft.json` (50/20) with the real embedder — closes the standing "swap in a real embedder before trusting B/C/E" caveat. Result: **F (facet + meet-point) GRADUATES in gold AND hybrid modes** even though the real embedder raised the baselines (C recall 0.80→0.875). The durable win is wrong-scope suppression (F 0.07 vs 0.38–0.40 for BM25/embedding/hybrid) plus lower stale-hit, at ≤0.05 recall loss. Extracted mode still collapses (recall 0.275 — the known Risk #2 extractor gap). This is the positive counterpoint to R1's same-day neutral-to-negative floor: R2's leverage is structural/scope facets at candidate generation, not a read-time re-rank. Full numbers + caveats (draft-fixture "too clean" risk, hybrid uses gold structural-facet stand-in) in `benchmark-notes/facet-r2-real-embedder-run.md`.

## 2026-07-05 — R1 live re-run: does not graduate (hybrid_alpha stays unset)

**bench(r1):** Ran the full R1 loop against the live dummy (prod clone, 23.8k entities, restarted after an OOM) with a fresh 155-query gold mine using the new paraphrase vehicle, scored through the recalibrated win gate. Result: **DOES NOT GRADUATE** — and this time it is real, not the old saturation artifact. The gate correctly exempted the saturated `exact_string_recall` and tested `symbol_recall`; `E_hybrid_a0` lost narrowly (0.700 vs 0.710) and regressed `wrong_scope` (0.034 -> 0.081). On the only headroom family (`paraphrased_debug_question`) the source-aware floor was neutral-to-negative (0.517 vs 0.533) — the opposite of the earlier 40-query run (+0.05), so the two bracket zero and the effect is within noise. With the vehicle fix, symbol/scope fell back to raw identifier (only 22 unique classes / 0 scope pairs have rich summaries) and now saturate (0.975 / 1.000). Conclusion: `hybrid_alpha` stays UNSET; R1's hybrid floor does not earn graduation on the dummy corpus, joining the oracle-stack LongMemEval verdict (read-time levers neutral-to-negative). Full numbers in `benchmark-notes/r1-dummy-gold-run.md`; this also validates the recalibrated gate live (it exempted the saturated metric instead of demanding the impossible `exact > 1.0`).

## 2026-07-05 — R1 gold miner: paraphrase vehicle for symbol/scope families

**fix(r1-miner):** `scripts/mine_r1_gold.py` no longer de-CamelCases identifiers for the `symbol_name_query` / `wrong_repo_same_topic` families (r1-dummy-gold-run.md showed `PricingModel` -> "Pricing Model" stripped the lexical signal AND left the single gold node unretrievable in the 23.8k-node graph). Both families now route their query text through the same LLM paraphrase vehicle as `paraphrased_debug_question` (identifier removed, so the source-aware floor / scope warden must do the work and the gold keeps real `symbol_recall` / scope headroom), with a raw-identifier fallback when there is no LLM client or the node body is too thin. Each query records a `vehicle` field (`paraphrase` | `identifier`). `exact_error_string` stays verbatim (a saturating floor guard, exempt under the recalibrated gate).

**refactor:** the `neo4j` import moved into `main()` (lazy) so the module and its pure helpers import without neo4j installed — required to test the miner offline / in CI.

**test:** Added `tests/test_mine_r1_gold.py` (first tests for the miner) — 7 offline cases over the query-vehicle routing (paraphrase vs identifier fallbacks, leak / thin-body guards, and `mine()` family routing) with a scripted fake session + fixed-reply fake client. Offline suite: 340 passed.

**note:** this is the CODE half of r1-dummy-gold-run.md step 3; the graph re-mine (+ paraphrase scale-up, step 2) and the real `hybrid_alpha` call remain corpus-gated.

## 2026-07-05 — Corpus sourcing survey (data phase)

**docs(benchmark-notes):** Added `benchmark-notes/corpus-sourcing-survey.md` — surveyed public corpora for the corpus-gated R1 `hybrid_alpha` tuning + R2 facet graduation data phase. Verdict: no off-the-shelf corpus qualifies as a drop-in (the phase is a union of code semantic-gap + temporal supersession + cross-repo scope + facet/belief labels, grounded in the agent's OWN repo graph — every public corpus covers only one axis and none is grounded in our repos). Per-axis mapping (CodeSearchNet/CoSQA/CoIR; SituatedQA/TimeQA/PAT-Questions/"Supersede"; RepoBench-R/CORE-Bench/CodeScaleBench; LongMemEval/LoCoMo/BEAM) with fit verdicts. Also confirmed the fixtures already exist as drafts (`facet_r2_draft.json` 50/20, `r1_dummy_gold.json` 135 queries), so the remaining work is graph-gated validation, not authoring; public corpora contribute methodology (CoSQA/CoIR paraphrasing, SituatedQA timestamp-flips), not gold.

## 2026-07-05 — R1 win gate recalibration (ignore saturated metrics)

**fix(r1):** `evaluate_win_gate` no longer requires beating a metric already saturated at the baseline. The old gate demanded a strict win on BOTH `exact_string_recall` AND `symbol_recall`, but on the real dummy-gold corpus `exact_string_recall` saturates at 1.0 (graphiti's internal RRF already fuses BM25 + cosine), so `1.0 > 1.0` could never fire regardless of a real win on the headroom metrics. Now: improvement metrics at/above `SATURATION_CEILING` (default 1.0) are exempt from the must-beat test but still may not regress; graduation requires a strict win on every UNSATURATED improvement metric with no saturated/stale/scope regression. If every improvement metric is saturated the gate refuses to graduate and records a `reason`. Gate output gained `eligible_metrics` / `saturated_metrics` / `saturation_ceiling` so the exemption is auditable. On the dummy-gold numbers the gate now graduates `E_hybrid_a0` (symbol 0.300→0.325) and recommends `hybrid_alpha=0.0`.

**test:** Added 3 `tests/test_r1_runner.py` cases (saturated-metric graduation, all-saturated refusal, saturated-metric-regression block). Existing gate tests unchanged and green (all use a contested baseline). Offline suite: 333 passed.

**docs:** `benchmark-notes/r1-dummy-gold-run.md` step 1 (recalibrate the gate) marked DONE; steps 2–3 (scale paraphrase family, fix symbol/scope families) + the real `hybrid_alpha` call remain corpus-gated.

## 2026-07-04 — Continuous Integration (GitHub Actions)

**ci:** Added `.github/workflows/ci.yml` — the first CI for the bench (closes the deferred-verification "CI can run archolith-bench" cross-cutting item / R0 sub-task). A `test` job runs the bench suite on Python 3.11 + 3.12; a `lint` job runs `ruff check archolith_bench tests`. The sibling packages `archolith-maintenance` (required) and `archolith-filter` / `archolith-mcp-audit` (the optional audit/filter integrations) are installed from their public GitHub repos (none are on PyPI), so the suite smoke test runs too.

**test:** Added `tests/conftest.py` collection guard — skips modules whose dependencies aren't installed: the R3/R5 ladder benches (import the separate `menhir` repo, which has private deps and is not CI-installable) and, when the audit/filter siblings are absent, the suite smoke test. All run whenever their deps are present (locally and in CI).

**chore(lint):** Cleared the 7 pre-existing ruff violations in the bench package (unused imports in `r1`/`r3`/`r5`; one dead `changed_in_window` call + its import in `r5/runner.py`) so the scoped lint gate is green. The `scripts/` lint debt is left as a separate follow-up.

## 2026-07-02 — LongMemEval Framework Consolidation

**refactor(lme):** Consolidated LongMemEval test harnesses into `scripts/longmemeval/` with centralized config, dispatcher, analysis layer, and runbook. All hardcoded values (ports, credentials, paths, models) moved to `config.sh` with environment-variable overrides. Promoted analysis harnesses (answer-accuracy matrix, MSC sweep, oracle ablation, retrieval quality) from session tmp dir into the framework. Added stratification documentation (6 question types, sampling trap warning) and campaign findings (node-only strongest config, frontier oracle selectivity, brief-construction bottleneck).

**docs:** New `scripts/longmemeval/README.md` runbook covers graph lifecycle, config reference, stratification rules, and troubleshooting. Pointer added to `.agent/README.md`.

## 2026-06-21 — Optional Suite Install Path

**docs(packaging):** Documented the launch-supported source checkout path for optional filter/audit dependencies: install `../archolith-filter` and `../archolith-mcp-audit` editable before `pip install -e ".[all]"`.

**launch:** Marked the optional sibling package publication-path gate resolved as source-first, while keeping standalone `.[all]` unavailable until sibling packages are published to the configured package index.

## 2026-06-21 — Shared Token Counting Primitive

**refactor(metrics):** `estimate_tokens()` and `estimate_messages_tokens()` now delegate primitive text counts to `archolith-maintenance` while preserving benchmark-owned content-only semantics.

**packaging:** Added `archolith-maintenance` as the shared helper dependency for canonical token accounting.

## 2026-06-21 — Token Metrics Phantom Count Remediation

**fix(metrics):** `estimate_tokens()` now returns `0` for `None`, empty, and whitespace-only content, and `estimate_messages_tokens()` no longer applies a minimum-one floor to empty message sets.

**tests:** Added regression coverage for empty inputs, multipart text/content parts, and image-only parts that should not add phantom tokens.

## 2026-06-21 — Remediation Safe Fixes

**packaging/docs:** Removed the deprecated license classifier, added `ruff` to the dev extra, corrected project URLs to the current remote, documented checkpoint lifecycle, and refreshed agent notes for configuration and shared token counting.

**maintenance:** Cleared safe ruff findings in API/display/proxy/restart/cost/harness tests, removed the dead `filter_only` proxy override, hoisted direct-arm detection out of the turn loop, added a trace fallback warning, and made external harness timeout configurable without changing the default.

**safety:** Updated memory benchmark production guards so proxy port `9800` is allowed for throwaway/local targets while staging/preprod/preview/release-like hosts are refused.

## 2026-06-21 — Memory A/B Client Threading

**fix(harness):** `run_memory_ab()` now creates a real chat `httpx.Client` and passes it into `send_fn`, fixing the real `send_chat` path that previously received `None`.

**lifecycle:** `HttpMenhirClient` now supports context-manager use and closes its underlying client when `run_memory_ab()` exits.

## 2026-06-21 — External Harness Env Hardening

**security:** External benchmark subprocesses now inherit only an explicit allowlist of OS environment variables plus adapter-declared overrides, preventing accidental parent-secret leakage.

**tests:** Added coverage for secret filtering, allowlisted `PATH`, override precedence, and OpenAI-compatible env construction.

## 2026-06-21 — Proxy Trace Polling and Upstream Reduction Metric

**fix(proxy):** Proxy trace matching now uses the benchmark's 1-based turn loop index and warns before falling back to the last trace turn.

**feat(proxy):** Added configurable proxy trace polling via `--poll-interval` and persisted `upstream_input_reduction_ratio` as the billing-meter prompt reduction metric separate from internal curation leverage.

**tests:** Added focused offline regressions for trace selection, fallback warning, upstream reduction calculation, and poll-interval entrypoint defaults.

## 2026-06-21 — Remediation Coverage and Benchmark Report Refresh

**test(proxy):** Added offline coverage for the main `run_benchmark()` loop, checkpoint resume, checkpoint cleanup, and collapse-abort behavior.

**test(restart/report):** Added restart/bootstrap scoring regressions plus report persistence and generated `BENCHMARKS.md` coverage.

**docs(report):** Regenerated `BENCHMARKS.md` through the CLI with the stale-evidence caveat intact and separate upstream-input versus internal-curation savings columns.

## 2026-06-21 — Tier 2 Metric Quality Remediation

**fix(probes):** Fact probes now use dependency-free morphology-aware keyword matching so simple inflections do not undercount recall.

**fix(continuity/restart):** Continuity path extraction now recognizes Windows, relative, dotfile, and common no-extension paths; restart/bootstrap scoring flags re-read intent without penalizing recovered facts.

**fix(longmemeval):** Deterministic LongMemEval scoring now rejects obvious negated-answer false positives while keeping official LLM-judge scoring deferred to a budgeted evidence pass.

## 2026-06-21 — Tier 3 Backlog Cleanup

**fix(harness):** Stub Menhir recall now ranks in O(n log n) without `list.index()`, LongBench letter extraction uses the last fallback letter, and real Menhir reset cleanup requires explicit confirmation or dry-run.

**security:** External benchmark temp directories now use a shared secure tempdir helper with best-effort `0700` permissions.

**maintenance/tests:** Extracted proxy run summary aggregation, added pricing-default completeness tests, and documented why `scripts/run_mteb_local.py` intentionally stays separate from `MtebAdapter`.

## 2026-06-20 — Token estimator validation

**fix(metrics):** `estimate_tokens()` now uses `tiktoken` `cl100k_base` when available and falls back to the
existing char-divide heuristic only when the optional tokenizer is absent.

**tests:** Added representative estimator fixtures for prose, JSON/tool schemas, code snippets, and mixed
OpenAI message arrays.

**docs:** Added `.agent/benchmark-notes/token-estimator-validation-2026-06-20.md` with measured heuristic
error bounds and a no-change recommendation for `archolith-context` production token accounting.

**follow-up:** Added the planned `archolith_bench/suites/token_estimator.py` validation suite and the
acceptance report at `results/token-estimator-2026-06-20.md`.

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
