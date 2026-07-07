#!/usr/bin/env bash
# Minimal-Sufficient-Context sweep: accuracy vs recall top-k on the strongest config.
# One sweep yields BOTH curves — accuracy vs memory-COUNT (k) and accuracy vs TOKENS
# (mean input tokens per k). Their divergence = over-fragmentation. Config chosen by arg
# (default node_plain, the matrix winner). Stratified: all 6 types x LME_PER_TYPE per k.
set -uo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/../config.sh"

CFG="${1:-node_plain}"
PER="${LME_PER_TYPE:-10}"
KS="1 2 3 5 10"
PORT="${LME_PORT_MSC}"
URL="http://localhost:$PORT"
KEY="$("${MENHIR_MAIN_PY}" - "${MENHIR_MAIN}/.env" OPENAI_API_KEY <<'PY'
import sys; from dotenv import dotenv_values; print(dotenv_values(sys.argv[1]).get(sys.argv[2],""))
PY
)"
TYPES="temporal-reasoning multi-session knowledge-update single-session-user single-session-assistant single-session-preference"
LOG="${BENCH_DIR}/results/lme-msc/analysis.log"
mkdir -p "$(dirname "$LOG")"
: > "$LOG"
log(){ printf '[msc] %s %s\n' "$(date '+%F %H:%M:%S')" "$*" | tee -a "$LOG"; }

# config env
case "$CFG" in
  node_plain) FE=false; MODE=standalone; ORACLE=false ;;
  frontier)   FE=false; MODE=standalone; ORACLE=true ;;
  pointer)    FE=true;  MODE=pointer;    ORACLE=true ;;
  *) echo "unknown config $CFG"; exit 1 ;;
esac

netstat -ano | grep ":$PORT" | grep -i listen | awk '{print $NF}' | sort -u | while read p; do taskkill //F //PID "$p" >/dev/null 2>&1; done
docker start "${LME_NEO4J_NAME}" >/dev/null 2>&1
for _ in $(seq 1 40); do docker exec "${LME_NEO4J_NAME}" cypher-shell -u neo4j -p "${LME_NEO4J_PW}" "RETURN 1" >/dev/null 2>&1 && break; sleep 2; done
( export LONGMEMEVAL_VARIANT=oracle MENHIR_BENCHMARK_MODE=1 MENHIR_API_HOST=127.0.0.1 MENHIR_API_PORT="$PORT" \
    OTEL_SDK_DISABLED=true LANGFUSE_TRACING_ENABLED=false LANGFUSE_PUBLIC_KEY="" LANGFUSE_SECRET_KEY="" LANGFUSE_HOST="" \
    MENHIR_OPERATOR_KEY="" MENHIR_AGENT_KEY="" MENHIR_READONLY_KEY="" MENHIR_API_KEY="" \
    NEO4J_URI="bolt://localhost:${LME_BOLT}" NEO4J_USER=neo4j NEO4J_PASSWORD="${LME_NEO4J_PW}" NEO4J_DATABASE=neo4j \
    GRAPHITI_EMBED_PROVIDER=openai MEMORY_GRAPHITI_EMBED_PROVIDER=openai \
    OPENAI_API_KEY="$KEY" OPENAI_EMBED_MODEL="${LME_EMBED_MODEL}" PYTHONPATH="${MENHIR_FRONTIER}/src" \
    MENHIR_FRONTIER_FACT_EDGES="$FE" MENHIR_FRONTIER_FACT_EDGE_MODE="$MODE" MENHIR_FRONTIER_ORACLE_RANKING="$ORACLE" ; \
  cd "${MENHIR_FRONTIER}" && "${MENHIR_FRONTIER_BIN}" serve --port "$PORT" ) >>"$LOG" 2>&1 & PID=$!
for _ in $(seq 1 90); do curl -sf "$URL/api/health" >/dev/null 2>&1 && break; sleep 2; done
curl -sf "$URL/api/health" >/dev/null 2>&1 || { log "NOT healthy"; kill $PID; exit 1; }
log "===== MSC SWEEP cfg=$CFG (fe=$FE mode=$MODE oracle=$ORACLE) ks={$KS} PER=$PER ====="

for K in $KS; do
  cor=0; tot=0; intok=0
  for T in $TYPES; do
    OUT="${BENCH_DIR}/results/lme-msc-$CFG-k$K-$T"; mkdir -p "$OUT"
    ( cd "${BENCH_DIR}" && UPSTREAM_BASE_URL="https://api.openai.com/v1" UPSTREAM_API_KEY="$KEY" \
        BENCHMARK_MODEL="${LME_ANSWER_MODEL}" OPENAI_API_KEY="$KEY" LONGMEMEVAL_VARIANT=oracle LME_RECALL_LIMIT="$K" \
        "${BENCH_BIN}" harness longmemeval-menhir --menhir-url "$URL" --recall-only \
          --subset "$T" --model "${LME_ANSWER_MODEL}" --scorer "${LME_SCORER}" --judge-model "${LME_JUDGE_MODEL}" \
          --format markdown --output-dir "$OUT" --out "$OUT/harness.md" --limit "$PER" ) >>"$LOG" 2>&1
    # parse "menhir_recall | N | score | input | ..." row
    read -r n sc intk < <(grep -oE "menhir_recall \| [0-9]+ \| [0-9.]+ \| [0-9,]+" "$OUT/harness.md" 2>/dev/null | head -1 | tr -d ',' | awk -F'|' '{print $2, $3, $4}')
    n=${n:-0}; sc=${sc:-0}; intk=${intk:-0}
    c=$(awk "BEGIN{printf \"%d\", ($sc*$n)+0.5}")
    cor=$((cor + c)); tot=$((tot + n)); intok=$((intok + intk))
  done
  acc=$(awk "BEGIN{printf \"%.3f\", ($tot>0)?$cor/$tot:0}")
  meantok=$(awk "BEGIN{printf \"%d\", ($tot>0)?$intok/$tot:0}")
  log "k=$K  acc=$acc  ($cor/$tot)  mean_input_tokens=$meantok"
done
log "===== MSC DONE ====="
echo "__MSC_COMPLETE__" | tee -a "$LOG"
kill $PID 2>/dev/null || true
