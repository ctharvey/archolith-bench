#!/usr/bin/env bash
# Build a FRESH graph with ONLY the 78 knowledge-update items from LongMemEval (oracle variant),
# then run recall+QA scoring against it. This is the canonical current-code scalar reingest:
# scalar consolidation and TurnEvidence are mandatory, and recall explicitly exercises View authority.
#
# Two arms are intentionally pinned so the post-binding measurement has a contemporaneous control:
#   baseline  = current production gate (3/3, no identity reconciliation)
#   candidate = true 2/3 + attribute/scope/subject identity reconciliation
#
# Usage:
#   LME_KU_RUN_ID=scalar-current-baseline-20260728 LME_KU_ARM=baseline \
#     ./scripts/longmemeval/run_knowledge_update_buildout.sh
#   LME_KU_RUN_ID=scalar-current-candidate-20260728 LME_KU_ARM=candidate \
#     ./scripts/longmemeval/run_knowledge_update_buildout.sh
#   LME_KU_RUN_ID=... LME_KU_ARM=baseline \
#     ./scripts/longmemeval/run_knowledge_update_buildout.sh --preflight-only
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BENCH_DIR="$(git -C "${SCRIPT_DIR}" rev-parse --show-toplevel)"
ARCH_DIR="${BENCH_DIR%/*}"

log(){ printf '[lme-ku-buildout] %s %s\n' "$(date '+%F %H:%M:%S')" "$*" >&2; }
die(){ printf '[lme-ku-buildout] ERROR: %s\n' "$*" >&2; exit 1; }

MODE="${1:-run}"
[ "${MODE}" = "run" ] || [ "${MODE}" = "--preflight-only" ] ||
  die "unknown argument: ${MODE} (expected --preflight-only or no argument)"

RUN_ID="${LME_KU_RUN_ID:-}"
[ -n "${RUN_ID}" ] || die "LME_KU_RUN_ID is required; never reuse the historical default"
[[ "${RUN_ID}" =~ ^[A-Za-z0-9._-]+$ ]] || die "RUN_ID contains unsafe characters"

ARM="${LME_KU_ARM:-}"
case "${ARM}" in
  baseline)
    export LME_SCALAR_THRESHOLD="1.0"
    export LME_SCALAR_RECONCILE_ATTRIBUTE="0"
    export LME_SCALAR_RECONCILE_SCOPE="0"
    export LME_SCALAR_RECONCILE_SUBJECT="0"
    ;;
  candidate)
    export LME_SCALAR_THRESHOLD="2/3"
    export LME_SCALAR_RECONCILE_ATTRIBUTE="1"
    export LME_SCALAR_RECONCILE_SCOPE="1"
    export LME_SCALAR_RECONCILE_SUBJECT="1"
    ;;
  *)
    die "LME_KU_ARM must be exactly 'baseline' or 'candidate'"
    ;;
esac

# This dedicated wrapper must never silently fall back to the ordinary non-scalar LME defaults.
export LME_SCALAR_STATE_ENABLED="1"
export LME_REQUIRE_TURN_EVIDENCE="1"
export LME_BACKFILL_DATES="0"
export LME_SCALAR_VIEW_AUTHORITY_ENABLED="${LME_SCALAR_VIEW_AUTHORITY_ENABLED:-1}"
export LME_CONSOLIDATION_AUDIT_ENABLED="${LME_CONSOLIDATION_AUDIT_ENABLED:-1}"
export LME_RECALL_AUDIT_ENABLED="${LME_RECALL_AUDIT_ENABLED:-1}"
export MENHIR_PERSONAL_MEMORY_CONSOLIDATION_AUDIT_ENABLED="${LME_CONSOLIDATION_AUDIT_ENABLED}"
export LME_KU_ALLOW_RESUME="${LME_KU_ALLOW_RESUME:-0}"
export LME_KU_KEEP_NEO4J_UP="${LME_KU_KEEP_NEO4J_UP:-0}"
export LME_KU_ALLOW_DIRTY="${LME_KU_ALLOW_DIRTY:-0}"
if [ "${LME_KU_ALLOW_RESUME}" = "1" ]; then
  export LME_REQUIRE_FRESH="0"
