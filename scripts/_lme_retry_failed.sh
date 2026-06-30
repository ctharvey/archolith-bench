#!/usr/bin/env bash
# Re-enrich FAILED Episodic nodes in the existing menhir-lme-neo4j DB.
# Starts menhir-frontier on port 8102, resets all FAILED episodes, drains, stops menhir.
# The Neo4j container (menhir-lme-neo4j, bolt 7689) must already be running.
# The Neo4j is NOT stopped on exit — it holds the data for the subsequent A/B.
#
# Usage:
#   scripts/_lme_retry_failed.sh [--drain-timeout <seconds>]  # default 86400 (24h)
set -euo pipefail

BENCH_DIR="/c/Users/thron/IdeaProjects/projects/archolith/archolith-bench"
MENHIR_DIR="/c/Users/thron/IdeaProjects/projects/archolith/menhir-frontier"
MENHIR_PY="${MENHIR_DIR}/.venv/Scripts/python.exe"
MENHIR_BIN="${MENHIR_DIR}/.venv/Scripts/menhir"
BENCH_PY="${BENCH_DIR}/.venv/Scripts/python.exe"
NEO4J_NAME="menhir-lme-neo4j"; NEO4J_BOLT=7689; NEO4J_PW="lmedata123"
MENHIR_PORT=8102; MENHIR_URL="http://localhost:${MENHIR_PORT}"

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
docker ps --format '{{.Names}}' | grep -qx "${NEO4J_NAME}" \
  || die "${NEO4J_NAME} is not running — start it with: docker start ${NEO4J_NAME}"
[ -x "${MENHIR_PY}" ] || die "menhir-frontier venv python missing: ${MENHIR_PY}"
[ -e "${MENHIR_BIN}" ] || [ -e "${MENHIR_BIN}.exe" ] \
  || die "menhir console script missing — pip install -e ${MENHIR_DIR}"
[ -e "${BENCH_PY}" ] || die "archolith-bench venv python missing: ${BENCH_PY}"

OPENAI_KEY="$("${MENHIR_PY}" - "${MENHIR_DIR}/.env" OPENAI_API_KEY <<'PY'
import sys; from dotenv import dotenv_values; print(dotenv_values(sys.argv[1]).get(sys.argv[2],""))
PY
)"; [ -n "${OPENAI_KEY}" ] || die "OPENAI_API_KEY not found in ${MENHIR_DIR}/.env"
log "preflight OK. keys resolved."

# ---- menhir-frontier lifecycle (stops on exit; Neo4j stays up) --------------
MENHIR_PID=""
cleanup() {
  log "stopping menhir-frontier (Neo4j ${NEO4J_NAME} stays up)..."
  [ -n "${MENHIR_PID}" ] && kill "${MENHIR_PID}" 2>/dev/null || true
}
trap cleanup EXIT

# Blank env so menhir's default .env (local-llama / prod Neo4j) is NOT loaded.
EMPTY_ENV="$(mktemp)"; export ENV_FILE="${EMPTY_ENV}"

# Dedicated log dir (avoids WinError 32 RotatingFileHandler collisions).
export MENHIR_LOG_DIR="${BENCH_DIR}/results/lme-ingest/menhir-logs"; mkdir -p "${MENHIR_LOG_DIR}"

export MENHIR_BENCHMARK_MODE=1
export MENHIR_API_HOST=127.0.0.1
export MENHIR_API_PORT="${MENHIR_PORT}"
# Raise budget so episodes that need more extraction calls don't hit FAILED again.
export MENHIR_MAX_LLM_CALLS_PER_JOB=30
export OTEL_SDK_DISABLED=true
export LANGFUSE_TRACING_ENABLED=false
export LANGFUSE_PUBLIC_KEY="" LANGFUSE_SECRET_KEY="" LANGFUSE_HOST=""
export MENHIR_OPERATOR_KEY="" MENHIR_AGENT_KEY="" MENHIR_READONLY_KEY="" MENHIR_API_KEY=""
# Existing persistent Neo4j
export NEO4J_URI="bolt://localhost:${NEO4J_BOLT}"
export NEO4J_USER="neo4j"
export NEO4J_PASSWORD="${NEO4J_PW}"
export NEO4J_DATABASE="neo4j"
# OpenAI extraction + embedding (matches original build config)
export GRAPHITI_LLM_PROVIDER="openai"   MEMORY_GRAPHITI_PROVIDER="openai"
export LLM_CHAT_PROVIDER="openai"        MEMORY_CHAT_PROVIDER="openai"
export GRAPHITI_RERANKER_PROVIDER="openai" MEMORY_GRAPHITI_RERANKER_PROVIDER="openai"
export GRAPHITI_EMBED_PROVIDER="openai"  MEMORY_GRAPHITI_EMBED_PROVIDER="openai"
export OPENAI_API_KEY="${OPENAI_KEY}"
export OPENAI_CHAT_MODEL="gpt-4.1-nano"
export OPENAI_EMBED_MODEL="text-embedding-3-small"

log "starting menhir-frontier on ${MENHIR_URL} (pointing at ${NEO4J_NAME})..."
( cd "${MENHIR_DIR}" && "${MENHIR_BIN}" serve --port "${MENHIR_PORT}" ) & MENHIR_PID=$!

log "waiting for menhir-frontier /api/health..."
for _ in $(seq 1 90); do
  curl -sf "${MENHIR_URL}/api/health" >/dev/null 2>&1 && break
  sleep 2
done
curl -sf "${MENHIR_URL}/api/health" >/dev/null 2>&1 || die "menhir-frontier not healthy on ${MENHIR_PORT}"
log "menhir-frontier healthy. starting retry pass..."

# ---- retry ------------------------------------------------------------------
"${BENCH_PY}" "${BENCH_DIR}/scripts/_retry_failed_episodes.py" \
  --menhir-url "${MENHIR_URL}" \
  --drain-timeout "${DRAIN_TIMEOUT}"

log "retry pass complete."
