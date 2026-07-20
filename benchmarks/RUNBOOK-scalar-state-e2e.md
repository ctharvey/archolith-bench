# Runbook: ScalarStateView (Piece C) e2e (throwaway menhir, scheduler ON)

How to run the `menhir-scalar-state` harness against a **throwaway** menhir + real LLM. This exercises
Menhir's REAL typed-scalar path end to end: `/api/memory` ingest -> background consolidation scheduler
(`enable_scalar_state=True`) -> `TypedScalarPerceptionService` -> `:TypedAssertion` log -> materialized
`scalar_state` Views, verified over bolt. Successor to the CLOSED lexical sidecar line
(`scripts/longmemeval/analysis/TYPED-VALUE-ARM.md`).

## Why this differs from the phase3 runbook

The numeric-counter phase3 benchmark triggers consolidation explicitly over HTTP (`POST /api/phase3/run`)
and runs menhir with the scheduler OFF. Typed-scalar perception runs ONLY inside the SCHEDULED
consolidation job gated by `MENHIR_PERSONAL_MEMORY_SCALAR_STATE_ENABLED=1` -- the HTTP route does NOT
enable it. So this harness needs the **background scheduler ON** (benchmark mode OFF) with a short
consolidation interval; it ingests episodes, waits for a tick to materialize the Views, then verifies.

## Safety rules (non-negotiable)

- **Never touch the real menhir on `:8090`** or the real (prod) menhir Neo4j on **bolt `:7687`**. Use a
  throwaway only. The harness `ScalarBoltReader` refuses any bolt URI on port 7687 or the known prod host.
- Throwaway Neo4j = `docker-compose.benchmark.yml` in the **menhir** repo (bolt 7688, isolated volume).
- Activation is fresh-only: `activate_scalar_state()` refuses a store with legacy/unstamped nodes. Use a
  clean throwaway DB (bring the volume up fresh, or a fresh namespace on a clean store).
- The throwaway env holds an `OPENAI_API_KEY` -- write it under a temp dir and delete it at teardown.

## 1. Bring up the throwaway Neo4j (menhir repo)

```bash
cd <menhir>
docker compose -f docker-compose.benchmark.yml up -d       # neo4j on bolt 7688, browser 7475
```

## 2. Write a throwaway env file (temp; holds the OpenAI key)

```bash
ENVF="$TEMP/menhir-scalar-8098.env"        # a temp path, NOT the repo
cat > "$ENVF" <<EOF
NEO4J_URI=bolt://localhost:7688
NEO4J_USER=neo4j
NEO4J_PASSWORD=benchthrowaway
NEO4J_DATABASE=neo4j
MENHIR_API_HOST=127.0.0.1
MENHIR_API_PORT=8098
MENHIR_PERSONAL_MEMORY_CHAT_MODEL=gpt-4o-mini
# scheduler MUST be on (benchmark mode disables it) and the scalar flag MUST be on
MENHIR_BENCHMARK_MODE=0
MENHIR_PERSONAL_MEMORY_CONSOLIDATION_ENABLED=1
MENHIR_PERSONAL_MEMORY_SCALAR_STATE_ENABLED=1
MENHIR_PERSONAL_MEMORY_SCALAR_STATE_PERCEIVER_VERSION=v1
# short interval so a tick lands within the harness wait window
MENHIR_PERSONAL_MEMORY_CONSOLIDATION_INTERVAL_S=5
EOF
grep '^OPENAI_API_KEY=' <menhir>/.env >> "$ENVF"    # reuse the dev key
```

Auth: menhir disables bearer auth when no `MENHIR_*_KEY` is set. If your shell exports `MENHIR_AGENT_KEY`
it leaks into both server and client and they match automatically -- either is fine, just be consistent.
A local Qwen (`loopback:8080`) works in place of `gpt-4o-mini` via the OpenAI-compatible chat model env.

## 3. Start the throwaway menhir on :8098 (menhir repo)

```bash
cd <menhir>
ENV_FILE="$ENVF" NEO4J_URI=bolt://localhost:7688 NEO4J_USER=neo4j NEO4J_PASSWORD=benchthrowaway \
  MENHIR_API_PORT=8098 MENHIR_BENCHMARK_MODE=0 \
  MENHIR_PERSONAL_MEMORY_CONSOLIDATION_ENABLED=1 MENHIR_PERSONAL_MEMORY_SCALAR_STATE_ENABLED=1 \
  MENHIR_PERSONAL_MEMORY_CONSOLIDATION_INTERVAL_S=5 \
  .venv/Scripts/python.exe -m menhir.cli serve --port 8098 --host 127.0.0.1
# wait for GET http://127.0.0.1:8098/api/health -> {"status":"ok", ... "startup_mode":"full"}
# the log should NOT say "MENHIR_BENCHMARK_MODE=1 -- scheduler ... disabled"
```

## 4. Install the bolt extra + run the harness (archolith-bench repo)

```bash
cd <archolith-bench>
.venv/Scripts/python.exe -m pip install -e .[menhir-scalar]   # neo4j driver for the bolt read path

.venv/Scripts/python.exe -m archolith_bench.cli harness menhir-scalar-state \
    --menhir-url http://127.0.0.1:8098 \
    --neo4j-uri bolt://localhost:7688 --neo4j-password benchthrowaway \
    --scalar-max-wait-s 120 \
    --confirm-menhir-reset \
    --format markdown --out results/menhir_scalar_state_e2e.md
```

The harness ingests the known typed-scalar fixtures (one per ValueKind + an advisory + a non-scalar
control), waits up to `--scalar-max-wait-s` for the scheduler to materialize Views, then verifies the
INVARIANTS over bolt and writes evidence. Exit code is non-zero on FAIL.

Offline smoke of the harness itself (no menhir/Neo4j/LLM):

```bash
.venv/Scripts/python.exe -m archolith_bench.cli harness menhir-scalar-state --offline-fixture x
```

## 5. What "good" looks like

- Verdict PASS: >=1 current `scalar_state` View in the seeded namespace; zero duplicate current View
  keys; zero duplicate (subject, slot) pairs; every assertion `evidence_tier='agent'`; zero wrong-
  namespace Views; zero default-silo leak.
- Per-case: `view` fixtures MATCH their (kind, value) slot; the advisory case stays advisory/abstain
  (no concrete View); the non-scalar control produces nothing. Perception is stochastic, so a single
  `view` MISS is reported, not a hard failure -- the verdict gates on the structural invariants.

## 6. Teardown (always)

```bash
# stop the :8098 server (Ctrl-C, or kill the PID holding the port)
cd <menhir> && docker compose -f docker-compose.benchmark.yml down -v   # removes the throwaway volume
rm -f "$ENVF"                                                            # delete the key-bearing env file
# verify: :8098 down, real :8090 + prod bolt :7687 untouched
```
