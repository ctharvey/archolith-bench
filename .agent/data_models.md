# archolith-bench — Data Models

No database. All state is in-memory dataclasses, JSON files on disk, and checkpoint files.

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
