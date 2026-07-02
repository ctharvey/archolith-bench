# LongMemEval Mode B (menhir persistent memory) — runbook

Launch/marketing benchmark: answer LongMemEval questions from menhir's persistent
graph memory (ingest sessions as episodes, then recall) instead of in-context haystack.

Driver: `scripts/run_longmemeval_modeb.sh` (orchestrates everything below).

## Config (decided)

| Role | Value |
|------|-------|
| Answer model | `deepseek-v4-flash` (bench `send_chat` → `UPSTREAM_BASE_URL`) |
| menhir extraction (Graphiti LLM) | `deepseek-v4-flash`, OpenAI-compatible "local" kind, base `https://api.deepseek.com/v1` |
| menhir embedding | `text-embedding-3-small` (OpenAI, 1536-dim — matches prod) |

Secrets are read at runtime, never committed:
- DeepSeek key ← `cth.mcp.delegate/.env:DELEGATE_API_KEY`
- OpenAI key ← `menhir/.env:OPENAI_API_KEY`

## Why no code change was needed for `MENHIR_BENCHMARK_MODE`

The enrichment worker is an **in-process asyncio task** (`_ensure_enrichment_worker`),
not scheduler-managed. The only scheduler dependency in the enrichment path is
`acquire_llama_url_async`, which fires **only** for local-llama base URLs (`:8081`)
per `should_use_scheduler()` (`infrastructure/llama_endpoint.py`). With **cloud**
provider base URLs (deepseek/openai), `should_use_scheduler()` is `False`, so
`POST /api/memory?wait=true` enriches **inline**. `MENHIR_BENCHMARK_MODE=1` therefore
disables only the maintenance scheduler + orphan recovery (no store mutation
mid-measurement) and does **not** block ingestion.

The earlier "episode stuck queued" symptom was a config artifact of pointing the
throwaway at the default local-llama provider — not a bug. Fix is configuration
(cloud providers), which the launch script wires.

## Isolation / safety

- Throwaway Neo4j only: `menhir/docker-compose.benchmark.yml` (bolt `7688`, http
  `7475`, volume `menhir_bench_neo4j_data`, creds `neo4j/benchthrowaway`).
- menhir runs on `8101` (prod is `8100`); auth disabled (empty keys → middleware
  pass-through).
- Bench enforces `assert_not_production(--menhir-url)` independently.
- Never point any of this at prod Neo4j (`bolt://192.168.86.33:7687`).

## One-time setup

```sh
# bench venv + editable install with the LongMemEval (HuggingFace datasets) extra
python -m venv /c/Users/thron/IdeaProjects/projects/archolith/archolith-bench/.venv
/c/Users/thron/IdeaProjects/projects/archolith/archolith-bench/.venv/Scripts/python.exe \
  -m pip install -e "/c/Users/thron/IdeaProjects/projects/archolith/archolith-bench[longmemeval]"
```

menhir is expected already installed in `menhir/.venv` (console script `menhir`).

## Run

```sh
# 1. Start Docker Desktop / WSL (the daemon must be up).

# 2. Preflight (no side effects): checks daemon, venvs, keys.
scripts/run_longmemeval_modeb.sh --check

# 3. Real run (start small, then scale up).
scripts/run_longmemeval_modeb.sh --limit 20
scripts/run_longmemeval_modeb.sh --subset single-session-user --limit 10
```

Evidence is written to `results/harness_longmemeval_modeb.md`. The script tears
down menhir + the throwaway Neo4j (`down -v`) on exit.

## Offline plumbing smoke (no Docker, no menhir, no network)

Validates the A/B → score → evidence pipeline only (stub menhir client):

```sh
archolith-bench harness longmemeval-menhir \
  --offline-fixture fixtures/longmemeval_sample.json --format markdown
```

## Status

Every value in the script is verified against the code, but the full sequence had
**not** been executed end-to-end at authoring time (Docker daemon was down). Treat
the first real run as a shakeout: watch the menhir `/api/health` wait and the first
few `POST /api/memory?wait=true` round-trips for inline-enrichment latency.
