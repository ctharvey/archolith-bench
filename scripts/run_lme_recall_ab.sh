#!/usr/bin/env bash
# Recall-only LongMemEval Mode-B A/B against the PRE-BUILT menhir-lme-neo4j graph.
#
# Point it at any branch OR worktree path; it materializes the menhir source (auto
# `git worktree add` when given a bare branch, reusing an existing worktree if there is
# one), serves menhir from that source over the persistent LME Neo4j via PYTHONPATH
# (no per-variant rewiring), and runs the no_memory vs menhir_recall A/B in RECALL-ONLY
# mode — it never re-ingests and never resets the graph.
#
# Prereq: the graph must already be built once via scripts/_lme_build_db.sh.
# Usage:  run_lme_recall_ab.sh <branch|worktree-path> [limit]
#   run_lme_recall_ab.sh main 30
#   run_lme_recall_ab.sh claude/menhir-chain-handoff-doc-7iuat2 30
#   run_lme_recall_ab.sh ../menhir-frontier 30
# Env overrides: ANSWER_MODEL (default gpt-4o-mini), LONGMEMEVAL_VARIANT (default oracle —
#   MUST match the variant the graph was built with), SCORER (containment|llm-judge).
set -euo pipefail

SRC_ARG="${1:?usage: run_lme_recall_ab.sh <branch|worktree-path> [limit]}"
LIMIT="${2:-30}"

ARCH_DIR="/c/Users/thron/IdeaProjects/projects/archolith"
BENCH_DIR="${ARCH_DIR}/archolith-bench"
MENHIR_MAIN="${ARCH_DIR}/menhir"            # repo root + the installed menhir venv/console script
MENHIR_PY="${MENHIR_MAIN}/.venv/Scripts/python.exe"
MENHIR_BIN="${MENHIR_MAIN}/.venv/Scripts/menhir"
BENCH_BIN="${BENCH_DIR}/.venv/Scripts/archolith-bench"
# Pre-built LME graph (from _lme_build_db.sh) — REUSE only, NEVER create or reset here.
NEO4J_NAME="menhir-lme-neo4j"; NEO4J_BOLT=7689; NEO4J_HTTP=7476; NEO4J_PW="lmedata123"
MENHIR_PORT=8103; MENHIR_URL="http://localhost:${MENHIR_PORT}"
ANSWER_MODEL="${ANSWER_MODEL:-gpt-4o-mini}"
SCORER="${SCORER:-containment}"
# MUST match the variant the graph was ingested under, or question_ids (namespaces) won't line up.
export LONGMEMEVAL_VARIANT="${LONGMEMEVAL_VARIANT:-oracle}"

log(){ printf '[lme-recall] %s\n' "$*" >&2; }
die(){ printf '[lme-recall] ERROR: %s\n' "$*" >&2; exit 1; }

# ---- resolve the menhir source to A/B (explicit worktree path, or auto worktree from a branch) ----
WT_CREATED=""
if [ -d "${SRC_ARG}/src/menhir" ]; then
  SRC_DIR="$(cd "${SRC_ARG}" && pwd)"                       # an explicit menhir checkout/worktree
  log "source = path ${SRC_DIR}"
else
  BRANCH="${SRC_ARG}"                                        # treat as a branch name
  SRC_DIR="$(git -C "${MENHIR_MAIN}" worktree list --porcelain \
            | awk -v b="refs/heads/${BRANCH}" '/^worktree /{p=substr($0,10)} /^branch /{if($2==b) print p}' \
            | head -1)"
  if [ -n "${SRC_DIR}" ]; then
    log "source = existing worktree for ${BRANCH}: ${SRC_DIR}"
  else
    SRC_DIR="${ARCH_DIR}/.lme-worktrees/$(printf '%s' "${BRANCH}" | tr '/:' '__')"
    log "source = NEW worktree for ${BRANCH} -> ${SRC_DIR}"
    git -C "${MENHIR_MAIN}" worktree add "${SRC_DIR}" "${BRANCH}" >/dev/null || die "git worktree add ${BRANCH} failed"
    WT_CREATED="${SRC_DIR}"
  fi
fi
[ -d "${SRC_DIR}/src/menhir" ] || die "no src/menhir under ${SRC_DIR}"
VARIANT="$(basename "${SRC_DIR}")"
RUN_OUTPUT_DIR="${BENCH_DIR}/results/lme-recall-${VARIANT}"; mkdir -p "${RUN_OUTPUT_DIR}"

