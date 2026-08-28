#!/usr/bin/env bash
# Per-oracle ablation × question-type -> the routing table (MARGINAL effects, not optimal weights).
# Add-one-in ladder from the winning node_plain baseline, so each arm isolates one frontier
# component's marginal contribution. evidence_anchor is tested UNDER warden_gate (where it can
# actually drop candidates). fact_edges OFF throughout to isolate oracle effects.
#
# Arms (label:OR:IL:EA:WG:BG:CI:DG) — OracleRanking IntentLens EvidenceAnchor WardenGate
#                                     BeliefGate Contradiction DiversityGate
set -uo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/../config.sh"

PER="${LME_PER_TYPE:-10}"
ARMS=(
  "node_plain:false:false:false:false:false:false:false"     # reference (matrix winner)
  "oracle:true:false:false:false:false:false:false"          # + combiner reorder only
  "oracle_lens:true:true:false:false:false:false:false"      # + intent lens
  "gate_ea:true:true:true:true:false:false:false"            # + warden gate WITH evidence-anchor
  "gate_noea:true:true:false:true:false:false:false"         # + warden gate WITHOUT evidence-anchor
  "aggressive:true:true:true:true:true:true:true"            # + belief + contradiction + diversity
)
PORT="${LME_PORT_ABL}"
URL="http://localhost:$PORT"
KEY="$("${MENHIR_MAIN_PY}" - "${BENCH_DIR}/.env" OPENAI_API_KEY <<'PY'
import sys; from dotenv import dotenv_values; print(dotenv_values(sys.argv[1]).get(sys.argv[2],""))
PY
)"
TYPES="temporal-reasoning multi-session knowledge-update single-session-user single-session-assistant single-session-preference"
LOG="${BENCH_DIR}/results/lme-ablation/analysis.log"
mkdir -p "$(dirname "$LOG")"
: > "$LOG"
log(){ printf '[abl] %s %s\n' "$(date '+%F %H:%M:%S')" "$*" | tee -a "$LOG"; }

serve(){ # OR IL EA WG BG CI DG
  netstat -ano | grep ":$PORT" | grep -i listen | awk '{print $NF}' | sort -u | while read p; do taskkill //F //PID "$p" >/dev/null 2>&1; done
  docker start "${LME_NEO4J_NAME}" >/dev/null 2>&1
  for _ in $(seq 1 40); do docker exec "${LME_NEO4J_NAME}" cypher-shell -u neo4j -p "${LME_NEO4J_PW}" "RETURN 1" >/dev/null 2>&1 && break; sleep 2; done
  ( export LONGMEMEVAL_VARIANT=oracle MENHIR_BENCHMARK_MODE=1 MENHIR_API_HOST=127.0.0.1 MENHIR_API_PORT="$PORT" \
      OTEL_SDK_DISABLED=true LANGFUSE_TRACING_ENABLED=false LANGFUSE_PUBLIC_KEY="" LANGFUSE_SECRET_KEY="" LANGFUSE_HOST="" \
      MENHIR_OPERATOR_KEY="" MENHIR_AGENT_KEY="" MENHIR_READONLY_KEY="" MENHIR_API_KEY="" \
      NEO4J_URI="bolt://localhost:${LME_BOLT}" NEO4J_USER=neo4j NEO4J_PASSWORD="${LME_NEO4J_PW}" NEO4J_DATABASE=neo4j \
      GRAPHITI_EMBED_PROVIDER=openai MEMORY_GRAPHITI_EMBED_PROVIDER=openai \
      OPENAI_API_KEY="$KEY" OPENAI_EMBED_MODEL="${LME_EMBED_MODEL}" PYTHONPATH="${MENHIR_FRONTIER}/src" \
      MENHIR_FRONTIER_FACT_EDGES=false \
      MENHIR_FRONTIER_ORACLE_RANKING="$1" MENHIR_FRONTIER_INTENT_LENS="$2" \
      MENHIR_FRONTIER_EVIDENCE_ANCHOR="$3" MENHIR_FRONTIER_WARDEN_GATE="$4" \
      MENHIR_FRONTIER_BELIEF_GATE="$5" MENHIR_FRONTIER_CONTRADICTION_INTERRUPT="$6" \
      MENHIR_FRONTIER_DIVERSITY_GATE="$7" ; \
    cd "${MENHIR_FRONTIER}" && "${MENHIR_FRONTIER_BIN}" serve --port "$PORT" ) >>"$LOG" 2>&1 & echo $!
}

log "===== ORACLE ABLATION (arms x 6 types x $PER) ====="
for SPEC in "${ARMS[@]}"; do
  IFS=: read -r LABEL OR IL EA WG BG CI DG <<< "$SPEC"
  PID=$(serve "$OR" "$IL" "$EA" "$WG" "$BG" "$CI" "$DG")
  for _ in $(seq 1 90); do curl -sf "$URL/api/health" >/dev/null 2>&1 && break; sleep 2; done
  curl -sf "$URL/api/health" >/dev/null 2>&1 || { log "$LABEL: NOT healthy"; kill "$PID" 2>/dev/null; continue; }
  log "$LABEL: up (OR=$OR IL=$IL EA=$EA WG=$WG BG=$BG CI=$CI DG=$DG)"
  cor=0; tot=0
  for T in $TYPES; do
    OUT="${BENCH_DIR}/results/lme-abl-$LABEL-$T"; mkdir -p "$OUT"
    ( cd "${BENCH_DIR}" && UPSTREAM_BASE_URL="https://api.openai.com/v1" UPSTREAM_API_KEY="$KEY" \
        BENCHMARK_MODEL="${LME_ANSWER_MODEL}" OPENAI_API_KEY="$KEY" LONGMEMEVAL_VARIANT=oracle \
        "${BENCH_BIN}" harness longmemeval-menhir --menhir-url "$URL" --recall-only \
          --subset "$T" --model "${LME_ANSWER_MODEL}" --scorer "${LME_SCORER}" --judge-model "${LME_JUDGE_MODEL}" \
          --format markdown --output-dir "$OUT" --out "$OUT/harness.md" --limit "$PER" ) >>"$LOG" 2>&1
    read -r n sc < <(grep -oE "menhir_recall \| [0-9]+ \| [0-9.]+" "$OUT/harness.md" 2>/dev/null | head -1 | awk -F'|' '{print $2, $3}')
    n=${n:-0}; sc=${sc:-0}
    c=$(awk "BEGIN{printf \"%d\", ($sc*$n)+0.5}")
    cor=$((cor+c)); tot=$((tot+n))
    log "  $LABEL/$T: score=$sc"
  done
  acc=$(awk "BEGIN{printf \"%.3f\", ($tot>0)?$cor/$tot:0}")
  log "$LABEL: AVG=$acc ($cor/$tot)"
  kill "$PID" 2>/dev/null || true; sleep 2
done
log "===== ABLATION DONE ====="
echo "__ABLATION_COMPLETE__" | tee -a "$LOG"
