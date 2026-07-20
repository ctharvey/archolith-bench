#!/usr/bin/env bash
# End-to-end run of the menhir-scalar-state benchmark against a THROWAWAY menhir with the
# typed-scalar consolidation scheduler ON. Brings up a FRESH ephemeral Neo4j (activation is
# fresh-only), starts menhir serve with the scalar flag + background scheduler, runs the
# harness, and tears everything down. Reuses the LongMemEval config.sh conventions.
#
# Usage: run_scalar_state_e2e.sh [--keep] [-- <extra archolith-bench harness args>]
#   --keep   leave the menhir server + Neo4j container up after the run (debugging)
#
# Differs from build_graph.sh in one load-bearing way: MENHIR_BENCHMARK_MODE=0 so the
# background scheduler runs (benchmark mode disables it); typed-scalar perception ONLY runs
# inside the scheduled consolidation job, never over the HTTP phase3 route.
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/longmemeval/config.sh"

# ---- scalar-state throwaway knobs (all overridable) ----
SS_NEO4J_NAME="${SS_NEO4J_NAME:-menhir-scalar-neo4j}"
SS_BOLT="${SS_BOLT:-7691}"                 # host bolt port for the throwaway (maps to container 7687)
SS_HTTP="${SS_HTTP:-7477}"                 # host browser/http port (maps to container 7474)
SS_NEO4J_PW="${SS_NEO4J_PW:-scalarthrowaway}"
SS_NEO4J_IMAGE="${SS_NEO4J_IMAGE:-${LME_NEO4J_IMAGE}}"
SS_PORT="${SS_PORT:-8098}"                 # menhir serve port
SS_INTERVAL_S="${SS_INTERVAL_S:-5}"        # consolidation tick interval (short so a tick lands fast)
SS_PERCEIVER_VERSION="${SS_PERCEIVER_VERSION:-v1}"
SS_CHAT_MODEL="${SS_CHAT_MODEL:-${LME_EXTRACT_MODEL}}"   # gpt-4o-mini by default
SS_MAX_WAIT_S="${SS_MAX_WAIT_S:-120}"
SS_OUT="${SS_OUT:-${BENCH_DIR}/results/menhir_scalar_state_e2e.md}"
SS_FORMAT="${SS_FORMAT:-markdown}"

KEEP="false"
EXTRA_ARGS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --keep) KEEP="true"; shift ;;
    --) shift; EXTRA_ARGS=("$@"); break ;;
    *) EXTRA_ARGS+=("$1"); shift ;;
  esac
done

MENHIR_URL="http://127.0.0.1:${SS_PORT}"
BOLT_URI="bolt://localhost:${SS_BOLT}"

log(){ printf '[scalar-e2e] %s\n' "$*" >&2; }
die(){ printf '[scalar-e2e] ERROR: %s\n' "$*" >&2; exit 1; }

# ---- ensure the bolt read extra is installed (neo4j driver) ----
"${BENCH_PY}" -c "import neo4j" 2>/dev/null || {
  log "installing bolt read extra (.[menhir-scalar]) into the bench venv..."
  "${BENCH_PY}" -m pip install -e "${BENCH_DIR}[menhir-scalar]" >/dev/null
}

OPENAI_KEY="$("${MENHIR_MAIN_PY}" - "${MENHIR_MAIN}/.env" OPENAI_API_KEY <<'PY'
import sys; from dotenv import dotenv_values; print(dotenv_values(sys.argv[1]).get(sys.argv[2],""))
PY
)"; [ -n "${OPENAI_KEY}" ] || die "no OPENAI_API_KEY in ${MENHIR_MAIN}/.env"

MENHIR_PID=""
cleanup(){
  if [ "${KEEP}" = "true" ]; then
    log "--keep set: leaving menhir (:${SS_PORT}) and Neo4j ${SS_NEO4J_NAME} (bolt ${SS_BOLT}) UP."
    return
  fi
  log "tearing down..."
  [ -n "${MENHIR_PID}" ] && kill "${MENHIR_PID}" 2>/dev/null || true
  docker rm -f "${SS_NEO4J_NAME}" >/dev/null 2>&1 || true   # ephemeral: no named volume, fully fresh
}
trap cleanup EXIT

