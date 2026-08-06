# archolith-bench — Data Models

No database. All state is in-memory dataclasses, JSON files on disk, and checkpoint files.

## Offline deterministic scalar shadow report

`archolith_bench.deterministic_scalar_shadow` measures Menhir's frozen typed-scalar proposals over
the exact episode content captured by `scripts/freeze_scalar_samples.py`. The report is read-only
and machine-generated: it reruns Menhir's pure deterministic extractor on that frozen episode text
and replays the captured LLM proposals through Menhir's real gate/comparator. It makes no new LLM,
network, Neo4j, Docker, or service calls.

| Field | Meaning |
|-------|---------|
| `provenance` | capture paths/hashes/settings, sidecar path/hash/capture bindings, report schema, generation time, Menhir commit/dirty state, extractor/template versions |
| `effective_gate_settings` | explicit threshold, span-alignment, reconciliation, and canonical-self settings used for this report |
| `aggregate` / `namespaces` | episode eligibility, deterministic proposals, committed LLM claims, canonical exact/aligned one-to-one agreement, router misses, class/reason counts, and ratios with denominators |
| `call_savings` | baseline k calls and conservative future calls saved at the namespace-batch boundary; partial namespaces save zero |
| `measurements` | token/cost savings, `null` unless measured fields support such a claim |

The optional label sidecar is versioned (`schema_version: 1`) and capture-local. Its required
`capture_sha256` is a non-empty list of unique canonical lowercase SHA-256 strings whose set exactly
matches all measured captures. Each `false_positive` or `false_current` row is a human-labeled
known-negative target, not a reviewed sample of all admissions. The report uses stable
`known_negative_target_hit_rate` semantics with `hit_count`, `labeled_negative_targets`, and
`hit_rate`; this is not an overall/population false-positive or false-current rate and does not
satisfy the plan's population precision/confidence-interval gate. A category without labeled
negative targets is `not_measured` with null numeric fields.

## Historical scalar spend attribution report

The offline `scalar-spend-attribution/v1` report is descriptive evidence for a completed
historical run. Its explicit JSON and Markdown outputs are collision-preflighted against every
input artifact and each other, then atomically published; manifest, provenance, checkpoint, and
SQLite inputs remain read-only, with SQLite opened in read-only mode.

| Top-level contract | Meaning |
|--------------------|---------|
| `input_artifacts` | Exact manifest, provenance, telemetry, and recall-checkpoint paths plus SHA-256 hashes |
| `provenance` | Observed canonicality concerns, attempt/commit/dirty/interruption facts; full canonical acceptance is not evaluated |
| `manifest` | Aggregate and per-namespace scalar calls, artifacts, failures/timeouts/consolidation, and the namespace/task join |
| `telemetry` | Only completed `episode_task_events` Graphiti ingest chat events with parent task exactly `memory: graphiti add_episode`; includes model/endpoint distributions and a chronological timezone-aware first/last boundary |
| `recall_checkpoint` | Per-arm row/call counts, correctness, measured input/output/total tokens, latency, model identity when available, and presentation-only state/history signatures |
| `pricing` | Explicit input/output USD-per-million rates used for recall answer-cost arithmetic; current or inferred pricing is not used |
| `attribution` | Scalar-caused corrections and cost per scalar-corrected answer are `null`/`not_measured` without a scalar-disabled counterfactual; unpersisted scalar or judge token/cost usage remains `null`/`not_measured` |
| `negative_controls` | Explicit caller-selected task IDs with the same accounting and presentation checks; no benchmark-specific IDs are implied |
| `limitations` | Noncanonical/descriptive status, stage-specific call-count comparisons, absent scalar economics, absent causal counterfactual, and other evidence gaps |

## Persistent LongMemEval Regression Fixture

`fixtures/longmemeval/menhir_suburbs_extraction_regression.json` is a one-item LongMemEval-compatible
JSON array. In addition to the standard `question_id`, `question_type`, `question`, `answer`,
`haystack_sessions`, `haystack_dates`, and `haystack_session_ids` fields, the item carries
`fixture_expectations`: the isolated namespace, current subject/object/fact matchers, stale object,
minimum turn count, and required Menhir commit. The persistent ingester records the resolved fixture
path in each manifest row. Each parsed `haystack_dates` value is the shared `occurred_at` world time
for the session's episodes and TurnEvidence; Menhir's later server receive time is a separate
`recorded_at` processing timestamp.


