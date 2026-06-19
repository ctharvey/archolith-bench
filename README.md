# archolith-bench

Benchmark suite for the [archolith&trade;](https://github.com/archolith/archolith-bench) token-reduction stack.
Measures proxy context assembly, client-side filtering, and MCP audit savings
across reproducible multi-turn coding scenarios.

### Headline numbers (2026-05-30)

| Metric | Value | Source |
|--------|-------|--------|
| Proxy upstream input reduction | **25.8%** | `proxy_only`, 15K budget, 10-turn code review, DeepSeek upstream |
| Filter compression | **49.5%** | 12 real session samples, 8 categories |
| MCP waste reduction | Pending live run | Fixture-only result is not a launch headline |

TODO: refresh the proxy benchmarks before launch and replace the single-scenario
headline with a broader run across current proxy settings, budgets, and models.

See [BENCHMARKS.md](BENCHMARKS.md) for full tables and reproduction instructions,
and [`benchmarks/`](benchmarks/) for tracked evidence summaries.

## Suites

| Suite | Purpose |
|-------|---------|
| `proxy` | Multi-turn token savings and continuity measurement |
| `filter` | Compression-ratio measurement on real tool-output corpora |
| `audit` | MCP token-waste reduction before/after comparison |
| `stack` | Experimental four-way comparison; pending refreshed live run |
| `industry` | Launch coverage matrix mapping products to trusted external benchmark families |

## Quick Start

```bash
# Base CLI install
pip install -e .

# List available scenarios (no live proxy needed)
archolith-bench proxy --list
```

Install optional suite dependencies when you need filter or audit runs:

```bash
pip install -e ".[all]"

# Run a single scenario against a live proxy
archolith-bench proxy --scenario scenarios/taskflow.json --arms direct,proxy_only

# Run all scenarios across multiple budgets
archolith-bench proxy --all --arms direct,proxy_only,proxy_plus_filter --budgets 4000,15000
```

Generate the industry benchmark coverage matrix before launch:

```bash
archolith-bench industry --launch-only --out benchmarks/industry-trusted-benchmark-coverage.md
```

The industry matrix is not a substitute for completed benchmark evidence. It
separates implemented local coverage from candidate-before-launch work such as
SWE-bench, LongBench v2, CyberSecEval, AgentDojo, OWASP security checks, and
real audit logs.

The base install supports the CLI, report generation, and proxy orchestration.
The `filter`, `audit`, and `all` extras install sibling Archolith suite
dependencies when those packages are available from your package index or local
editable environment.

## Experiment Arms

| Arm | Filter | Proxy Assembly | What It Measures |
|-----|--------|----------------|-----------------|
| `direct` | off | off | Baseline |
| `filter_only` | on | off | Filter token savings alone |
| `proxy_only` | off | on (baseline) | Context engine without filter |
| `proxy_plus_filter` | on | on (filter as engine) | Full-stack experimental arm |
| `proxy_typed_state` | on | on + typed work state | Typed state continuity |
| `proxy_state_snippets` | on | on + snippet injection | Snippet continuity |

## Configuration

Set environment variables in `.env`:

- `UPSTREAM_API_KEY` (required for runs)
- `PROXY_URL` (default: `http://localhost:9800/v1`)
- `UPSTREAM_BASE_URL` (default: `https://api.openai.com/v1`)
- `BENCHMARK_MODEL` (default: `gpt-4o-mini`)

## License

Source-available under the [PolyForm Noncommercial License 1.0.0](LICENSE).
Free for non-commercial use; commercial use requires permission from the licensor.
Contributions are subject to the [CLA](CLA.md).

archolith&trade; is a trademark of Charles Harvey. Use of the name in
derivative works or competing products requires explicit permission.