OPENAI_KEY="$("${MENHIR_PY}" - "${MENHIR_MAIN}/.env" OPENAI_API_KEY <<'PY'
import sys; from dotenv import dotenv_values; print(dotenv_values(sys.argv[1]).get(sys.argv[2],""))
PY
)"; [ -n "${OPENAI_KEY}" ] || die "no OPENAI_API_KEY in ${MENHIR_MAIN}/.env"

# ---- ensure the PRE-BUILT Neo4j is up (reuse only; never create, never reset) ----
docker ps --format '{{.Names}}' | grep -qx "${NEO4J_NAME}" \
  || docker start "${NEO4J_NAME}" >/dev/null 2>&1 \
  || die "pre-built ${NEO4J_NAME} not found — run scripts/_lme_build_db.sh first"
for _ in $(seq 1 60); do curl -sf "http://localhost:${NEO4J_HTTP}" >/dev/null 2>&1 && break; sleep 2; done
curl -sf "http://localhost:${NEO4J_HTTP}" >/dev/null 2>&1 || die "Neo4j ${NEO4J_NAME} not ready"

MENHIR_PID=""
cleanup(){
  [ -n "${MENHIR_PID}" ] && kill "${MENHIR_PID}" 2>/dev/null || true
  # Remove ONLY a worktree this script created; never an existing one, never the Neo4j.
  [ -n "${WT_CREATED}" ] && git -C "${MENHIR_MAIN}" worktree remove --force "${WT_CREATED}" 2>/dev/null || true
}
trap cleanup EXIT

# ---- serve menhir from the variant source over the pre-built Neo4j (recall path only) ----
export PYTHONPATH="${SRC_DIR}/src"          # load the variant's source over the installed menhir
EMPTY_ENV="$(mktemp)"; export ENV_FILE="${EMPTY_ENV}"
export MENHIR_LOG_DIR="${RUN_OUTPUT_DIR}/menhir-logs"; mkdir -p "${MENHIR_LOG_DIR}"
export MENHIR_BENCHMARK_MODE=1 MENHIR_API_HOST=127.0.0.1 MENHIR_API_PORT="${MENHIR_PORT}"
export OTEL_SDK_DISABLED=true LANGFUSE_TRACING_ENABLED=false LANGFUSE_PUBLIC_KEY="" LANGFUSE_SECRET_KEY="" LANGFUSE_HOST=""
export MENHIR_OPERATOR_KEY="" MENHIR_AGENT_KEY="" MENHIR_READONLY_KEY="" MENHIR_API_KEY=""
export NEO4J_URI="bolt://localhost:${NEO4J_BOLT}" NEO4J_USER="neo4j" NEO4J_PASSWORD="${NEO4J_PW}" NEO4J_DATABASE="neo4j"
# Recall embeds the query, so it needs the SAME embedder the graph was built with.
export GRAPHITI_EMBED_PROVIDER="openai" MEMORY_GRAPHITI_EMBED_PROVIDER="openai"
export OPENAI_API_KEY="${OPENAI_KEY}" OPENAI_EMBED_MODEL="text-embedding-3-small"

log "serving menhir (${VARIANT}) on ${MENHIR_URL} over ${NEO4J_NAME} (bolt ${NEO4J_BOLT})..."
( cd "${SRC_DIR}" && "${MENHIR_BIN}" serve --port "${MENHIR_PORT}" ) & MENHIR_PID=$!
for _ in $(seq 1 90); do curl -sf "${MENHIR_URL}/api/health" >/dev/null 2>&1 && break; sleep 2; done
curl -sf "${MENHIR_URL}/api/health" >/dev/null 2>&1 || die "menhir not healthy"

# ---- recall-only A/B: no ingest, no reset (so --confirm-menhir-reset is NOT needed) ----
export UPSTREAM_BASE_URL="https://api.openai.com/v1" UPSTREAM_API_KEY="${OPENAI_KEY}" BENCHMARK_MODEL="${ANSWER_MODEL}"
log "recall-only A/B (${VARIANT}) variant=${LONGMEMEVAL_VARIANT} limit=${LIMIT} scorer=${SCORER}..."
( cd "${BENCH_DIR}" && "${BENCH_BIN}" harness longmemeval-menhir \
    --menhir-url "${MENHIR_URL}" --recall-only \
    --model "${ANSWER_MODEL}" --scorer "${SCORER}" --format markdown \
    --output-dir "${RUN_OUTPUT_DIR}" --out "${RUN_OUTPUT_DIR}/harness_recall_ab.md" \
    --limit "${LIMIT}" --resume )
log "done -> ${RUN_OUTPUT_DIR}/harness_recall_ab.md"
