#!/usr/bin/env bash
# Throwaway: run LongMemEval Mode B against MAIN or FRONTIER menhir, same current harness,
# gpt-4o-mini answer model, default memory arms (no_memory, menhir_recall). For a frontier-vs-
# main A/B. Not committed. Usage: _run_lme_variant.sh <main|frontier> <limit>
set -euo pipefail
VARIANT="${1:?variant: main|frontier}"
LIMIT="${2:-30}"

BENCH_DIR="/c/Users/thron/IdeaProjects/projects/archolith/archolith-bench"
MENHIR_DIR="/c/Users/thron/IdeaProjects/projects/archolith/menhir"
FRONTIER_DIR="/c/Users/thron/IdeaProjects/projects/archolith/menhir-frontier"
DELEGATE_ENV="/c/Users/thron/IdeaProjects/projects/ctharvey/cth.mcp.delegate/.env"
MENHIR_PY="${MENHIR_DIR}/.venv/Scripts/python.exe"
MENHIR_BIN="${MENHIR_DIR}/.venv/Scripts/menhir"
BENCH_BIN="${BENCH_DIR}/.venv/Scripts/archolith-bench"
COMPOSE_FILE="${MENHIR_DIR}/docker-compose.benchmark.yml"
NEO4J_HTTP_PORT=7475; NEO4J_BOLT_PORT=7688; NEO4J_PASSWORD="benchthrowaway"
MENHIR_PORT=8101; MENHIR_URL="http://localhost:${MENHIR_PORT}"
OPENAI_ANSWER_MODEL="gpt-4o-mini"; OPENAI_EXTRACTION_MODEL="gpt-4.1-nano"; OPENAI_EMBED_MODEL="text-embedding-3-small"
log() { printf '[lme-%s] %s\n' "${VARIANT}" "$*" >&2; }
die() { printf '[lme-%s] ERROR: %s\n' "${VARIANT}" "$*" >&2; exit 1; }
rdval() { "${MENHIR_PY}" - "$1" "$2" <<'PY'
import sys; from dotenv import dotenv_values; print(dotenv_values(sys.argv[1]).get(sys.argv[2],""))
PY
}

[ "${VARIANT}" = "main" ] || [ "${VARIANT}" = "frontier" ] || die "variant must be main|frontier"
OPENAI_KEY="$(rdval "${BENCH_DIR}/.env" OPENAI_API_KEY)"; [ -n "${OPENAI_KEY}" ] || die "no OPENAI_API_KEY in ${BENCH_DIR}/.env"
RUN_OUTPUT_DIR="${BENCH_DIR}/results/lme-${VARIANT}"; mkdir -p "${RUN_OUTPUT_DIR}"

MENHIR_PID=""
cleanup(){ log teardown; [ -n "${MENHIR_PID}" ] && kill "${MENHIR_PID}" 2>/dev/null || true; docker compose -f "${COMPOSE_FILE}" down -v 2>/dev/null || true; }
trap cleanup EXIT

log "throwaway Neo4j up..."; docker compose -f "${COMPOSE_FILE}" up -d
for _ in $(seq 1 60); do curl -sf "http://localhost:${NEO4J_HTTP_PORT}" >/dev/null 2>&1 && break; sleep 2; done
curl -sf "http://localhost:${NEO4J_HTTP_PORT}" >/dev/null 2>&1 || die "Neo4j not ready"

EMPTY_ENV="$(mktemp)"; export ENV_FILE="${EMPTY_ENV}"
# Dedicated per-variant log dir so menhir's RotatingFileHandler never shares server.log with
# another menhir process (the cross-process WinError 32 on rollover is the log-noise source).
export MENHIR_LOG_DIR="${RUN_OUTPUT_DIR}/menhir-logs"; mkdir -p "${MENHIR_LOG_DIR}"
export MENHIR_BENCHMARK_MODE=1 MENHIR_API_HOST=127.0.0.1 MENHIR_API_PORT="${MENHIR_PORT}"
export OTEL_SDK_DISABLED=true LANGFUSE_TRACING_ENABLED=false LANGFUSE_PUBLIC_KEY="" LANGFUSE_SECRET_KEY="" LANGFUSE_HOST=""
export MENHIR_OPERATOR_KEY="" MENHIR_AGENT_KEY="" MENHIR_READONLY_KEY="" MENHIR_API_KEY=""
export NEO4J_URI="bolt://localhost:${NEO4J_BOLT_PORT}" NEO4J_USER="neo4j" NEO4J_PASSWORD="${NEO4J_PASSWORD}" NEO4J_DATABASE="neo4j"
# extraction + embedding = openai (matches the 0.367 ext-openai config)
export GRAPHITI_LLM_PROVIDER="openai" MEMORY_GRAPHITI_PROVIDER="openai" LLM_CHAT_PROVIDER="openai" MEMORY_CHAT_PROVIDER="openai"
export GRAPHITI_RERANKER_PROVIDER="openai" MEMORY_GRAPHITI_RERANKER_PROVIDER="openai"
export GRAPHITI_EMBED_PROVIDER="openai" MEMORY_GRAPHITI_EMBED_PROVIDER="openai"
export OPENAI_API_KEY="${OPENAI_KEY}" OPENAI_CHAT_MODEL="${OPENAI_EXTRACTION_MODEL}" OPENAI_EMBED_MODEL="${OPENAI_EMBED_MODEL}"

SERVE_CWD="${MENHIR_DIR}"
if [ "${VARIANT}" = "frontier" ]; then
  export PYTHONPATH="${FRONTIER_DIR}/src"   # load frontier source over the editable main install
  SERVE_CWD="${FRONTIER_DIR}"
  log "frontier source via PYTHONPATH=${PYTHONPATH}"
fi

log "menhir serve (${VARIANT}) on ${MENHIR_URL}..."
( cd "${SERVE_CWD}" && "${MENHIR_BIN}" serve --port "${MENHIR_PORT}" ) & MENHIR_PID=$!
for _ in $(seq 1 90); do curl -sf "${MENHIR_URL}/api/health" >/dev/null 2>&1 && break; sleep 2; done
curl -sf "${MENHIR_URL}/api/health" >/dev/null 2>&1 || die "menhir not healthy"
log "menhir healthy. confirming loaded source..."
curl -s "${MENHIR_URL}/api/health" >/dev/null 2>&1 || true

# answer model = gpt-4o-mini via OpenAI (the bench send_chat upstream)
export UPSTREAM_BASE_URL="https://api.openai.com/v1" UPSTREAM_API_KEY="${OPENAI_KEY}" BENCHMARK_MODEL="${OPENAI_ANSWER_MODEL}"
cmd=( "${BENCH_BIN}" harness longmemeval-menhir --menhir-url "${MENHIR_URL}" --confirm-menhir-reset
      --model "${OPENAI_ANSWER_MODEL}" --format markdown --output-dir "${RUN_OUTPUT_DIR}"
      --out "${RUN_OUTPUT_DIR}/harness_longmemeval_modeb.md" --limit "${LIMIT}" --resume )
log "running: ${cmd[*]}"
( cd "${BENCH_DIR}" && "${cmd[@]}" )
log "done -> ${RUN_OUTPUT_DIR}/harness_longmemeval_modeb.md"
