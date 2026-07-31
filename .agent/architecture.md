# archolith-bench — Architecture

## Overview

archolith-bench is the unified benchmark suite for the archolith product family. It measures proxy context assembly savings, client-side filter compression ratios, MCP audit waste reduction, and full-stack additive contributions across reproducible multi-turn coding scenarios.

The benchmark is a **CLI tool**, not a service. It runs offline, sending controlled conversation scenarios through the archolith proxy and/or direct upstream API, collecting token metrics, continuity data, and quality scores.

## Role in the Archolith Ecosystem

| Layer | Project | What archolith-bench measures |
|-------|---------|------------------------------|
| L0–L2 | archolith-filter | Compression ratios across 8 categories of tool output corpora |
| L3 | archolith-audit / archolith-mcp-audit | MCP token-waste reduction before/after server-side fixes |
| L4 | archolith-context (proxy) | Multi-turn token savings, continuity, restart/orientation scores |
| Stack | All layers | Experimental four-way additive comparison: direct / filter-only / proxy-only / proxy+filter |
| Launch | All products | Industry benchmark coverage matrix and claim gates |

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.11+ |
| HTTP client | httpx >= 0.27 |
| Config | python-dotenv (`.env` file) |
| Token counting | archolith-maintenance primitive; tiktoken when available |
| Filter compression | archolith-filter (peer dependency) |
| Audit comparison | archolith-audit distribution (`archolith_mcp_audit`, source repo `archolith-mcp-audit`) |
| Packaging | setuptools (pyproject.toml) |
| Linting | ruff |
| Testing | pytest |

### Dashboard scalar explorer (transitional — being replaced)

`archolith_bench/dashboard.py` owns the local HTTP surface and manifest/checkpoint allowlist.
**The standalone `:8200` dashboard is transitional.** Menhir Recall Lab (`/explorer/recall-lab/bench-runs/`)
is the canonical owner for benchmark task inspection. Keep the `:8200` dashboard as a temporary fallback
until the Menhir explorer covers all scalar viewer detail (evidence, assertions, views, memory inventory,
derivation classification).
`archolith_bench/scalar_viewer.py` owns the read-only provenance model. Its Neo4j path keeps the
four scalar measurement boundaries separate (`TurnEvidence` → gate → `TypedAssertion` → View),
while the optional SQLite path reads the behavior-neutral consolidation receipt. Audit selection
is graph-correlated by `source_key`/`assertion_id`; a newer telemetry pass from a different graph
attempt is not presented as provenance for the graph currently on screen. Evidence cards display
both `occurred_at` source/world time and `recorded_at` Menhir-ingest time; historical LME ordering
must never be inferred from the latter.

The scalar explorer shows `scalar_state` and `scalar_history` Views side by side. History Views
render advisory entry tables (source time / operation / value / stated span) with a delta-only
warning; when `scalar_state` abstains, the answer section shows the abstention reason alongside the
advisory history with the latest delta value. `ScalarTaskReader.read()` returns `history_views`
with parsed JSON payload and op_counts. Each returned assertion also carries separate state/history
fold outcomes derived from View contributor provenance, binding state, and the correlated
consolidation receipt. The assertion stage therefore distinguishes current contributors,
history-only assertions, safe fold abstentions, expiries, pending bindings, and write failures.
Blocked assertion cards resolve the assertion's `evidence_id` (falling back to its `FOUNDS` edge)
to show the complete original `TurnEvidence` quote beside the shorter extracted span.

The browser calls `/api/scalar-tasks` for manifest-scoped choices and
`/api/scalar-task?namespace=...` for one snapshot. Bolt credentials and the telemetry path remain
inside the dashboard process. The page refresh loop replaces only benchmark progress, so an open
scalar walkthrough and its selected stage are not reset every five seconds. The same refresh tick
updates the task catalog in place as manifest rows arrive. Every manifested task remains selectable;
namespaces whose graph evidence is temporarily unavailable are labeled instead of being hidden.
Each task also has a stable `/tasks/<namespace>` URL. Its memory-map stage distinguishes ordinary
relationship-fact `CONTENT` from rebuildable `scalar_state`/`scalar_history` `VIEW` records. View
provenance is further labeled `absolute`, `delta`, or `mixed` from contributing assertion operations;
source evidence and `TypedAssertion` rows remain separate pipeline artifacts rather than being
misrepresented as recall memories. `/tasks/` is the searchable task directory: it joins every
completed manifest task to its available checkpoint scores, assertion/View counts, and detail URL.

