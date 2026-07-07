#!/usr/bin/env bash
# D0 — Retrieval Entropy instrument runner. Deterministic, GPT-free.
#   floor    — dispersion of the answer's evidence in the graph (Neo4j + dataset only)
#   delivered/both — also serves menhir node-only and measures the retriever walk to first gold hit
# Re-run before/after a consolidation pass and diff the FLOOR vector — that is the fitness signal.
#
# Usage: entropy.sh [floor|delivered|both]   (default: both)
set -uo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/../config.sh"

MODE="${1:-both}"
PORT="${LME_PORT_ENTROPY}"; URL="http://localhost:${PORT}"
NAME="${LME_NEO4J_NAME}"; BOLT="${LME_BOLT}"; PW="${LME_NEO4J_PW}"
PY="${MENHIR_FRONTIER_PY}"; BIN="${MENHIR_FRONTIER_BIN}"; SRC="${MENHIR_FRONTIER}"
EVAL="$(dirname "${BASH_SOURCE[0]}")/entropy.py"
OUT="${LME_RESULTS_DIR%/lme-ingest}/lme-entropy"; mkdir -p "$OUT"
docker start "$NAME" >/dev/null 2>&1

export LME_BOLT="bolt://localhost:${BOLT}" LME_NEO4J_PW="$PW" LME_NS_PREFIX="${LME_NS_PREFIX}" \
  LME_ENTROPY_PER_TYPE="${LME_ENTROPY_PER_TYPE}" LME_ENTROPY_K="${LME_ENTROPY_K}" \
  LME_ENTROPY_OUT="${LME_ENTROPY_OUT:-$OUT/entropy_rows.json}" MODE="$MODE"

PID=""
cleanup(){ [ -n "$PID" ] && kill "$PID" 2>/dev/null || true; }
trap cleanup EXIT

if [ "$MODE" != "floor" ]; then
  KEY="$("$PY" - "${SRC}/.env" OPENAI_API_KEY <<'PYK'
import sys; from dotenv import dotenv_values; print(dotenv_values(sys.argv[1]).get(sys.argv[2],""))
PYK
)"
  netstat -ano | grep ":$PORT" | grep -i listen | awk '{print $NF}' | sort -u | while read p; do taskkill //F //PID "$p" >/dev/null 2>&1; done
  ( export LONGMEMEVAL_VARIANT="${LONGMEMEVAL_VARIANT}" MENHIR_BENCHMARK_MODE=1 MENHIR_API_HOST=127.0.0.1 MENHIR_API_PORT="$PORT" \
      OTEL_SDK_DISABLED=true LANGFUSE_TRACING_ENABLED=false LANGFUSE_PUBLIC_KEY="" LANGFUSE_SECRET_KEY="" LANGFUSE_HOST="" \
      MENHIR_OPERATOR_KEY="" MENHIR_AGENT_KEY="" MENHIR_READONLY_KEY="" MENHIR_API_KEY="" \
      NEO4J_URI="bolt://localhost:$BOLT" NEO4J_USER=neo4j NEO4J_PASSWORD="$PW" NEO4J_DATABASE=neo4j \
      GRAPHITI_EMBED_PROVIDER=openai MEMORY_GRAPHITI_EMBED_PROVIDER=openai \
      OPENAI_API_KEY="$KEY" OPENAI_EMBED_MODEL="${LME_EMBED_MODEL}" PYTHONPATH="$SRC/src" ; \
    cd "$SRC" && "$BIN" serve --port "$PORT" ) >"$OUT/serve.log" 2>&1 & PID=$!
  for _ in $(seq 1 90); do curl -sf "$URL/api/health" >/dev/null 2>&1 && break; sleep 2; done
  curl -sf "$URL/api/health" >/dev/null 2>&1 || { echo "menhir NOT healthy; see $OUT/serve.log" >&2; exit 1; }
  export MENHIR_URL="$URL"
fi

"$PY" "$EVAL"
