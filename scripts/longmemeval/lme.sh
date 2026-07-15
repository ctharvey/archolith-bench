#!/usr/bin/env bash
# LongMemEval framework dispatcher — the main entry point for all operations.
#
# Usage:
#   lme.sh build [N]                   # build persistent graph (default N=30)
#   lme.sh promote                     # flip SESSION -> PERSISTENT (regular memories)
#   lme.sh backfill-dates [--dry-run]  # repair valid_at from real session dates (no re-ingest)
#   lme.sh recall-ab <branch|path> [N] # recall-only A/B on built graph
#   lme.sh buildout-ab [N]             # ingest A/B (main vs frontier, fresh graphs)
#   lme.sh backup                      # dump the persistent graph
#   lme.sh restore                     # restore the persistent graph from backup
#   lme.sh status [watch [secs]]       # read-only progress tracker
#   lme.sh retry                       # reset+drain FAILED episodes
#   lme.sh matrix [per_type]           # answer-accuracy matrix (analysis)
#   lme.sh msc <config>                # minimal-sufficient-context sweep (analysis)
#   lme.sh ablation                    # per-oracle ablation (analysis)
#   lme.sh presence                    # retrieval quality (analysis)
#   lme.sh brief-ab [--score]          # BriefBuilder A/B (flat vs +Timeline); --score spends OpenAI
#   lme.sh entropy [floor|both]        # D0 retrieval-entropy instrument (GPT-free fitness function)
#   lme.sh probe <question_id>         # single-question recall ranking trace
#   lme.sh ir-gate                     # M1 gate verdict + artifacts (Phase 4, JSON + Markdown)
#   lme.sh -h|--help                   # show this help

set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/config.sh"

usage(){
  sed -n '2,21p' "${BASH_SOURCE[0]}" | sed 's/^# //'
  exit "${1:-0}"
}

COMMAND="${1:-}"
[ -n "$COMMAND" ] || usage 1

case "$COMMAND" in
  build)
    "${_LONGMEMEVAL_DIR}/build_graph.sh" "${2:-30}"
    ;;
  promote)
    "${_LONGMEMEVAL_DIR}/promote_persistent.sh"
    ;;
  backfill-dates)
    [ "${2:-}" = "--dry-run" ] && export DRY_RUN=1
    LME_BOLT="${LME_BOLT}" LME_NEO4J_PW="${LME_NEO4J_PW}" LME_NS_PREFIX="${LME_NS_PREFIX}" \
      LME_REVERT_SNAPSHOT="${LME_REVERT_SNAPSHOT:-${LME_RESULTS_DIR}/date-backfill-revert.json}" \
      "${MENHIR_FRONTIER_PY}" "${_LONGMEMEVAL_DIR}/lib/backfill_dates.py"
    ;;
  recall-ab)
    if [ -z "${2:-}" ]; then echo "usage: lme.sh recall-ab <branch|path> [limit]" >&2; exit 1; fi
    "${_LONGMEMEVAL_DIR}/recall_ab.sh" "$2" "${3:-30}"
    ;;
  buildout-ab)
    "${_LONGMEMEVAL_DIR}/buildout_ab.sh" "${2:-30}"
    ;;
  backup)
    "${_LONGMEMEVAL_DIR}/backup_graph.sh"
    ;;
  restore)
    "${_LONGMEMEVAL_DIR}/backup_graph.sh" restore
    ;;
  status)
    "${_LONGMEMEVAL_DIR}/status.sh" "${2:-}" "${3:-}"
    ;;
  retry)
    "${_LONGMEMEVAL_DIR}/retry.sh"
    ;;
  matrix)
    "${_LONGMEMEVAL_DIR}/analysis/answer_matrix.sh" "${2:-}"
    ;;
  msc)
    if [ -z "${2:-}" ]; then echo "usage: lme.sh msc <config>" >&2; exit 1; fi
    "${_LONGMEMEVAL_DIR}/analysis/msc_sweep.sh" "$2"
    ;;
  ablation)
    "${_LONGMEMEVAL_DIR}/analysis/ablation_sweep.sh"
    ;;
  presence)
    MENHIR_URL="http://localhost:${LME_PORT_RQ}" "${MENHIR_FRONTIER_PY}" "${_LONGMEMEVAL_DIR}/analysis/lib/retrieval_quality.py"
    ;;
  brief-ab)
    [ "${2:-}" = "--score" ] && export RUN_SCORE=1
    "${_LONGMEMEVAL_DIR}/analysis/brief_ab.sh"
    ;;
  entropy)
    "${_LONGMEMEVAL_DIR}/analysis/entropy.sh" "${2:-both}"
    ;;
  probe)
    if [ -z "${2:-}" ]; then echo "usage: lme.sh probe <question_id>" >&2; exit 1; fi
    "${_LONGMEMEVAL_DIR}/lib/recall_probe.sh" "$2"
    ;;
  ir-gate)
    # Phase 4: M1 gate verdict + artifacts (JSON + Markdown)
    # Requires a running menhir server on LME_PORT_RQ and the persistent graph already built.
    # Emits gate verdict block + JSON/Markdown artifacts to results/lme-gate/
    MENHIR_URL="http://localhost:${LME_PORT_RQ}" \
      MENHIR_MAIN="${MENHIR_MAIN}" \
      LME_RUN_ID="${LME_RUN_ID:-}" \
      LME_GRAPH_FRESH="${LME_GRAPH_FRESH:-false}" \
      "${MENHIR_FRONTIER_PY}" "${_LONGMEMEVAL_DIR}/analysis/lib/retrieval_quality.py"
    ;;
  -h|--help)
    usage 0
    ;;
  *)
    echo "unknown command: $COMMAND" >&2
    usage 1
    ;;
esac