## Bootstrap Hygiene Models (`bootstrap_hygiene/`)

`BootstrapFixture` contains explicit workspace keys, memory records, and an off-topic query. Each `BootstrapRecord` may be recent semantic memory, structural noise, a retention pin with `general`/`workspace:<key>` scope, or a stale-advisory sentinel. `BootstrapHygieneRunner` emits hard gate booleans plus report-only negative-query and input-token metrics in both deterministic offline and guarded live black-box modes.

## Scenario Models (`core/scenario.py`)

### Scenario

Multi-turn conversation definition loaded from `scenarios/*.json`.

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Short scenario identifier |
| `description` | `str` | Human-readable scenario description |
| `system_prompt` | `str` | System prompt injected at conversation start |
| `turns` | `list[str]` | Ordered list of user messages, one per turn |
| `fact_probes` | `list[FactProbe]` | Optional fact recall probes with expected keywords |

Factory: `Scenario.from_file(path: Path) -> Scenario`

### FactProbe

A fact recall question asked at a specific turn to measure continuity.

| Field | Type | Description |
|-------|------|-------------|
| `after_turn` | `int` | Turn number after which the probe is asked |
| `question` | `str` | The probe question text |
| `expected_keywords` | `list[str]` | Keywords expected in a correct answer |

## Metric Models (`core/metrics.py`)

### TokenMetrics

Per-turn token economics for a single arm vs direct baseline.

| Field | Type | Description |
|-------|------|-------------|
| `direct_input` | `int` | Tokens sent to direct upstream (baseline) |
| `arm_input` | `int` | Tokens sent to arm endpoint (proxy or direct+filter) |
| `rewritten_tokens` | `int` | Tokens after proxy curation (from proxy trace) |
| `savings_ratio` | `float` | `(direct_input - rewritten_tokens) / direct_input` |
| `extraction_cost` | `int` | Tokens consumed by extractor LLM calls |
| `net_savings` | `int` | `(direct_input - rewritten_tokens) - extraction_cost` |

### ContinuityMetrics

Cross-turn behavioral metrics capturing whether the model re-reads or re-runs things.

| Field | Type | Description |
|-------|------|-------------|
| `repeat_file_reads` | `int` | Count of files read more than once |
| `repeat_diagnostics` | `int` | Count of commands run more than once |
| `decision_retention` | `float` | Fraction of fact probe keywords correctly recalled (0.0–1.0) |
| `verification_continuity` | `float` | Final-turn verification score |
| `turn_one_orientation_score` | `float` | Restart/bootstrap: does the model orient without re-reading? (0.0–1.0) |
| `snippet_hit_rate` | `float` | For snippet arms: fraction of recalled snippets that were relevant |

### QualityPerfMetrics

Quality and performance measurements.

| Field | Type | Description |
|-------|------|-------------|
| `fact_recall_accuracy` | `float` | Accuracy on fact probe questions (0.0–1.0) |
| `response_similarity` | `float` | Cosine similarity between direct and proxy arm responses |
| `assembly_latency_ms` | `float` | Proxy assembly time in milliseconds |
| `total_latency_ms` | `float` | End-to-end request time in milliseconds |

### TurnResult

Single turn result for one arm.

| Field | Type | Description |
|-------|------|-------------|
| `turn` | `int` | Turn number (0-indexed) |
| `user_msg_preview` | `str` | Truncated preview of the user message |
| `user_msg` | `str` | Full user message text |
| `direct` | `dict` | Raw direct upstream response |
| `proxy` | `dict` | Raw proxy arm response |
| `trace` | `dict` | Proxy trace data (assembly metrics, token savings) |
| `token_metrics` | `TokenMetrics` | Token savings for this turn |
| `continuity` | `ContinuityMetrics` | Continuity observations for this turn |

### ScenarioResult

Full benchmark run result, serialized to `results/*.json`.

| Field | Type | Description |
|-------|------|-------------|
| `scenario` | `str` | Scenario filename |
| `description` | `str` | Scenario description |
| `model` | `str` | Model used |
| `budget` | `int \| None` | Token budget (None = default) |
| `arm` | `str` | Arm name |
| `turns_run` | `int` | Actual turns completed |
| `turns_total` | `int` | Total turns in scenario |
| `aborted` | `bool` | Whether the run was aborted |
| `abort_reason` | `str` | Reason for abort (e.g., output collapse) |
| `timestamp` | `str` | ISO 8601 run timestamp |
| `summary` | `dict` | Aggregate token/arm summary |
| `quality` | `dict` | Quality metrics dict |
| `continuity` | `ContinuityMetrics` | Aggregate continuity for the run |
| `turns` | `list[TurnResult]` | All turn results |
| `fact_probes` | `list[dict]` | Probe results |