## Data Flow

```
Scenario JSON (scenarios/*.json)
        │
        ▼
┌──────────────────────────────┐
│  CLI (cli.py)                │  Parse args, validate arms/budgets
│  main() → _run_proxy/filter/ │
│  stack/audit/report          │
└──────────┬───────────────────┘
           │
           ▼
┌──────────────────────────────┐
│  Suite Runner                 │
│  suites/proxy.py              │  Per-turn loop, arm config, fact probes
│  suites/filter.py             │  Corpus scan → filter_output() per sample
│  suites/audit.py              │  Load before/after JSON → compare_reports()
│  suites/stack.py              │  Run proxy suite 4× for four-way comparison
│  suites/industry.py           │  Product → external benchmark matrix
└──────────┬───────────────────┘
           │
    ┌──────┴──────┐
    ▼             ▼
┌─────────┐  ┌──────────────┐
│ Direct   │  │ Proxy (9800) │  Send chat, collect response + token usage
│ Upstream │  │ archolith-   │  For proxy arms: fetch trace for metrics
│ API      │  │ context      │
└────┬─────┘  └──────┬───────┘
     │               │
     ▼               ▼
┌──────────────────────────────┐
│  Metrics + Continuity        │  TokenMetrics, ContinuityMetrics,
│  core/metrics.py             │  QualityPerfMetrics, TurnResult
│  suites/proxy.py (tracker)   │
└──────────┬───────────────────┘
           │
           ▼
┌──────────────────────────────┐
│  Report / Output              │  JSON results → results/
│  core/report.py               │  Markdown tables → BENCHMARKS.md
└──────────────────────────────┘
```

### Proxy Suite Flow (`suites/proxy.py`)

1. Set proxy budget via `POST /admin/config` (context_token_budget)
2. Apply arm-specific config overrides (RTK enabled/disabled, assembly_mode)
3. For each turn in the scenario:
   a. Send `direct_history` to direct upstream → baseline response + tokens
   b. Send `arm_history` to appropriate endpoint (proxy or direct, per arm)
   c. For proxy arms: fetch proxy trace (`GET /trace/turns/{turn_id}`) → assembly metrics
   d. For `filter_only` arm: preprocess history through `archolith_filter.filter_output` before sending
   e. Run `ContinuityTracker.observe_turn()` → count repeat reads/diagnostics
   f. Run fact probes at designated turns (if `--no-probes` not set)
   g. Save checkpoints after each turn (resumable via `--resume`)
   h. Detect output collapse: response <50 tokens, 2 consecutive = abort
4. After all turns:
   a. Compute `ContinuityMetrics` from tracker
   b. Run restart/bootstrap: replay scenario, start fresh conversation, ask orientation question → `turn_one_orientation_score`
   c. Produce summary (`total_direct_input_tokens`, `total_proxy_input_tokens`, `overall_savings_ratio`)
   d. Save JSON results + markdown transcripts

### Filter Suite Flow (`suites/filter.py`)

1. Scan `corpora/` for `.txt` files, infer category from filename prefix
2. For each sample: run `filter_output()` with category-specific command/tool hints
3. Record raw tokens vs filtered tokens, savings ratio
4. Group results by category (git_diff, git_log, git_status, json, logs, read_file, search, test)
5. Output: `results/filter_results.json` + optional `results/filter_results.md`

### Audit Suite Flow (`suites/audit.py`)

1. Load before and after JSON audit reports
2. Call `archolith_mcp_audit.comparator.compare_reports()` → `ServerDelta` objects
3. Compute per-server and aggregate token/waste deltas
4. Format human-readable report via `format_delta_report()`
5. Output: `results/audit_comparison.json` + optional markdown

### Industry Suite Flow (`suites/industry.py`)

1. Read the executable registry in `core/industry.py`
2. Filter by product/suite when requested
3. Write `results/industry_benchmarks.json` and `results/industry_benchmarks.md`
4. Optionally write a tracked launch artifact, usually `benchmarks/industry-trusted-benchmark-coverage.md`
5. Report generator includes the matrix when `results/industry_benchmarks.json` exists

