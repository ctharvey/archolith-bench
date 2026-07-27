#!/usr/bin/env bash
# Build a FRESH graph with ONLY the 78 knowledge-update items from LongMemEval (oracle variant),
# then run recall+QA scoring against them. Tests whether gpt-4o-mini + temp=0 + dedup hardening
# is a general improvement for knowledge-update handling, not just Rachel-specific.
#
# Uses the fixed menhir/main (temp=0, dedup identity gate, edge-consistency invariant, gpt-4o-mini).
#
# Usage:
#   ./scripts/longmemeval/run_knowledge_update_buildout.sh
#   LME_KU_RUN_ID=ku-v2 ./scripts/longmemeval/run_knowledge_update_buildout.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BENCH_DIR="$(git -C "${SCRIPT_DIR}" rev-parse --show-toplevel)"
ARCH_DIR="${BENCH_DIR%/*}"
RUN_ID="${LME_KU_RUN_ID:-ku-fix-20260716}"

log(){ printf '[lme-ku-buildout] %s %s\n' "$(date '+%F %H:%M:%S')" "$*" >&2; }
die(){ printf '[lme-ku-buildout] ERROR: %s\n' "$*" >&2; exit 1; }

[[ "${RUN_ID}" =~ ^[A-Za-z0-9._-]+$ ]] || die "RUN_ID contains unsafe characters"

export BENCH_DIR ARCH_DIR
export MENHIR_MAIN="${MENHIR_MAIN:-${ARCH_DIR}/menhir}"
export MENHIR_FRONTIER="${MENHIR_FRONTIER:-${MENHIR_MAIN}}"

# Fixture: pre-exported 78 knowledge-update items (oracle variant)
FIXTURE_PATH="${BENCH_DIR}/fixtures/longmemeval/knowledge_update_subset.json"
[ -f "${FIXTURE_PATH}" ] || die "fixture not found: ${FIXTURE_PATH}"
export LME_FIXTURE_PATH="${FIXTURE_PATH}"

# Container/volume/ports — isolated from the persistent graph
export LME_NEO4J_NAME="menhir-lme-${RUN_ID}"
export LME_NEO4J_VOL="menhir-lme-data-${RUN_ID}"
export LME_BOLT="${LME_BOLT:-7694}"
export LME_HTTP="${LME_HTTP:-7481}"
export LME_PORT_BUILD="${LME_PORT_BUILD:-8124}"
export LME_RESULTS_DIR="${BENCH_DIR}/results/lme-ku-buildout/${RUN_ID}"
export LME_MANIFEST_PATH="${LME_RESULTS_DIR}/manifest.json"
export LME_REVERT_SNAPSHOT_PATH="${LME_RESULTS_DIR}/date-backfill-revert.json"
export LONGMEMEVAL_VARIANT=oracle
# The fix under test: gpt-4o-mini (temp=0 is in the code)
export LME_EXTRACT_MODEL="${LME_EXTRACT_MODEL:-gpt-4o-mini}"

set -a
source "${SCRIPT_DIR}/config.sh"
set +a

command -v docker >/dev/null 2>&1 || die "docker not on PATH"
[ -f "${BENCH_PY}" ] || die "archolith-bench venv python missing: ${BENCH_PY}"
[ -d "${MENHIR_MAIN}/.git" ] || die "Menhir checkout missing: ${MENHIR_MAIN}"

KU_COUNT="$("${BENCH_PY}" -c "import json; print(len(json.load(open(r'${FIXTURE_PATH}'))))")"
log "fixture: ${KU_COUNT} knowledge-update items"

# ---- guard against clobbering ----
if docker ps -a --format '{{.Names}}' | grep -Fxq "${LME_NEO4J_NAME}"; then
  if [ "${LME_KU_ALLOW_RESUME:-0}" = "1" ]; then
    log "RESUME: reusing existing container ${LME_NEO4J_NAME}"
    docker start "${LME_NEO4J_NAME}" 2>/dev/null || true
  else
    die "container ${LME_NEO4J_NAME} already exists; set LME_KU_ALLOW_RESUME=1 to resume or pick a new LME_KU_RUN_ID"
  fi
fi

mkdir -p "${LME_RESULTS_DIR}"

# ---- record run provenance ----
MENHIR_COMMIT="$(git -C "${MENHIR_MAIN}" rev-parse --short HEAD 2>/dev/null || echo unknown)"
BENCH_COMMIT="$(git -C "${BENCH_DIR}" rev-parse --short HEAD 2>/dev/null || echo unknown)"
cat > "${LME_RESULTS_DIR}/run_provenance.json" <<EOF
{
  "run_id": "${RUN_ID}",
  "started_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "menhir_commit": "${MENHIR_COMMIT}",
  "bench_commit": "${BENCH_COMMIT}",
  "extract_model": "${LME_EXTRACT_MODEL}",
  "fixture": "${FIXTURE_PATH}",
  "fixture_count": ${KU_COUNT},
  "container": "${LME_NEO4J_NAME}",
  "bolt_port": ${LME_BOLT},
  "menhir_port": ${LME_PORT_BUILD},
  "purpose": "knowledge-update subset buildout — test whether gpt-4o-mini + temp=0 + dedup hardening generalizes beyond Rachel/suburbs"
}
EOF
log "provenance recorded: ${LME_RESULTS_DIR}/run_provenance.json"

# ---- Phase 1: build graph ----
log "======== PHASE 1: BUILD GRAPH (${KU_COUNT} items) ========"
"${SCRIPT_DIR}/build_graph.sh" "${KU_COUNT}"
log "build complete"