## Corpus Models (`core/corpus.py`)

### CorpusSample

A single tool-output sample loaded from `corpora/`.

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Filename without extension |
| `category` | `str` | Inferred category (git_diff, git_log, json, search, test, etc.) |
| `path` | `Path` | Full file path |
| `raw_text` | `str` | Full raw text content |

## Filter Suite Models (`suites/filter.py`)

### FilterResult

Per-sample filter compression result.

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Sample name |
| `category` | `str` | Tool output category |
| `raw_chars` | `int` | Original character count |
| `filtered_chars` | `int` | Compressed character count |
| `raw_tokens` | `int` | Estimated original tokens |
| `filtered_tokens` | `int` | Estimated compressed tokens |
| `savings_ratio` | `float` | `(raw_tokens - filtered_tokens) / raw_tokens` |
| `truncated` | `bool` | Whether the sample was truncated |

## Experiment Arms (`arms.py`)

### Arm Definition

Each arm is a dict entry in `ARM_DEFINITIONS`:

| Key | Type | Description |
|-----|------|-------------|
| `label` | `str` | Human-readable arm label |
| `filter_enabled` | `bool` | Preprocess with archolith-filter |
| `proxy_enabled` | `bool` | Route through archolith proxy |
| `config_overrides` | `dict` | Proxy `/admin/config` overrides |

Six arms defined:

| Arm | Filter | Proxy | Assembly Mode |
|-----|--------|-------|---------------|
| `direct` | off | off | — |
| `filter_only` | on | off | — |
| `proxy_only` | off | on | baseline |
| `proxy_plus_filter` | on | on | filter as engine |
| `proxy_typed_state` | on | on | typed_state |
| `proxy_state_snippets` | on | on | state_snippets |

`PROXY_FAMILY_ARMS` is the subset of arms where `proxy_enabled=True`: `proxy_only`, `proxy_plus_filter`, `proxy_typed_state`, `proxy_state_snippets`.

## Industry Benchmark Registry (`core/industry.py`)

### IndustryBenchmark

Executable launch coverage entry tying one Archolith product to a trusted
external benchmark family.

| Field | Type | Description |
|-------|------|-------------|
| `benchmark_id` | `str` | Stable local identifier such as `ruler` or `swe-bench` |
| `name` | `str` | Public benchmark name |
| `product` | `str` | Archolith product the benchmark applies to |
| `suite` | `str` | Local archolith-bench suite or future suite owner |
| `authority` | `str` | Maintainer or institution behind the external benchmark |
| `benchmark_type` | `str` | What capability the benchmark measures |
| `status` | `str` | `implemented-local` or `candidate-before-launch` |
| `source_url` | `str` | Canonical project/source URL |
| `paper_url` | `str` | Paper or formal benchmark description URL |
| `rationale` | `str` | Why the benchmark is relevant to the product |
| `local_coverage` | `str` | What archolith-bench currently implements or lacks |
| `launch_gate` | `str` | Exit criteria before using the benchmark in public claims |
| `run_command` | `str` | Local command or TODO for executing the benchmark path |
| `evidence_path` | `str` | Expected tracked artifact under `benchmarks/` |

Registry output:

| File | Purpose |
|------|---------|
| `results/industry_benchmarks.json` | Machine-readable registry output |
| `results/industry_benchmarks.md` | Generated human-readable matrix |
| `benchmarks/industry-trusted-benchmark-coverage.md` | Tracked launch artifact when generated with `--out` |

## Repository Reference

| Data | Storage | Access |
|------|---------|--------|
| Scenario definitions | `scenarios/*.json` | `Scenario.from_file()` |
| Corpus samples | `corpora/*.txt` | `CorpusSample` loader |
| Fixture audit reports | `fixtures/audit_*.json` | Loaded by audit suite |
| Benchmark results | `results/*.json` | Read by report generator |
| Industry benchmark registry | `archolith_bench/core/industry.py` | Read by industry suite and report generator |
| Checkpoints | `.checkpoint_*.json` (cwd) | Resumable state |
| Experiment metadata | `experiments/<name>/` | Experiment mode |

No enums are defined. Categories, arm names, and output formats are string-validated at the CLI boundary.
