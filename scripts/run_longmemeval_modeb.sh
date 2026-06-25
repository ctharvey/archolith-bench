#!/usr/bin/env bash
#
# run_longmemeval_modeb.sh -- LongMemEval Mode B (menhir persistent memory) run.
#
# Mode B answers LongMemEval questions using menhir's persistent graph memory
# (ingest each session as episodes, then recall) instead of stuffing the whole
# haystack in-context. This is the launch / marketing benchmark.
#
# Marketing config (decided):
#   answer model       : deepseek-v4-flash   (bench send_chat -> UPSTREAM_BASE_URL)
#   menhir extraction  : deepseek-v4-flash   (Graphiti LLM, OpenAI-compatible)
#   menhir embedding   : text-embedding-3-small (OpenAI, 1536-dim, matches prod)
#
# KEY DESIGN NOTE (why no code change was needed for benchmark_mode):
#   menhir's enrichment worker is an in-process asyncio task (_ensure_enrichment_worker),
#   NOT scheduler-managed. The ONLY scheduler dependency in the enrichment path is
#   acquire_llama_url_async, which fires ONLY for local-llama base URLs (8081) --
#   see should_use_scheduler() in infrastructure/llama_endpoint.py. With CLOUD
#   provider base URLs (deepseek / openai), should_use_scheduler() is False, so
#   ingestion enriches inline on POST /api/memory?wait=true. MENHIR_BENCHMARK_MODE=1
#   therefore correctly disables ONLY the maintenance scheduler + orphan recovery
#   (no store mutation mid-measurement) without blocking ingestion.
#   The earlier "episode stuck queued" was purely a config artifact of running the
#   throwaway against the DEFAULT local-llama provider; it is not a code bug.
#
# SAFETY: never points at production. Throwaway Neo4j only (port 7688, separate
#   volume). menhir runs on port 8101 (prod is 8100). Secrets are read from the
#   existing .env files at runtime and never written to any committed file.
#   The bench harness independently enforces assert_not_production(--menhir-url).
#
# STATUS: recipe values are individually verified against the code; the full
#   sequence had NOT been executed end-to-end at authoring time because the Docker
#   daemon was down (WSL killed). Treat the first real run as a shakeout.
#
# Usage:
#   scripts/run_longmemeval_modeb.sh --check          # preflight only, no side effects
#   scripts/run_longmemeval_modeb.sh --limit 20       # real run, first 20 items
#   scripts/run_longmemeval_modeb.sh --subset single-session-user --limit 10
#
set -euo pipefail

# ---- fixed config -----------------------------------------------------------
BENCH_DIR="/c/Users/thron/IdeaProjects/projects/archolith/archolith-bench"
MENHIR_DIR="/c/Users/thron/IdeaProjects/projects/archolith/menhir"
DELEGATE_ENV="/c/Users/thron/IdeaProjects/projects/ctharvey/cth.mcp.delegate/.env"
MENHIR_PY="${MENHIR_DIR}/.venv/Scripts/python.exe"
MENHIR_BIN="${MENHIR_DIR}/.venv/Scripts/menhir"
BENCH_PY="${BENCH_DIR}/.venv/Scripts/python.exe"
BENCH_BIN="${BENCH_DIR}/.venv/Scripts/archolith-bench"

COMPOSE_FILE="${MENHIR_DIR}/docker-compose.benchmark.yml"
NEO4J_BOLT_PORT=7688
NEO4J_HTTP_PORT=7475
NEO4J_PASSWORD="benchthrowaway"
MENHIR_PORT=8101
MENHIR_URL="http://localhost:${MENHIR_PORT}"

DEEPSEEK_BASE="https://api.deepseek.com/v1"
DEEPSEEK_MODEL="deepseek-v4-flash"   # the ANSWER model (bench send_chat -> upstream)
OPENAI_EMBED_MODEL="text-embedding-3-small"

# menhir EXTRACTION LLM (Graphiti entity/edge extraction). Single switch:
#   openai   -> gpt-4.1-nano @ api.openai.com  (fast: finishes within menhir's 60s
#               per-episode wait=true cap; this is the WORKING config)
#   deepseek -> deepseek-v4-flash @ api.deepseek.com  (the marketing-intended model,
#               but ~4-5s/call currently overruns the 60s wait so recall races ahead
#               of enrichment -> empty recall. Revisit with a longer enrichment wait.)
EXTRACTION_PROVIDER="openai"          # openai | deepseek
OPENAI_EXTRACTION_MODEL="gpt-4.1-nano"