# ---- Phase 2: recall+QA scoring ----
log "======== PHASE 2: RECALL+QA SCORING ========"

OPENAI_KEY="$("${MENHIR_MAIN_PY}" - "${MENHIR_MAIN}/.env" OPENAI_API_KEY <<'PY'
import sys; from dotenv import dotenv_values; print(dotenv_values(sys.argv[1]).get(sys.argv[2],""))
PY
)"
[ -n "${OPENAI_KEY}" ] || die "no OPENAI_API_KEY in menhir .env"

# Start a fresh menhir for recall (the build menhir exited after build_graph.sh)
RECALL_PORT="${LME_KU_RECALL_PORT:-8125}"
RECALL_URL="http://localhost:${RECALL_PORT}"
EMPTY_ENV="$(mktemp)"
MENHIR_PID=""
cleanup_recall(){ [ -n "${MENHIR_PID}" ] && kill "${MENHIR_PID}" 2>/dev/null || true; }
trap cleanup_recall EXIT

log "starting recall menhir on port ${RECALL_PORT}..."
( export ENV_FILE="${EMPTY_ENV}" \
    LONGMEMEVAL_VARIANT=oracle \
    MENHIR_LOG_DIR="${LME_RESULTS_DIR}/menhir-recall-logs" \
    MENHIR_BENCHMARK_MODE=1 MENHIR_API_HOST=127.0.0.1 MENHIR_API_PORT="${RECALL_PORT}" \
    OTEL_SDK_DISABLED=true LANGFUSE_TRACING_ENABLED=false LANGFUSE_PUBLIC_KEY="" LANGFUSE_SECRET_KEY="" LANGFUSE_HOST="" \
    MENHIR_OPERATOR_KEY="" MENHIR_AGENT_KEY="" MENHIR_READONLY_KEY="" MENHIR_API_KEY="" \
    NEO4J_URI="bolt://localhost:${LME_BOLT}" NEO4J_USER=neo4j NEO4J_PASSWORD="${LME_NEO4J_PW}" NEO4J_DATABASE=neo4j \
    GRAPHITI_LLM_PROVIDER=openai MEMORY_GRAPHITI_PROVIDER=openai LLM_CHAT_PROVIDER=openai MEMORY_CHAT_PROVIDER=openai \
    GRAPHITI_RERANKER_PROVIDER=openai MEMORY_GRAPHITI_RERANKER_PROVIDER=openai \
    GRAPHITI_EMBED_PROVIDER=openai MEMORY_GRAPHITI_EMBED_PROVIDER=openai \
    OPENAI_API_KEY="${OPENAI_KEY}" OPENAI_CHAT_MODEL="${LME_EXTRACT_MODEL}" OPENAI_EMBED_MODEL="${LME_EMBED_MODEL}" \
    PYTHONPATH="${MENHIR_MAIN}/src"; \
  mkdir -p "${LME_RESULTS_DIR}/menhir-recall-logs"; \
  cd "${MENHIR_MAIN}" && "${MENHIR_MAIN_BIN}" serve --port "${RECALL_PORT}" ) \
  >"${LME_RESULTS_DIR}/recall_serve.log" 2>&1 &
MENHIR_PID=$!
for _ in $(seq 1 90); do curl -sf "${RECALL_URL}/api/health" >/dev/null 2>&1 && break; sleep 2; done
curl -sf "${RECALL_URL}/api/health" >/dev/null 2>&1 || die "recall menhir not healthy"
log "recall menhir healthy"

# Run the harness — score all knowledge-update items
log "scoring ${KU_COUNT} knowledge-update items..."
RECALL_OUT="${LME_RESULTS_DIR}/harness_recall"
mkdir -p "${RECALL_OUT}"

( cd "${BENCH_DIR}" && \
  UPSTREAM_BASE_URL="https://api.openai.com/v1" UPSTREAM_API_KEY="${OPENAI_KEY}" BENCHMARK_MODEL="gpt-4o" \
  OPENAI_API_KEY="${OPENAI_KEY}" LONGMEMEVAL_VARIANT=oracle \
  "${BENCH_BIN}" harness longmemeval-menhir --menhir-url "${RECALL_URL}" --recall-only \
    --model "${LME_ANSWER_MODEL}" --scorer "${LME_SCORER}" --judge-model "${LME_JUDGE_MODEL}" \
    --format markdown --subset knowledge-update \
    --output-dir "${RECALL_OUT}" --out "${RECALL_OUT}/results.md" \
    --limit "${KU_COUNT}" --recall-limit 10 --resume ) \
  >>"${LME_RESULTS_DIR}/recall_harness.log" 2>&1
HARNESS_EXIT=$?

log "harness exit code: ${HARNESS_EXIT}"

if [ -f "${RECALL_OUT}/results.md" ]; then
  log "======== RESULTS ========"
  cat "${RECALL_OUT}/results.md" >&2
fi

# Record completion
"${BENCH_PY}" -c "
import json, sys
p = '${LME_RESULTS_DIR}/run_provenance.json'
d = json.load(open(p)); d['completed_at'] = '$(date -u +%Y-%m-%dT%H:%M:%SZ)'; d['harness_exit'] = ${HARNESS_EXIT}
json.dump(d, open(p,'w'), indent=2)
"

kill "${MENHIR_PID}" 2>/dev/null || true
MENHIR_PID=""
log "done. Results in ${LME_RESULTS_DIR}"
log "Neo4j container ${LME_NEO4J_NAME} left up for inspection."
log "To clean up: docker rm -f ${LME_NEO4J_NAME} && docker volume rm ${LME_NEO4J_VOL}"