else
  export LME_REQUIRE_FRESH="1"
fi

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
[ -f "${BENCH_BIN}" ] || die "archolith-bench CLI missing: ${BENCH_BIN}"
[ -f "${MENHIR_MAIN_PY}" ] || die "Menhir venv python missing: ${MENHIR_MAIN_PY}"
[ -f "${MENHIR_MAIN_BIN}" ] || die "Menhir CLI missing: ${MENHIR_MAIN_BIN}"
[ -d "${MENHIR_MAIN}/.git" ] || die "Menhir checkout missing: ${MENHIR_MAIN}"
docker info >/dev/null 2>&1 || die "Docker daemon is not available"
docker image inspect "${LME_NEO4J_IMAGE}" >/dev/null 2>&1 ||
  die "pinned Neo4j image is not available locally: ${LME_NEO4J_IMAGE}"

MENHIR_COMMIT="$(git -C "${MENHIR_MAIN}" rev-parse HEAD 2>/dev/null || echo unknown)"
BENCH_COMMIT="$(git -C "${BENCH_DIR}" rev-parse HEAD 2>/dev/null || echo unknown)"
MENHIR_DIRTY="$([ -n "$(git -C "${MENHIR_MAIN}" status --porcelain --untracked-files=no)" ] && echo true || echo false)"
BENCH_DIRTY="$([ -n "$(git -C "${BENCH_DIR}" status --porcelain --untracked-files=no)" ] && echo true || echo false)"
if [ "${LME_KU_ALLOW_DIRTY}" != "1" ] &&
   { [ "${MENHIR_DIRTY}" = "true" ] || [ "${BENCH_DIRTY}" = "true" ]; }; then
  die "tracked code is dirty (menhir=${MENHIR_DIRTY}, bench=${BENCH_DIRTY}); commit it or set LME_KU_ALLOW_DIRTY=1 for a non-canonical run"
fi

read -r KU_COUNT FIXTURE_SHA256 < <(
  "${BENCH_PY}" - "${FIXTURE_PATH}" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
raw = path.read_bytes()
rows = json.loads(raw)
if not isinstance(rows, list) or not rows:
    raise SystemExit("fixture must be a non-empty JSON list")
ids = [str(row.get("question_id") or "") for row in rows]
if any(not question_id for question_id in ids) or len(set(ids)) != len(ids):
    raise SystemExit("fixture question_id values must be non-empty and unique")
if any(row.get("question_type") != "knowledge-update" for row in rows):
    raise SystemExit("fixture contains a non-knowledge-update item")
if any(not row.get("question") or not row.get("answer") for row in rows):
    raise SystemExit("fixture contains an item without a question or answer")
print(len(rows), hashlib.sha256(raw).hexdigest())
PY
)
[ "${KU_COUNT}" = "78" ] || die "expected the frozen 78-item fixture, found ${KU_COUNT}"
log "fixture: ${KU_COUNT} knowledge-update items; sha256=${FIXTURE_SHA256}"

# ---- guard against clobbering ----
if docker ps -a --format '{{.Names}}' | grep -Fxq "${LME_NEO4J_NAME}"; then
  if [ "${LME_KU_ALLOW_RESUME:-0}" = "1" ]; then
    log "RESUME: reusing existing container ${LME_NEO4J_NAME}"
    docker start "${LME_NEO4J_NAME}" 2>/dev/null || true
  else
    die "container ${LME_NEO4J_NAME} already exists; set LME_KU_ALLOW_RESUME=1 to resume or pick a new LME_KU_RUN_ID"
  fi
fi