The industry suite records external benchmark families such as RULER,
LongBench v2, SWE-bench, BigCodeBench, HELM, MTEB, CyberSecEval, AgentDojo,
and OWASP LLM/application security checks. It does not claim those benchmarks
are complete. `candidate-before-launch` entries are explicit gates until a
tracked evidence file exists.

### Stack Suite Flow (`suites/stack.py`)

Status: experimental pending refreshed live-proxy run. Do not use stack results
as launch headline copy until tracked evidence is added under `benchmarks/`.

Runs the same scenario through 4 fixed arms sequentially:
1. `direct` — baseline (no filter, no proxy)
2. `filter_only` — client-side filter, no proxy
3. `proxy_only` — proxy assembly, no filter
4. `proxy_plus_filter` — full stack

Produces a four-way comparison table showing additive contributions of each layer.

## Key Components

### CLI (`cli.py`)

Argparse-based entry point. Six suite/reporting subcommands: `proxy`, `filter`, `stack`, `audit`, `industry`, `report`. Handles argument validation, proxy health checks, arm name resolution, benchmark coverage filtering, and dispatches to suite runners.

### Experiment Arms (`arms.py`)

Six named experiment arms defined in `ARM_DEFINITIONS` dict. Each arm specifies:
- `filter_enabled` — whether to apply archolith-filter preprocessing
- `proxy_enabled` — whether to route through the archolith proxy
- `config_overrides` — dict of proxy `/admin/config` overrides

Four arms are in the "proxy family" (`proxy_enabled=True`): `proxy_only`, `proxy_plus_filter`, `proxy_typed_state`, `proxy_state_snippets`.

### API Helpers (`core/api.py`)

- `send_chat()` — HTTP POST to chat completions endpoint with exponential backoff on 429
- `set_proxy_budget()` — `POST /admin/config` to set context_token_budget
- `apply_arm_config()` — apply arm config overrides to proxy
- `get_proxy_trace()` — fetch turn trace for assembly metrics
- `check_proxy_health()` — `GET /health` to verify proxy is reachable
- `estimate_tokens()` / `estimate_messages_tokens()` — content-only token estimation via `archolith-maintenance`

### Scenario Models (`core/scenario.py`)

`Scenario` dataclass with `from_file()` factory. Scenarios live as JSON files in `scenarios/`. Each defines: `name`, `description`, `system_prompt`, `turns` (list of user messages), and optional `fact_probes` (questions with expected keywords asked at designated turns).

### Metrics (`core/metrics.py`)

| Dataclass | Purpose |
|-----------|---------|
| `TokenMetrics` | Per-turn token economics: direct vs arm input, savings ratio, extraction cost, net savings |
| `ContinuityMetrics` | Cross-turn behavior: repeat file reads, repeat diagnostics, decision retention, verification continuity, orientation score, snippet hit rate |
| `QualityPerfMetrics` | Quality + performance: fact recall accuracy, response similarity, assembly latency, total latency |
| `TurnResult` | Single turn: user message, direct/proxy responses, trace data, token + continuity metrics |
| `ScenarioResult` | Full run: scenario metadata, arm/budget, aborted status, summary, continuity, all turn results, fact probes |
| `IndustryBenchmark` | External benchmark mapping: product, suite, authority, status, launch gate, command, evidence path |

### Continuity Tracker (`suites/proxy.py`)

`ContinuityTracker` class observes each turn's tool calls and results. Counts:
- Repeat file reads (same path read in multiple turns)
- Repeat diagnostics (same command run in multiple turns)
- Decision retention (from fact probe results)
- Verification continuity (from final-turn verification responses)

Also computes `turn_one_orientation_score` via restart/bootstrap: replays the scenario, then starts a fresh conversation to test whether the model recovers context without re-reading files.

### Report Generator (`core/report.py`)

- `print_summary()` — per-run human-readable summary
- `print_cross_scenario_summary()` — comparison across multiple runs
- `print_four_way_table()` — stack suite four-arm comparison
- `save_results()` — JSON output to `results/`
- `write_benchmarks_md()` — generates `BENCHMARKS.md` from all results
- Includes `results/industry_benchmarks.json` when present, so generated `BENCHMARKS.md` shows trusted benchmark coverage and evidence paths

