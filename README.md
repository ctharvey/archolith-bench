# archolith-bench

Unified benchmark suite for the archolith product family.

## Suites

| Suite | Purpose | Status |
|-------|---------|--------|
| `proxy` | Multi-turn token savings and continuity measurement | Phase 1 (critical path) |
| `filter` | Compression-ratio product claim on real corpora | Phase 2 |
| `audit` | MCP token-waste reduction before/after | Phase 4 |
| `stack` | Four-way headline comparison (direct/filter/proxy/proxy+filter) | Phase 3 |

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