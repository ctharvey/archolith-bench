#!/usr/bin/env bash
# Phase-4 cache-economics measurement: both scenarios, N=3, full length, both arms.
# Cost focus: --no-probes --no-restart (quality/continuity measures are orthogonal to
# the cost verdict and add upstream spend). Provider deepseek-v4-flash drives the live
# upstream + the live summary; traces are re-priced across the ladder afterward.
set -u
cd "$(dirname "$0")"
ROOT="results/phase4-$(date +%Y%m%d)"
LOG="$ROOT/run.log"
mkdir -p "$ROOT"
echo "[phase4] start $(date)" | tee "$LOG"

for n in 1 2 3; do
  for scen in long_agent taskflow; do
    OUT="$ROOT/run${n}/${scen}"
    mkdir -p "$OUT"
    echo "[phase4] run${n} ${scen} -> $OUT  $(date)" | tee -a "$LOG"
    python -m archolith_bench.cli proxy \
      --scenario "scenarios/${scen}.json" \
      --arms proxy_plus_filter,direct \
      --provider deepseek-v4-flash \
      --no-probes --no-restart \
      --output-dir "$OUT" >> "$LOG" 2>&1
    rc=$?
    echo "[phase4] run${n} ${scen} exit=$rc  $(date)" | tee -a "$LOG"
    # 429s on DeepSeek/OpenAI are NOT a hard breaker for this run (the metered-API
    # 429 protocol is for PokemonPriceTracker/eBay/TCGPlayer). The bench degrades
    # per-turn on an [ERROR 429] anyway; just note it and keep going.
    if grep -qiE "rate.?limit|429|too many requests" "$LOG"; then
      echo "[phase4] note: rate-limit text seen in log — continuing (not a hard stop)  $(date)" | tee -a "$LOG"
    fi
    if [ $rc -ne 0 ]; then
      echo "[phase4] non-zero exit — stopping  $(date)" | tee -a "$LOG"
      exit $rc
    fi
  done
done
echo "[phase4] ALL RUNS COMPLETE $(date)" | tee -a "$LOG"