## Persistent LongMemEval ingestion fixtures

The persistent LongMemEval builder lives under `scripts/longmemeval/`. Its Python ingester accepts
either the Hugging Face dataset or an explicit offline JSON fixture. Fixture runs use the same
`HttpMenhirClient`, per-turn ingestion, queue drain, failed-episode retry, manifest, promotion,
and Graphiti-backed graph mutation as a normal build. Parsed `haystack_dates` are sent as
`occurred_at` on both the episode and its `TurnEvidence`; Menhir retains its own `recorded_at`
separately for processing cursors.

`run_suburbs_fixture.sh` is the canonical extraction-regression entrypoint. It gives the run a
dedicated Neo4j container, volume, ports, manifest, logs, and result directory; refuses accidental
reuse unless resume is explicitly enabled; checks that Menhir contains the required fix commit;
then verifies current and retired graph facts directly. Fixture evidence is diagnostic and must
not be reported as full LongMemEval answer-accuracy evidence.
The first live run on 2026-07-16 is intentionally recorded as RED: the exact long utterance kept
the suburb proposition but bound it to Chicago. Full-corpus rebuilds are gated on this fixture
becoming green.




## Configuration / Environment Variables

All configuration via `.env` file:

| Variable | Purpose | Default |
|----------|---------|---------|
| `UPSTREAM_API_KEY` | API key for direct upstream and proxy forwarding | (required) |
| `PROXY_URL` | Proxy chat completions endpoint | `http://localhost:9800/v1` |
| `UPSTREAM_BASE_URL` | Direct upstream API for baseline comparison | `https://api.openai.com/v1` |
| `BENCHMARK_MODEL` | Model used for benchmark conversations | `gpt-4o-mini` |
| `PROXY_PORT` | Proxy port (used to build PROXY_URL fallback) | `9800` |

## External Dependencies

| Dependency | Purpose | Required |
|------------|---------|----------|
| archolith-context (proxy) | Proxy endpoint for proxy/stack suites | For proxy/stack suites |
| archolith-filter | Filter compression in filter suite + filter_only arm | Optional extra: `filter` / `all` |
| archolith-audit distribution (`archolith_mcp_audit`) | Audit comparison | Optional extra: `audit` / `all`; source checkout lives at `../archolith-mcp-audit` |
| archolith-maintenance | Shared token-counting primitive | Yes (pip/editable peer) |
| httpx | HTTP client for all API calls | Yes (pip) |
| python-dotenv | `.env` file loading | Yes (pip) |
| Upstream LLM API | Chat completions for benchmark conversations | Yes (API key) |
| tiktoken | Accurate token counting through `archolith-maintenance` when installed | Transitive optional |

## Port Assignment

| Service | Port |
|---------|------|
| archolith-context proxy | 9800 (benchmark default; 9800 in proxy's own docs) |

## File Layout

```
archolith-bench/
├── pyproject.toml
├── .env / .env.example
├── AGENTS.md
├── README.md
├── LICENSE
├── archolith_bench/          # Main package
│   ├── cli.py                # CLI entry point
│   ├── arms.py               # Experiment arm registry
│   ├── core/
│   │   ├── api.py            # HTTP helpers
│   │   ├── corpus.py         # Corpus loader for filter suite
│   │   ├── industry.py       # Trusted benchmark registry
│   │   ├── metrics.py        # Metric dataclasses
│   │   ├── report.py         # Report generation
│   │   └── scenario.py       # Scenario loading
│   └── suites/
│       ├── proxy.py          # Proxy benchmark runner
│       ├── filter.py         # Filter compression benchmark
│       ├── industry.py       # Industry benchmark coverage report
│       ├── audit.py          # Audit before/after comparison
│       └── stack.py          # Four-way stack comparison
├── scenarios/                # Multi-turn conversation JSON
├── corpora/                  # Tool-output samples for filter suite
├── fixtures/                 # Sample audit before/after JSON
├── results/                  # Benchmark output
└── .agent/                   # Agent context docs
    ├── README.md
    ├── architecture.md
    ├── data_models.md
    ├── CHANGELOG.md
    └── workflows/
        └── code_conventions.md
```