if [ "${LME_KU_ALLOW_RESUME}" != "1" ]; then
  docker volume inspect "${LME_NEO4J_VOL}" >/dev/null 2>&1 &&
    die "fresh run refused: volume already exists: ${LME_NEO4J_VOL}"
  [ ! -e "${LME_RESULTS_DIR}" ] ||
    die "fresh run refused: results directory already exists: ${LME_RESULTS_DIR}"
  "${BENCH_PY}" - "${LME_BOLT}" "${LME_HTTP}" "${LME_PORT_BUILD}" "${LME_KU_RECALL_PORT:-8125}" <<'PY'
import socket
import sys

for raw in sys.argv[1:]:
    port = int(raw)
    with socket.socket() as sock:
        try:
            sock.bind(("127.0.0.1", port))
        except OSError as exc:
            raise SystemExit(f"required port is unavailable: {port}: {exc}") from exc
PY
fi

OPENAI_KEY="$("${MENHIR_MAIN_PY}" - "${MENHIR_MAIN}/.env" OPENAI_API_KEY <<'PY'
import sys
from dotenv import dotenv_values

print(dotenv_values(sys.argv[1]).get(sys.argv[2], ""))
PY
)"
[ -n "${OPENAI_KEY}" ] || die "no OPENAI_API_KEY in menhir .env"

log "preflight PASS: arm=${ARM} run=${RUN_ID} fresh=${LME_REQUIRE_FRESH} scalar=1 threshold=${LME_SCALAR_THRESHOLD} reconcile=${LME_SCALAR_RECONCILE_ATTRIBUTE}/${LME_SCALAR_RECONCILE_SCOPE}/${LME_SCALAR_RECONCILE_SUBJECT} authority=${LME_SCALAR_VIEW_AUTHORITY_ENABLED} turn_evidence=${LME_REQUIRE_TURN_EVIDENCE} audits=${LME_CONSOLIDATION_AUDIT_ENABLED}/${LME_RECALL_AUDIT_ENABLED}"

if [ "${MODE}" = "--preflight-only" ]; then
  exit 0
fi

mkdir -p "${LME_RESULTS_DIR}"

# ---- record run provenance ----
cat > "${LME_RESULTS_DIR}/run_provenance.json" <<EOF
{
  "run_id": "${RUN_ID}",
  "arm": "${ARM}",
  "started_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "menhir_commit": "${MENHIR_COMMIT}",
  "menhir_dirty": ${MENHIR_DIRTY},
  "bench_commit": "${BENCH_COMMIT}",
  "bench_dirty": ${BENCH_DIRTY},
  "extract_model": "${LME_EXTRACT_MODEL}",
  "fixture": "${FIXTURE_PATH}",
  "fixture_count": ${KU_COUNT},
  "fixture_sha256": "${FIXTURE_SHA256}",
  "container": "${LME_NEO4J_NAME}",
  "volume": "${LME_NEO4J_VOL}",
  "bolt_port": ${LME_BOLT},
  "menhir_port": ${LME_PORT_BUILD},
  "recall_port": ${LME_KU_RECALL_PORT:-8125},
  "neo4j_heap": "${LME_NEO4J_HEAP}",
  "require_fresh": ${LME_REQUIRE_FRESH},
  "scalar_state_enabled": ${LME_SCALAR_STATE_ENABLED},
  "scalar_threshold": "${LME_SCALAR_THRESHOLD}",
  "scalar_reconcile_attribute": ${LME_SCALAR_RECONCILE_ATTRIBUTE},
  "scalar_reconcile_scope": ${LME_SCALAR_RECONCILE_SCOPE},
  "scalar_reconcile_subject": ${LME_SCALAR_RECONCILE_SUBJECT},
  "scalar_view_authority_enabled": ${LME_SCALAR_VIEW_AUTHORITY_ENABLED},
  "consolidation_audit_enabled": ${LME_CONSOLIDATION_AUDIT_ENABLED},
  "recall_audit_enabled": ${LME_RECALL_AUDIT_ENABLED},
  "turn_evidence_required": ${LME_REQUIRE_TURN_EVIDENCE},
  "backfill_dates": ${LME_BACKFILL_DATES},
  "purpose": "fresh current-code scalar knowledge-update ${ARM} arm"
}
EOF
log "provenance recorded: ${LME_RESULTS_DIR}/run_provenance.json"

