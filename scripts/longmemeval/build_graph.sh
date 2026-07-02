#!/usr/bin/env bash
# Throwaway: build a PERSISTENT menhir/Neo4j with LongMemEval haystacks pre-ingested under
# stable namespaces, so recall-only A/B (main vs frontier) can run without re-ingesting.
# Neo4j stays up after; only the temp menhir (used for ingestion) is stopped. Not committed.
# Usage: _lme_build_db.sh <limit>
set -euo pipefail
LIMIT="${1:-30}"

BENCH_DIR="/c/Users/thron/IdeaProjects/projects/archolith/archolith-bench"
MENHIR_DIR="/c/Users/thron/IdeaProjects/projects/archolith/menhir-frontier"
MENHIR_PY="${MENHIR_DIR}/.venv/Scripts/python.exe"
MENHIR_BIN="${MENHIR_DIR}/.venv/Scripts/menhir"
BENCH_PY="${BENCH_DIR}/.venv/Scripts/python.exe"
NEO4J_NAME="menhir-lme-neo4j"; NEO4J_BOLT=7689; NEO4J_HTTP=7476; NEO4J_PW="lmedata123"; NEO4J_VOL="menhir-lme-data"
MENHIR_PORT=8102; MENHIR_URL="http://localhost:${MENHIR_PORT}"
log(){ printf '[lme-build] %s\n' "$*" >&2; }
die(){ printf '[lme-build] ERROR: %s\n' "$*" >&2; exit 1; }

OPENAI_KEY="$("${MENHIR_PY}" - "${MENHIR_DIR}/.env" OPENAI_API_KEY <<'PY'
import sys; from dotenv import dotenv_values; print(dotenv_values(sys.argv[1]).get(sys.argv[2],""))
PY
)"; [ -n "${OPENAI_KEY}" ] || die "no OPENAI_API_KEY"

# ---- persistent Neo4j (reuse if already up) ----
if ! docker ps --format '{{.Names}}' | grep -qx "${NEO4J_NAME}"; then
  if docker ps -a --format '{{.Names}}' | grep -qx "${NEO4J_NAME}"; then
    log "starting existing ${NEO4J_NAME}..."; docker start "${NEO4J_NAME}" >/dev/null
  else
    log "creating persistent Neo4j ${NEO4J_NAME} (bolt ${NEO4J_BOLT})..."
    docker run -d --name "${NEO4J_NAME}" -p ${NEO4J_BOLT}:7687 -p ${NEO4J_HTTP}:7474 \
      -e NEO4J_AUTH=neo4j/${NEO4J_PW} -e NEO4J_server_memory_heap_max__size=2G \
      -v ${NEO4J_VOL}:/data neo4j:5.26-community >/dev/null
  fi
fi
log "waiting for Neo4j HTTP (${NEO4J_HTTP})..."
for _ in $(seq 1 60); do curl -sf "http://localhost:${NEO4J_HTTP}" >/dev/null 2>&1 && break; sleep 2; done
curl -sf "http://localhost:${NEO4J_HTTP}" >/dev/null 2>&1 || die "Neo4j not ready"

# ---- temp menhir for ingestion (stopped on exit; Neo4j persists) ----
MENHIR_PID=""
cleanup(){ log "stopping ingest menhir (Neo4j ${NEO4J_NAME} stays up)..."; [ -n "${MENHIR_PID}" ] && kill "${MENHIR_PID}" 2>/dev/null || true; }
trap cleanup EXIT

EMPTY_ENV="$(mktemp)"; export ENV_FILE="${EMPTY_ENV}"
# LongMemEval variant: default to 'oracle' (evidence-only haystacks, ~22 turns/item vs ~494
# for 's') so the full 500-item build is ~1 day instead of ~weeks. Override by exporting
# LONGMEMEVAL_VARIANT=s|m before calling.
export LONGMEMEVAL_VARIANT="${LONGMEMEVAL_VARIANT:-oracle}"
# Dedicated log dir so the ingest menhir's RotatingFileHandler never shares server.log with
# another menhir process (the cross-process WinError 32 on rollover is the log-noise source).
export MENHIR_LOG_DIR="${BENCH_DIR}/results/lme-ingest/menhir-logs"; mkdir -p "${MENHIR_LOG_DIR}"
export MENHIR_BENCHMARK_MODE=1 MENHIR_API_HOST=127.0.0.1 MENHIR_API_PORT="${MENHIR_PORT}"
# Raise the per-episode LLM extraction budget (default 10) so long turns finish enrichment
# instead of hitting FAILED; the ingest script does a best-effort FAILED-retry for the rest.
export MENHIR_MAX_LLM_CALLS_PER_JOB=20
export OTEL_SDK_DISABLED=true LANGFUSE_TRACING_ENABLED=false LANGFUSE_PUBLIC_KEY="" LANGFUSE_SECRET_KEY="" LANGFUSE_HOST=""
export MENHIR_OPERATOR_KEY="" MENHIR_AGENT_KEY="" MENHIR_READONLY_KEY="" MENHIR_API_KEY=""
export NEO4J_URI="bolt://localhost:${NEO4J_BOLT}" NEO4J_USER="neo4j" NEO4J_PASSWORD="${NEO4J_PW}" NEO4J_DATABASE="neo4j"
export GRAPHITI_LLM_PROVIDER="openai" MEMORY_GRAPHITI_PROVIDER="openai" LLM_CHAT_PROVIDER="openai" MEMORY_CHAT_PROVIDER="openai"
export GRAPHITI_RERANKER_PROVIDER="openai" MEMORY_GRAPHITI_RERANKER_PROVIDER="openai"
export GRAPHITI_EMBED_PROVIDER="openai" MEMORY_GRAPHITI_EMBED_PROVIDER="openai"
export OPENAI_API_KEY="${OPENAI_KEY}" OPENAI_CHAT_MODEL="gpt-4.1-nano" OPENAI_EMBED_MODEL="text-embedding-3-small"

log "starting ingest menhir on ${MENHIR_URL}..."
( cd "${MENHIR_DIR}" && "${MENHIR_BIN}" serve --port "${MENHIR_PORT}" ) & MENHIR_PID=$!
for _ in $(seq 1 90); do curl -sf "${MENHIR_URL}/api/health" >/dev/null 2>&1 && break; sleep 2; done
curl -sf "${MENHIR_URL}/api/health" >/dev/null 2>&1 || die "menhir not healthy"
log "menhir healthy. ingesting ${LIMIT} items..."

"${BENCH_PY}" "${BENCH_DIR}/scripts/_ingest_lme.py" --limit "${LIMIT}" --menhir-url "${MENHIR_URL}"
log "ingest complete. Neo4j ${NEO4J_NAME} (bolt ${NEO4J_BOLT}) holds the data; manifest in results/lme-ingest/."
