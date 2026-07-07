#!/usr/bin/env bash
# Build a PERSISTENT menhir/Neo4j with LongMemEval haystacks pre-ingested under
# stable namespaces, so recall-only A/B (main vs frontier) can run without re-ingesting.
# Neo4j stays up after; only the temp menhir (used for ingestion) is stopped.
# Usage: build_graph.sh [limit]
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/config.sh"

LIMIT="${1:-30}"
MENHIR_PORT="${LME_PORT_BUILD}"
MENHIR_URL="http://localhost:${MENHIR_PORT}"

log(){ printf '[lme-build] %s\n' "$*" >&2; }
die(){ printf '[lme-build] ERROR: %s\n' "$*" >&2; exit 1; }

OPENAI_KEY="$("${MENHIR_FRONTIER_PY}" - "${MENHIR_FRONTIER}/.env" OPENAI_API_KEY <<'PY'
import sys; from dotenv import dotenv_values; print(dotenv_values(sys.argv[1]).get(sys.argv[2],""))
PY
)"; [ -n "${OPENAI_KEY}" ] || die "no OPENAI_API_KEY"

# ---- persistent Neo4j (reuse if already up) ----
if ! docker ps --format '{{.Names}}' | grep -qx "${LME_NEO4J_NAME}"; then
  if docker ps -a --format '{{.Names}}' | grep -qx "${LME_NEO4J_NAME}"; then
    log "starting existing ${LME_NEO4J_NAME}..."; docker start "${LME_NEO4J_NAME}" >/dev/null
  else
    log "creating persistent Neo4j ${LME_NEO4J_NAME} (bolt ${LME_BOLT})..."
    docker run -d --name "${LME_NEO4J_NAME}" -p ${LME_BOLT}:7687 -p ${LME_HTTP}:7474 \
      -e NEO4J_AUTH=neo4j/${LME_NEO4J_PW} -e NEO4J_server_memory_heap_max__size=2G \
      -v ${LME_NEO4J_VOL}:/data ${LME_NEO4J_IMAGE} >/dev/null
  fi
fi
log "waiting for Neo4j HTTP (${LME_HTTP})..."
for _ in $(seq 1 60); do curl -sf "http://localhost:${LME_HTTP}" >/dev/null 2>&1 && break; sleep 2; done
curl -sf "http://localhost:${LME_HTTP}" >/dev/null 2>&1 || die "Neo4j not ready"

# ---- temp menhir for ingestion (stopped on exit; Neo4j persists) ----
MENHIR_PID=""
cleanup(){ log "stopping ingest menhir (Neo4j ${LME_NEO4J_NAME} stays up)..."; [ -n "${MENHIR_PID}" ] && kill "${MENHIR_PID}" 2>/dev/null || true; }
trap cleanup EXIT

EMPTY_ENV="$(mktemp)"; export ENV_FILE="${EMPTY_ENV}"
# LongMemEval variant: default to 'oracle' (evidence-only haystacks, ~22 turns/item vs ~494
# for 's') so the full 500-item build is ~1 day instead of ~weeks. Override by exporting
# LONGMEMEVAL_VARIANT=s|m before calling.
export LONGMEMEVAL_VARIANT="${LONGMEMEVAL_VARIANT:-oracle}"
export LME_NEO4J_CONTAINER="${LME_NEO4J_NAME}" LME_NEO4J_PW="${LME_NEO4J_PW}"
# Dedicated log dir so the ingest menhir's RotatingFileHandler never shares server.log with
# another menhir process (the cross-process WinError 32 on rollover is the log-noise source).
export MENHIR_LOG_DIR="${LME_RESULTS_DIR}/menhir-logs"; mkdir -p "${MENHIR_LOG_DIR}"
export MENHIR_BENCHMARK_MODE=1 MENHIR_API_HOST=127.0.0.1 MENHIR_API_PORT="${MENHIR_PORT}"
# Raise the per-episode LLM extraction budget (default 10) so long turns finish enrichment
# instead of hitting FAILED; the ingest script does a best-effort FAILED-retry for the rest.
export MENHIR_MAX_LLM_CALLS_PER_JOB=20
export OTEL_SDK_DISABLED=true LANGFUSE_TRACING_ENABLED=false LANGFUSE_PUBLIC_KEY="" LANGFUSE_SECRET_KEY="" LANGFUSE_HOST=""
export MENHIR_OPERATOR_KEY="" MENHIR_AGENT_KEY="" MENHIR_READONLY_KEY="" MENHIR_API_KEY=""
export NEO4J_URI="bolt://localhost:${LME_BOLT}" NEO4J_USER="neo4j" NEO4J_PASSWORD="${LME_NEO4J_PW}" NEO4J_DATABASE="neo4j"
export GRAPHITI_LLM_PROVIDER="openai" MEMORY_GRAPHITI_PROVIDER="openai" LLM_CHAT_PROVIDER="openai" MEMORY_CHAT_PROVIDER="openai"
export GRAPHITI_RERANKER_PROVIDER="openai" MEMORY_GRAPHITI_RERANKER_PROVIDER="openai"
export GRAPHITI_EMBED_PROVIDER="openai" MEMORY_GRAPHITI_EMBED_PROVIDER="openai"
export OPENAI_API_KEY="${OPENAI_KEY}" OPENAI_CHAT_MODEL="${LME_EXTRACT_MODEL}" OPENAI_EMBED_MODEL="${LME_EMBED_MODEL}"

log "starting ingest menhir on ${MENHIR_URL}..."
( cd "${MENHIR_FRONTIER}" && "${MENHIR_FRONTIER_BIN}" serve --port "${MENHIR_PORT}" ) & MENHIR_PID=$!
for _ in $(seq 1 90); do curl -sf "${MENHIR_URL}/api/health" >/dev/null 2>&1 && break; sleep 2; done
curl -sf "${MENHIR_URL}/api/health" >/dev/null 2>&1 || die "menhir not healthy"
log "menhir healthy. ingesting ${LIMIT} items..."

"${BENCH_PY}" "$(dirname "${BASH_SOURCE[0]}")/lib/ingest.py" --limit "${LIMIT}" --menhir-url "${MENHIR_URL}"
log "ingest complete. promoting SESSION -> PERSISTENT (regular memories)..."

# Write the benchmark as regular memories: freshly-extracted nodes are SESSION-scoped and
# would be invisible to build_context / plain recall (recall_service.py:937). See
# promote_persistent.sh for the full rationale.
"$(dirname "${BASH_SOURCE[0]}")/promote_persistent.sh"

log "build complete. Neo4j ${LME_NEO4J_NAME} (bolt ${LME_BOLT}) holds the data; manifest in results/lme-ingest/."