# ---- args -------------------------------------------------------------------
LIMIT=""
SUBSET=""
CHECK_ONLY=0
for ((i=1; i<=$#; i++)); do
  case "${!i}" in
    --check)  CHECK_ONLY=1 ;;
    --limit)  n=$((i+1)); LIMIT="${!n}"; i=$n ;;
    --subset) n=$((i+1)); SUBSET="${!n}"; i=$n ;;
    *) ;;
  esac
done

log() { printf '[modeb] %s\n' "$*" >&2; }
die() { printf '[modeb] ERROR: %s\n' "$*" >&2; exit 1; }

read_env_val() {  # read_env_val <env-file> <KEY>   (never echoes the value to logs)
  "${MENHIR_PY}" - "$1" "$2" <<'PY'
import sys
from dotenv import dotenv_values
print(dotenv_values(sys.argv[1]).get(sys.argv[2], ""))
PY
}

# ---- preflight --------------------------------------------------------------
log "preflight..."
command -v docker >/dev/null 2>&1 || die "docker not on PATH"
docker version --format '{{.Server.Version}}' >/dev/null 2>&1 \
  || die "Docker daemon is not running -- start Docker Desktop / WSL first"
[ -f "${COMPOSE_FILE}" ]   || die "missing compose file: ${COMPOSE_FILE}"
[ -x "${MENHIR_PY}" ]      || die "menhir venv python missing: ${MENHIR_PY}"
[ -e "${MENHIR_BIN}" ] || [ -e "${MENHIR_BIN}.exe" ] || die "menhir console script missing (pip install -e ${MENHIR_DIR})"
[ -e "${BENCH_BIN}" ] || [ -e "${BENCH_BIN}.exe" ] || die "archolith-bench not installed -- create ${BENCH_DIR}/.venv and 'pip install -e .[longmemeval]'"

DEEPSEEK_KEY="$(read_env_val "${DELEGATE_ENV}" DELEGATE_API_KEY)"
OPENAI_KEY="$(read_env_val "${MENHIR_DIR}/.env" OPENAI_API_KEY)"
[ -n "${DEEPSEEK_KEY}" ] || die "DELEGATE_API_KEY (deepseek) not found in ${DELEGATE_ENV}"
[ -n "${OPENAI_KEY}" ]   || die "OPENAI_API_KEY not found in ${MENHIR_DIR}/.env"
log "secrets resolved: deepseek=set(len=${#DEEPSEEK_KEY}) openai=set(len=${#OPENAI_KEY})"

if [ "${CHECK_ONLY}" = "1" ]; then
  log "preflight OK (--check). Docker up, venvs present, keys resolved. Not launching."
  exit 0
fi

# ---- teardown trap ----------------------------------------------------------
MENHIR_PID=""
cleanup() {
  log "teardown..."
  [ -n "${MENHIR_PID}" ] && kill "${MENHIR_PID}" 2>/dev/null || true
  docker compose -f "${COMPOSE_FILE}" down -v 2>/dev/null || true
}
trap cleanup EXIT

# ---- 1. throwaway Neo4j -----------------------------------------------------
log "starting throwaway Neo4j (bolt ${NEO4J_BOLT_PORT})..."
docker compose -f "${COMPOSE_FILE}" up -d
log "waiting for Neo4j HTTP (${NEO4J_HTTP_PORT})..."
for _ in $(seq 1 60); do
  if curl -sf "http://localhost:${NEO4J_HTTP_PORT}" >/dev/null 2>&1; then break; fi
  sleep 2
done
curl -sf "http://localhost:${NEO4J_HTTP_PORT}" >/dev/null 2>&1 \
  || die "Neo4j did not become ready on ${NEO4J_HTTP_PORT}"

