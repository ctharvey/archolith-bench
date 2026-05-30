# archolith-bench

Benchmark suite for the [archolith](https://github.com/ctharvey/archolith) token-reduction stack.
Measures proxy context assembly, client-side filtering, and MCP audit savings
across reproducible multi-turn coding scenarios.

### Headline numbers (2026-05-30)

| Metric | Value | Source |
|--------|-------|--------|
| Proxy token savings | **58.6%** | 10-turn code review, DeepSeek upstream |
| Filter compression | **50.0%** | 12 real session samples, 8 categories |
| MCP waste reduction | **71.5%** | Live session telemetry, 5 servers |
| Best single-turn savings | **75%** | Curator mode, turns 6+ |

See [BENCHMARKS.md](BENCHMARKS.md) for full tables and reproduction instructions.

## Suites

| Suite | Purpose |
|-------|---------|
| `proxy` | Multi-turn token savings and continuity measurement |
| `filter` | Compression-ratio measurement on real tool-output corpora |
| `audit` | MCP token-waste reduction before/after comparison |
| `stack` | Four-way headline comparison (direct/filter/proxy/proxy+filter) |

## Quick Start

```bash
pip install -e .

# List available scenarios (no live proxy needed)
archolith-bench proxy --list

# Run a single scenario against a live proxy
archolith-bench proxy --scenario scenarios/taskflow.json --arms direct,proxy_only

# Run all scenarios across multiple budgets
archolith-bench proxy --all --arms direct,proxy_only,proxy_plus_filter --budgets 4000,15000
```

## Experiment Arms

| Arm | Filter | Proxy Assembly | What It Measures |
|-----|--------|----------------|-----------------|
| `direct` | off | off | Baseline |
| `filter_only` | on | off | Filter token savings alone |
| `proxy_only` | off | on (baseline) | Context engine without filter |
| `proxy_plus_filter` | on | on (filter as engine) | Full-stack headline |
| `proxy_typed_state` | on | on + typed work state | Typed state continuity |
| `proxy_state_snippets` | on | on + snippet injection | Snippet continuity |

## Configuration

Set environment variables in `.env`:

- `UPSTREAM_API_KEY` (required for runs)
- `PROXY_URL` (default: `http://localhost:9801/v1`)
- `UPSTREAM_BASE_URL` (default: `https://integrate.api.nvidia.com/v1`)
- `BENCHMARK_MODEL` (default: `gpt-4o-mini`)

## License

Source-available under the [PolyForm Noncommercial License 1.0.0](LICENSE).
Free for non-commercial use; commercial use requires permission from the licensor.
Contributions are subject to the [CLA](CLA.md).

"archolith" is a trademark of Charles Harvey. Use of the name in derivative
works or competing products requires explicit permission.