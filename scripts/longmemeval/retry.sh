#!/usr/bin/env bash
# Re-enrich FAILED Episodic nodes in the existing LME Neo4j DB.
# Starts menhir-frontier on LME_PORT_BUILD, resets all FAILED episodes, drains, stops menhir.
# The Neo4j container must already be running.
# The Neo4j is NOT stopped on exit — it holds the data for the subsequent A/B.
#
# Usage:
#   retry.sh [--drain-timeout <seconds>]  # default 86400 (24h)
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/config.sh"

MENHIR_PORT="${LME_PORT_BUILD}"
MENHIR_URL="http://localhost:${MENHIR_PORT}"

DRAIN_TIMEOUT=86400
for ((i=1; i<=$#; i++)); do
  case "${!i}" in
    --drain-timeout) n=$((i+1)); DRAIN_TIMEOUT="${!n}"; i=$n ;;
  esac
done

log() { printf '[retry] %s\n' "$*" >&2; }
die() { printf '[retry] ERROR: %s\n' "$*" >&2; exit 1; }

# ---- preflight --------------------------------------------------------------
command -v docker >/dev/null 2>&1 || die "docker not on PATH"
docker ps --format '{{.Names}}' | grep -qx "${LME_NEO4J_NAME}" \
  || die "${LME_NEO4J_NAME} is not running — start it with: docker start ${LME_NEO4J_NAME}"
[ -f "${MENHIR_FRONTIER_PY}" ] || die "menhir-frontier venv python missing: ${MENHIR_FRONTIER_PY}"
[ -f "${MENHIR_FRONTIER_BIN}" ] || [ -f "${MENHIR_FRONTIER_BIN}.exe" ] \
  || die "menhir console script missing — pip install -e ${MENHIR_FRONTIER}"
[ -f "${BENCH_PY}" ] || die "archolith-bench venv python missing: ${BENCH_PY}"

OPENAI_KEY="$("${MENHIR_FRONTIER_PY}" - "${MENHIR_FRONTIER}/.env" OPENAI_API_KEY <<'PY'
import sys; from dotenv import dotenv_values; print(dotenv_values(sys.argv[1]).get(sys.argv[2],""))
PY
)"; [ -n "${OPENAI_KEY}" ] || die "OPENAI_API_KEY not found in ${MENHIR_FRONTIER}/.env"
log "preflight OK. keys resolved."

# ---- menhir-frontier lifecycle (stops on exit; Neo4j stays up) --------------
MENHIR_PID=""
cleanup() {
  log "stopping menhir-frontier (Neo4j ${LME_NEO4J_NAME} stays up)..."
  [ -n "${MENHIR_PID}" ] && kill "${MENHIR_PID}" 2>/dev/null || true
}
trap cleanup EXIT

# Blank env so menhir's default .env (local-llama / prod Neo4j) is NOT loaded.
EMPTY_ENV="$(mktemp)"; export ENV_FILE="${EMPTY_ENV}"

# Dedicated log dir (avoids WinError 32 RotatingFileHandler collisions).
export MENHIR_LOG_DIR="${LME_RESULTS_DIR}/menhir-logs"; mkdir -p "${MENHIR_LOG_DIR}"

export MENHIR_BENCHMARK_MODE=1
export MENHIR_API_HOST=127.0.0.1
export MENHIR_API_PORT="${MENHIR_PORT}"
# Raise budget so episodes that need more extraction calls don't hit FAILED again.
export MENHIR_MAX_LLM_CALLS_PER_JOB=30
# Parallelize enrichment: N episodes extract at once, serialized per namespace (cloud
# provider, so the single-flight local-model lock does not apply). Override by exporting
# MENHIR_INGEST_CONCURRENCY before calling.
export MENHIR_INGEST_CONCURRENCY="${MENHIR_INGEST_CONCURRENCY:-8}"
export OTEL_SDK_DISABLED=true
export LANGFUSE_TRACING_ENABLED=false
export LANGFUSE_PUBLIC_KEY="" LANGFUSE_SECRET_KEY="" LANGFUSE_HOST=""
export MENHIR_OPERATOR_KEY="" MENHIR_AGENT_KEY="" MENHIR_READONLY_KEY="" MENHIR_API_KEY=""
# Existing persistent Neo4j
export NEO4J_URI="bolt://localhost:${LME_BOLT}"
export NEO4J_USER="neo4j"
export NEO4J_PASSWORD="${LME_NEO4J_PW}"
export NEO4J_DATABASE="neo4j"
export LME_NEO4J_CONTAINER="${LME_NEO4J_NAME}" LME_NEO4J_PW="${LME_NEO4J_PW}"
# OpenAI extraction + embedding (matches original build config)
export GRAPHITI_LLM_PROVIDER="openai"   MEMORY_GRAPHITI_PROVIDER="openai"
export LLM_CHAT_PROVIDER="openai"        MEMORY_CHAT_PROVIDER="openai"
export GRAPHITI_RERANKER_PROVIDER="openai" MEMORY_GRAPHITI_RERANKER_PROVIDER="openai"
export GRAPHITI_EMBED_PROVIDER="openai"  MEMORY_GRAPHITI_EMBED_PROVIDER="openai"
export OPENAI_API_KEY="${OPENAI_KEY}"
export OPENAI_CHAT_MODEL="${LME_EXTRACT_MODEL}"
export OPENAI_EMBED_MODEL="${LME_EMBED_MODEL}"

log "starting menhir-frontier on ${MENHIR_URL} (pointing at ${LME_NEO4J_NAME})..."
( cd "${MENHIR_FRONTIER}" && "${MENHIR_FRONTIER_BIN}" serve --port "${MENHIR_PORT}" ) & MENHIR_PID=$!

log "waiting for menhir-frontier /api/health..."
for _ in $(seq 1 90); do
  curl -sf "${MENHIR_URL}/api/health" >/dev/null 2>&1 && break
  sleep 2
done
curl -sf "${MENHIR_URL}/api/health" >/dev/null 2>&1 || die "menhir-frontier not healthy on ${MENHIR_PORT}"
log "menhir-frontier healthy. starting retry pass..."

# ---- retry ------------------------------------------------------------------
"${BENCH_PY}" "$(dirname "${BASH_SOURCE[0]}")/lib/retry.py" \
  --menhir-url "${MENHIR_URL}" \
  --drain-timeout "${DRAIN_TIMEOUT}"

log "retry pass complete."
