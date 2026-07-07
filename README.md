# archolith-bench

Benchmark suite for the [archolith&trade;](https://github.com/archolith/archolith-bench) family.
Measures proxy context assembly, client-side filtering, MCP audit savings, security benchmark
coverage, and Menhir memory/retrieval behavior across reproducible scenarios.

### Evidence status

No launch headline numbers are currently active. Historical and fixture runs remain in
[`benchmarks/`](benchmarks/) and generated reports for methodology review, but they should not be
used as public copy until refreshed against the current launch configuration and recorded in
[`HEADLINE-NUMBERS.md`](HEADLINE-NUMBERS.md).

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
| `extraction-bench` | Compare extraction models on the real backend pipeline (speed/quality/cache-aware cost) |
| `dashboard` | Live view of in-progress memory runs (terminal or `--serve` web); reads run checkpoints |
| `ports` | Index running stack processes by label + port (find stray menhir/neo4j/dashboard instances) |

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

## Extraction model selection

Graph-memory extraction is a multi-call structured-JSON pipeline per episode, so the choice
of extraction model is a real speed / cost / quality decision. `archolith-bench
extraction-bench` replays that real pipeline against any OpenAI-compatible model and reports
latency, quality, and **cache-aware** cost. Full writeup, pricing, and findings:
**[EXTRACTION_MODELS.md](EXTRACTION_MODELS.md)**.

**TL;DR:** quality is a tie among capable small models, so optimize speed + cost.

| model | provider | call p50 | ent/fact recall | cache hit | $/1k ep |
|-------|----------|---------:|----------------:|----------:|--------:|
| gpt-oss-120b | Cerebras (wafer) | 0.30 s | 1.00 / **0.40** | 56% | $0.77 |
| llama-3.3-70b | Groq (LPU) | 0.35 s | 1.00 / 0.80 | – | $0.53 |
| **gpt-4.1-nano** | OpenAI | 0.54 s | 0.90 / 0.80 | 0% | **$0.10** |
| **gemini-3.1-flash-lite** | Google | 0.63 s | 1.00 / **0.90** | 0% | $0.20 |
| **deepseek-v4-flash** | DeepSeek | 1.19 s | 1.00 / 0.80 | 74% | **$0.05** |
| local qwen ~9B | LM Studio | 4.56 s | 1.00 / 0.80 | – | $0 |

- **Best value:** `gpt-4.1-nano` (~$0.10/1k). **Best quality:** `gemini-3.1-flash-lite` (best fact recall, but ~2× cost).
- **Best open-weight:** `qwen3-next-80b` via OpenRouter (0.85 fact recall, 100% JSON, $0.22/1k — gemini-3.1 tier, no Google).
- **Cheapest:** `deepseek-v4-flash` — caching makes it cheapest (50× cache discount).
- **Fastest:** Cerebras `gpt-oss-120b` (0.30 s) — but only 0.40 fact recall, so *not* recommended for graph memory. **Free/private:** local Qwen (slower, $0).

By default the bench runs only the two **blessed keepers** — `gpt-4.1-nano` (default) and
`qwen3-next-80b` (open-weight alternative, via OpenRouter). Pass `--all` for the full
candidate sweep.

```bash
# keys read from env or menhir/.env; fast providers auto-enable when their key is present
archolith-bench extraction-bench --repeats 2            # just nano + qwen3-next-80b
archolith-bench extraction-bench --repeats 2 --all      # full candidate sweep
archolith-bench extraction-bench --repeats 2 --all --exclude gpt-5   # sweep minus slow reasoning models
```

## Quick Start

```bash
# Base CLI install
pip install -e .

# List available scenarios (no live proxy needed)
archolith-bench proxy --list
```

Install optional suite dependencies when you need filter or audit runs. The launch-supported
source checkout workflow is to install the sibling repos editable first, then install the
bench extras:

```bash
python -m pip install -e ../archolith-filter
python -m pip install -e ../archolith-mcp-audit
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

The base install supports the CLI, report generation, and proxy orchestration. Until
`archolith-filter` and the `archolith-audit` distribution are published to the package index used by
your environment, `pip install -e ".[all]"` is not a standalone public install command; use the
source checkout workflow above or install those packages from their eventual release artifacts first.
The audit source repo is `../archolith-mcp-audit`; its Python import package is `archolith_mcp_audit`.

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
