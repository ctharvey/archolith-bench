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
| `harness` | Runs official external benchmarks (e.g. LongBench v2) as a direct-vs-proxy A/B |

### Harness: official benchmarks as direct-vs-proxy A/B

Archolith is middleware, not a model, so a harness adapter never claims a standalone
benchmark score. It runs the official dataset + scorer twice (client pointed at the direct
upstream, then at the proxy) and reports the **delta**: official score preserved while input
tokens and cost drop. Local-analogue scenarios (RULER) are `-style` smoke tests only.

Adapters (all under one roof):

| Benchmark id | Kind | Extra |
|--------------|------|-------|
| `longbench-v2` | in-process | `longbench` |
| `bigcodebench-hard` | in-process (sandboxed exec) | `bigcodebench` |
| `longmemeval` | in-process (menhir memory capability) | `longmemeval` |
| `swe-bench` | external-cli wrapper | `swebench` |
| `cyberseceval-4` | external-cli wrapper | `cyberseceval` |
| `agentdojo` | external-cli wrapper | `agentdojo` |
| `mteb-retrieval` | external-cli wrapper (embeddings; see caveat) | `mteb` |

```bash
archolith-bench harness --list
pip install -e ".[longbench]"          # official LongBench v2 needs `datasets`
archolith-bench harness longbench-v2 --arms direct,proxy_only,proxy_plus_filter --subset single_document_qa --limit 50
```

In-process adapters drive each task via the chat client; external-cli adapters invoke the
official tool (per arm, direct vs proxy base URL) and parse its results. SWE-bench/CyberSecEval/
AgentDojo/MTEB are scaffolded — real runs (datasets, agent scaffolds, API budget) land at launch
step 3. **MTEB caveat:** it measures embeddings, which the chat proxy doesn't sit in front of, so
its proxy-arm delta is a no-op until an embeddings layer exists.

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

## Checkpoints

Resumable benchmark runs may create `.checkpoint_*.json` files in the working directory. They contain local run state only and are safe to delete after a run finishes or when intentionally starting fresh.

## License

Source-available under the [PolyForm Noncommercial License 1.0.0](LICENSE).
Free for non-commercial use; commercial use requires permission from the licensor.
Contributions are subject to the [CLA](CLA.md).

archolith&trade; is a trademark of Charles Harvey. Use of the name in
derivative works or competing products requires explicit permission.