# ---- FRESH ephemeral Neo4j (no named volume -> clean store every run; activation is fresh-only) ----
docker rm -f "${SS_NEO4J_NAME}" >/dev/null 2>&1 || true
log "creating FRESH throwaway Neo4j ${SS_NEO4J_NAME} (bolt ${SS_BOLT})..."
docker run -d --name "${SS_NEO4J_NAME}" -p ${SS_BOLT}:7687 -p ${SS_HTTP}:7474 \
  -e NEO4J_AUTH=neo4j/${SS_NEO4J_PW} -e NEO4J_server_memory_heap_max__size=2G \
  ${SS_NEO4J_IMAGE} >/dev/null
log "waiting for Neo4j HTTP (${SS_HTTP})..."
for _ in $(seq 1 60); do curl -sf "http://localhost:${SS_HTTP}" >/dev/null 2>&1 && break; sleep 2; done
curl -sf "http://localhost:${SS_HTTP}" >/dev/null 2>&1 || die "Neo4j not ready"

# ---- throwaway menhir: scheduler ON (benchmark mode OFF) + scalar flag ON ----
EMPTY_ENV="$(mktemp)"; export ENV_FILE="${EMPTY_ENV}"
export MENHIR_LOG_DIR="${LME_RESULTS_DIR}/scalar-e2e-logs"; mkdir -p "${MENHIR_LOG_DIR}"
export MENHIR_API_HOST=127.0.0.1 MENHIR_API_PORT="${SS_PORT}"
# THE difference from build_graph.sh: scheduler must run, and the scalar path must be enabled.
export MENHIR_BENCHMARK_MODE=0
export MENHIR_PERSONAL_MEMORY_CONSOLIDATION_ENABLED=1
export MENHIR_PERSONAL_MEMORY_SCALAR_STATE_ENABLED=1
export MENHIR_PERSONAL_MEMORY_SCALAR_STATE_PERCEIVER_VERSION="${SS_PERCEIVER_VERSION}"
export MENHIR_PERSONAL_MEMORY_CONSOLIDATION_INTERVAL_S="${SS_INTERVAL_S}"
export MENHIR_MAX_LLM_CALLS_PER_JOB=20
export OTEL_SDK_DISABLED=true LANGFUSE_TRACING_ENABLED=false LANGFUSE_PUBLIC_KEY="" LANGFUSE_SECRET_KEY="" LANGFUSE_HOST=""
export MENHIR_OPERATOR_KEY="" MENHIR_AGENT_KEY="" MENHIR_READONLY_KEY="" MENHIR_API_KEY=""
export NEO4J_URI="${BOLT_URI}" NEO4J_USER="neo4j" NEO4J_PASSWORD="${SS_NEO4J_PW}" NEO4J_DATABASE="neo4j"
export GRAPHITI_LLM_PROVIDER="openai" MEMORY_GRAPHITI_PROVIDER="openai" LLM_CHAT_PROVIDER="openai" MEMORY_CHAT_PROVIDER="openai"
export GRAPHITI_RERANKER_PROVIDER="openai" MEMORY_GRAPHITI_RERANKER_PROVIDER="openai"
export GRAPHITI_EMBED_PROVIDER="openai" MEMORY_GRAPHITI_EMBED_PROVIDER="openai"
export MENHIR_PERSONAL_MEMORY_CHAT_MODEL="${SS_CHAT_MODEL}"
export OPENAI_API_KEY="${OPENAI_KEY}" OPENAI_CHAT_MODEL="${SS_CHAT_MODEL}" OPENAI_EMBED_MODEL="${LME_EMBED_MODEL}"

log "starting throwaway menhir on ${MENHIR_URL} (scheduler ON, scalar flag ON, interval ${SS_INTERVAL_S}s)..."
( cd "${MENHIR_MAIN}" && "${MENHIR_MAIN_BIN}" serve --port "${SS_PORT}" --host 127.0.0.1 ) & MENHIR_PID=$!
for _ in $(seq 1 90); do curl -sf "${MENHIR_URL}/api/health" >/dev/null 2>&1 && break; sleep 2; done
curl -sf "${MENHIR_URL}/api/health" >/dev/null 2>&1 || die "menhir not healthy"
log "menhir healthy. running the scalar-state harness..."

# ---- run the harness ----
"${BENCH_PY}" -m archolith_bench.cli harness menhir-scalar-state \
  --menhir-url "${MENHIR_URL}" \
  --neo4j-uri "${BOLT_URI}" --neo4j-password "${SS_NEO4J_PW}" \
  --scalar-max-wait-s "${SS_MAX_WAIT_S}" \
  --confirm-menhir-reset \
  --format "${SS_FORMAT}" --out "${SS_OUT}" \
  "${EXTRA_ARGS[@]}"
RC=$?

log "done (harness rc=${RC}). evidence: ${SS_OUT}"
exit ${RC}