MENHIR_PID=""
cleanup_all(){
  [ -n "${MENHIR_PID}" ] && kill "${MENHIR_PID}" 2>/dev/null || true
  if [ "${LME_KU_KEEP_NEO4J_UP}" != "1" ] &&
     docker ps --format '{{.Names}}' | grep -Fxq "${LME_NEO4J_NAME}"; then
    log "stopping ${LME_NEO4J_NAME}; container and volume are preserved for inspection"
    docker stop "${LME_NEO4J_NAME}" >/dev/null || true
  fi
}
trap cleanup_all EXIT

# ---- Phase 1: build graph ----
log "======== PHASE 1: BUILD GRAPH (${KU_COUNT} items) ========"
"${SCRIPT_DIR}/build_graph.sh" "${KU_COUNT}"
log "build complete"

# ---- Phase 2: recall+QA scoring ----
log "======== PHASE 2: RECALL+QA SCORING ========"

# Start a fresh menhir for recall (the build menhir exited after build_graph.sh)
RECALL_PORT="${LME_KU_RECALL_PORT:-8125}"
RECALL_URL="http://localhost:${RECALL_PORT}"
EMPTY_ENV="$(mktemp)"

log "starting recall menhir on port ${RECALL_PORT}..."
( export ENV_FILE="${EMPTY_ENV}" \
    LONGMEMEVAL_VARIANT=oracle \
    MENHIR_LOG_DIR="${LME_RESULTS_DIR}/menhir-recall-logs" \
    MENHIR_BENCHMARK_MODE=1 MENHIR_API_HOST=127.0.0.1 MENHIR_API_PORT="${RECALL_PORT}" \
    MENHIR_PERSONAL_MEMORY_SCALAR_STATE_ENABLED="${LME_SCALAR_STATE_ENABLED}" \
    MENHIR_PERSONAL_MEMORY_SCALAR_VIEW_AUTHORITY_ENABLED="${LME_SCALAR_VIEW_AUTHORITY_ENABLED}" \
    MENHIR_PERSONAL_MEMORY_RECALL_AUDIT_ENABLED="${LME_RECALL_AUDIT_ENABLED}" \
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

if ( cd "${BENCH_DIR}" && \
  UPSTREAM_BASE_URL="https://api.openai.com/v1" UPSTREAM_API_KEY="${OPENAI_KEY}" BENCHMARK_MODEL="gpt-4o" \
  OPENAI_API_KEY="${OPENAI_KEY}" LONGMEMEVAL_VARIANT=oracle \
  "${BENCH_BIN}" harness longmemeval-menhir --menhir-url "${RECALL_URL}" --recall-only \
    --model "${LME_ANSWER_MODEL}" --scorer "${LME_SCORER}" --judge-model "${LME_JUDGE_MODEL}" \
    --format markdown --subset knowledge-update \
    --output-dir "${RECALL_OUT}" --out "${RECALL_OUT}/results.md" \
    --limit "${KU_COUNT}" --recall-limit 10 --resume ) \
  >>"${LME_RESULTS_DIR}/recall_harness.log" 2>&1; then
  HARNESS_EXIT=0
else
  HARNESS_EXIT=$?
fi

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
if [ "${LME_KU_KEEP_NEO4J_UP}" = "1" ]; then
  log "Neo4j container ${LME_NEO4J_NAME} left up by request."
else
  log "Neo4j container ${LME_NEO4J_NAME} will be stopped; data remains in ${LME_NEO4J_VOL}."
fi
exit "${HARNESS_EXIT}"
