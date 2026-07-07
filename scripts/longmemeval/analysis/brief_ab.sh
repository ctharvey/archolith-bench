#!/usr/bin/env bash
# Brief A/B: does the BriefBuilder (appended temporal Timeline) beat the flat relevance brief?
#
# Serves menhir-frontier twice over the PRE-BUILT graph — MENHIR_FRONTIER_BRIEF_BUILDER off then
# on — collecting /api/context briefs each time (free), then answers + judges both sets.
# The recall-only harness cannot measure this (it feeds /api/recall, never /api/context).
#
# Collection is free; the score phase spends OpenAI (answer + judge). Set RUN_SCORE=1 to score;
# omit it to only collect + eyeball the briefs first.
#
# Usage: brief_ab.sh            # collect only (no spend)
#        RUN_SCORE=1 brief_ab.sh  # collect + score
set -uo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/../config.sh"

PORT="${LME_PORT_BRIEF}"; URL="http://localhost:${PORT}"
OUT="${LME_RESULTS_DIR%/lme-ingest}/lme-brief-ab"; mkdir -p "$OUT"
NAME="${LME_NEO4J_NAME}"; BOLT="${LME_BOLT}"; PW="${LME_NEO4J_PW}"
PY="${MENHIR_FRONTIER_PY}"; BIN="${MENHIR_FRONTIER_BIN}"; SRC="${MENHIR_FRONTIER}"
EVAL="$(dirname "${BASH_SOURCE[0]}")/brief_ab.py"

KEY="$("$PY" - "${SRC}/.env" OPENAI_API_KEY <<'PYK'
import sys; from dotenv import dotenv_values; print(dotenv_values(sys.argv[1]).get(sys.argv[2],""))
PYK
)"; [ -n "$KEY" ] || { echo "no OPENAI_API_KEY in ${SRC}/.env" >&2; exit 1; }
docker start "$NAME" >/dev/null 2>&1

serve(){ # $1 = true|false brief flag
  netstat -ano | grep ":$PORT" | grep -i listen | awk '{print $NF}' | sort -u | while read p; do taskkill //F //PID "$p" >/dev/null 2>&1; done
  ( export LONGMEMEVAL_VARIANT="${LONGMEMEVAL_VARIANT}" MENHIR_BENCHMARK_MODE=1 MENHIR_API_HOST=127.0.0.1 MENHIR_API_PORT="$PORT" \
      OTEL_SDK_DISABLED=true LANGFUSE_TRACING_ENABLED=false LANGFUSE_PUBLIC_KEY="" LANGFUSE_SECRET_KEY="" LANGFUSE_HOST="" \
      MENHIR_OPERATOR_KEY="" MENHIR_AGENT_KEY="" MENHIR_READONLY_KEY="" MENHIR_API_KEY="" \
      NEO4J_URI="bolt://localhost:$BOLT" NEO4J_USER=neo4j NEO4J_PASSWORD="$PW" NEO4J_DATABASE=neo4j \
      GRAPHITI_EMBED_PROVIDER=openai MEMORY_GRAPHITI_EMBED_PROVIDER=openai \
      OPENAI_API_KEY="$KEY" OPENAI_EMBED_MODEL="${LME_EMBED_MODEL}" PYTHONPATH="$SRC/src" \
      MENHIR_FRONTIER_BRIEF_BUILDER="$1" ; \
    cd "$SRC" && "$BIN" serve --port "$PORT" ) >"$OUT/serve_$1.log" 2>&1 &
  for _ in $(seq 1 90); do curl -sf "$URL/api/health" >/dev/null 2>&1 && break; sleep 2; done
  curl -sf "$URL/api/health" >/dev/null 2>&1 || { echo "menhir NOT healthy ($1); see $OUT/serve_$1.log" >&2; exit 1; }
}

# Common env for the eval (constant across phases); MODE/BRIEF_TAG set per call.
export MENHIR_URL="$URL" OPENAI_API_KEY="$KEY" BRIEF_OUT_DIR="$OUT" \
  BRIEF_PER_TYPE="${LME_BRIEF_PER_TYPE}" BRIEF_TYPES="${LME_BRIEF_TYPES}" \
  ANSWER_MODEL="${LME_ANSWER_MODEL}" JUDGE_MODEL="${LME_JUDGE_MODEL}"

echo "=== collect briefs OFF (no OpenAI spend) ==="
serve false
MODE=collect BRIEF_TAG=off "$PY" "$EVAL"

echo "=== collect briefs ON (no OpenAI spend) ==="
serve true
MODE=collect BRIEF_TAG=on "$PY" "$EVAL"

netstat -ano | grep ":$PORT" | grep -i listen | awk '{print $NF}' | sort -u | while read p; do taskkill //F //PID "$p" >/dev/null 2>&1; done

if [ "${RUN_SCORE:-0}" = "1" ]; then
  echo "=== score both (answer=${LME_ANSWER_MODEL}, judge=${LME_JUDGE_MODEL}) ==="
  MODE=score "$PY" "$EVAL"
else
  echo "collected -> $OUT  (set RUN_SCORE=1 to answer+judge; costs OpenAI tokens)"
fi