# ---- 2. menhir server (cloud providers, benchmark mode, auth disabled) ------
# ENV_FILE points at an empty file so menhir's default .env (local-llama / prod
# Neo4j) is NOT loaded; load_dotenv(override=False) keeps these explicit exports.
EMPTY_ENV="$(mktemp)"
export ENV_FILE="${EMPTY_ENV}"
export MENHIR_BENCHMARK_MODE=1
export MENHIR_API_HOST=127.0.0.1
export MENHIR_API_PORT="${MENHIR_PORT}"
# Kill telemetry export: no Langfuse/OTLP collector runs in the throwaway, and the
# default exporter blocks ~5s per span batch trying localhost:3001, starving the
# event loop and aggravating upstream (deepseek) connect timeouts.
export OTEL_SDK_DISABLED=true
export LANGFUSE_TRACING_ENABLED=false
export LANGFUSE_PUBLIC_KEY="" LANGFUSE_SECRET_KEY="" LANGFUSE_HOST=""
# auth disabled on the throwaway (no keys -> BearerAuthMiddleware is a pass-through)
export MENHIR_OPERATOR_KEY="" MENHIR_AGENT_KEY="" MENHIR_READONLY_KEY="" MENHIR_API_KEY=""
# throwaway Neo4j
export NEO4J_URI="bolt://localhost:${NEO4J_BOLT_PORT}"
export NEO4J_USER="neo4j"
export NEO4J_PASSWORD="${NEO4J_PASSWORD}"
export NEO4J_DATABASE="neo4j"
# Extraction LLM provider selection. We pin every provider/model var with CANONICAL
# names so the throwaway is deterministic and ISOLATED from the launching shell --
# menhir settings read straight from os.environ with no override guard, so an inherited
# GRAPHITI_LLM_PROVIDER / OPENAI_CHAT_MODEL would otherwise silently win. (The canonical
# var is GRAPHITI_LLM_PROVIDER, NOT GRAPHITI_PROVIDER, which menhir historically dropped.)
if [ "${EXTRACTION_PROVIDER}" = "deepseek" ]; then
  # deepseek via the OpenAI-compatible "local" kind (cloud URL -> no scheduler).
  export GRAPHITI_LLM_PROVIDER="local" MEMORY_GRAPHITI_PROVIDER="local"
  export LLM_CHAT_PROVIDER="local" MEMORY_CHAT_PROVIDER="local"
  export GRAPHITI_RERANKER_PROVIDER="local" MEMORY_GRAPHITI_RERANKER_PROVIDER="local"
  export LOCAL_LLM_BASE_URL="${DEEPSEEK_BASE}"
  export LOCAL_LLM_CHAT_MODEL="${DEEPSEEK_MODEL}"
  export LOCAL_LLM_API_KEY="${DEEPSEEK_KEY}"
  unset OPENAI_CHAT_MODEL
  log "extraction LLM = deepseek (${DEEPSEEK_MODEL})"
else
  # openai gpt-4.1-nano (working config: fast enough for the 60s per-episode wait).
  export GRAPHITI_LLM_PROVIDER="openai" MEMORY_GRAPHITI_PROVIDER="openai"
  export LLM_CHAT_PROVIDER="openai" MEMORY_CHAT_PROVIDER="openai"
  export GRAPHITI_RERANKER_PROVIDER="openai" MEMORY_GRAPHITI_RERANKER_PROVIDER="openai"
  export OPENAI_CHAT_MODEL="${OPENAI_EXTRACTION_MODEL}"
  log "extraction LLM = openai (${OPENAI_EXTRACTION_MODEL})"
fi
# embedding = openai text-embedding-3-small (1536-dim, matches prod)
export GRAPHITI_EMBED_PROVIDER="openai" MEMORY_GRAPHITI_EMBED_PROVIDER="openai"
export OPENAI_API_KEY="${OPENAI_KEY}"
export OPENAI_EMBED_MODEL="${OPENAI_EMBED_MODEL}"

log "starting menhir serve on ${MENHIR_URL} (extraction=${DEEPSEEK_MODEL}, embed=${OPENAI_EMBED_MODEL})..."
( cd "${MENHIR_DIR}" && "${MENHIR_BIN}" serve --port "${MENHIR_PORT}" ) &
MENHIR_PID=$!

log "waiting for menhir /api/health..."
for _ in $(seq 1 90); do
  if curl -sf "${MENHIR_URL}/api/health" >/dev/null 2>&1; then break; fi
  sleep 2
done
curl -sf "${MENHIR_URL}/api/health" >/dev/null 2>&1 \
  || die "menhir did not become healthy on ${MENHIR_PORT}"
log "menhir healthy."

# ---- 3. bench: LongMemEval Mode B ------------------------------------------
# answer model endpoint (deepseek) for the bench send_chat path
export UPSTREAM_BASE_URL="${DEEPSEEK_BASE}"
export UPSTREAM_API_KEY="${DEEPSEEK_KEY}"
export BENCHMARK_MODEL="${DEEPSEEK_MODEL}"

cmd=( "${BENCH_BIN}" harness longmemeval-menhir
      --menhir-url "${MENHIR_URL}"
      --confirm-menhir-reset
      --model "${DEEPSEEK_MODEL}"
      --format markdown
      --out "${BENCH_DIR}/results/harness_longmemeval_modeb.md" )
[ -n "${LIMIT}"  ] && cmd+=( --limit "${LIMIT}" )
[ -n "${SUBSET}" ] && cmd+=( --subset "${SUBSET}" )

log "running: ${cmd[*]}"
( cd "${BENCH_DIR}" && "${cmd[@]}" )

log "done. Evidence: ${BENCH_DIR}/results/harness_longmemeval_modeb.md"
