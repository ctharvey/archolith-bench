#!/usr/bin/env bash
# LongMemEval framework configuration — centralized, environment-overridable.
# Source this in every script; all values use ${VAR:-default} for override.
#
# Usage:
#   source "$(dirname "${BASH_SOURCE[0]}")/config.sh"
#   echo "Build port: $LME_PORT_BUILD"
#   LME_ANSWER_MODEL=gpt-4-turbo ./recall_ab.sh main 30

# ---- Paths (derived from script location, not hardcoded absolutes) ----
# All path derivations should use git rev-parse --show-toplevel where possible.
# This file is sourced from scripts/longmemeval/, so $(dirname) gives us that dir.
# Parent of parent is archolith-bench root.
SCRIPT_DIR="${SCRIPT_DIR:-$(dirname "${BASH_SOURCE[0]}")}"
_LONGMEMEVAL_DIR="$(cd "${SCRIPT_DIR}" && pwd)"
BENCH_DIR="${BENCH_DIR:-$(git rev-parse --show-toplevel)}"
ARCH_DIR="${ARCH_DIR:-${BENCH_DIR%/*}}"  # parent of archolith-bench
MENHIR_MAIN="${MENHIR_MAIN:-${ARCH_DIR}/menhir}"
MENHIR_FRONTIER="${MENHIR_FRONTIER:-${ARCH_DIR}/menhir-frontier}"

# ---- Neo4j (persistent LME graph) ----
LME_NEO4J_NAME="${LME_NEO4J_NAME:-menhir-lme-neo4j}"
LME_BOLT="${LME_BOLT:-7689}"
LME_HTTP="${LME_HTTP:-7476}"
LME_NEO4J_PW="${LME_NEO4J_PW:-lmedata123}"
LME_NEO4J_VOL="${LME_NEO4J_VOL:-menhir-lme-data}"
LME_NEO4J_IMAGE="${LME_NEO4J_IMAGE:-neo4j:5.26-community}"

# ---- Menhir serve ports (one per workflow) ----
LME_PORT_BUILD="${LME_PORT_BUILD:-8102}"               # build_graph.sh
LME_PORT_RECALL="${LME_PORT_RECALL:-8103}"             # recall_ab.sh (shared persistent graph)
LME_PORT_BUILDOUT_MAIN="${LME_PORT_BUILDOUT_MAIN:-8105}"       # buildout_ab.sh (main branch, fresh graph)
LME_PORT_BUILDOUT_FRONTIER="${LME_PORT_BUILDOUT_FRONTIER:-8106}" # buildout_ab.sh (frontier, fresh graph)

# ---- Analysis ports (answer matrix, MSC sweep, ablation, retrieval quality) ----
LME_PORT_MATRIX="${LME_PORT_MATRIX:-8112}"             # analysis/answer_matrix.sh
LME_PORT_MSC="${LME_PORT_MSC:-8113}"                   # analysis/msc_sweep.sh
LME_PORT_ABL="${LME_PORT_ABL:-8114}"                   # analysis/ablation_sweep.sh
LME_PORT_RQ="${LME_PORT_RQ:-8109}"                     # analysis/lib/retrieval_quality.py

# ---- Models ----
LME_EXTRACT_MODEL="${LME_EXTRACT_MODEL:-gpt-4-1-nano}"
LME_ANSWER_MODEL="${LME_ANSWER_MODEL:-gpt-4o}"
LME_JUDGE_MODEL="${LME_JUDGE_MODEL:-gpt-4o-mini}"
LME_EMBED_MODEL="${LME_EMBED_MODEL:-text-embedding-3-small}"
LME_SCORER="${LME_SCORER:-llm-judge}"

# ---- Dataset and limits ----
LME_NS_PREFIX="${LME_NS_PREFIX:-lme-}"               # namespace prefix for all LME graphs (promote scope filter)
LME_DATASET="${LME_DATASET:-xiaowu0162/longmemeval}"
LONGMEMEVAL_VARIANT="${LONGMEMEVAL_VARIANT:-oracle}"
LME_LIMIT="${LME_LIMIT:-30}"
LME_RECALL_LIMIT="${LME_RECALL_LIMIT:-10}"            # recall top-k (menhir_client default is 10)
LME_PER_TYPE="${LME_PER_TYPE:-15}"                    # stratified sample size per question type

# ---- Backup and results ----
LME_BACKUP_DIR="${LME_BACKUP_DIR:-C:/Users/thron/menhir-lme-backup}"
LME_RESULTS_DIR="${LME_RESULTS_DIR:-${BENCH_DIR}/results/lme-ingest}"

# ---- Virtual environment bins (derived from paths above) ----
MENHIR_MAIN_PY="${MENHIR_MAIN_PY:-${MENHIR_MAIN}/.venv/Scripts/python.exe}"
MENHIR_MAIN_BIN="${MENHIR_MAIN_BIN:-${MENHIR_MAIN}/.venv/Scripts/menhir}"
MENHIR_FRONTIER_PY="${MENHIR_FRONTIER_PY:-${MENHIR_FRONTIER}/.venv/Scripts/python.exe}"
MENHIR_FRONTIER_BIN="${MENHIR_FRONTIER_BIN:-${MENHIR_FRONTIER}/.venv/Scripts/menhir}"
BENCH_PY="${BENCH_PY:-${BENCH_DIR}/.venv/Scripts/python.exe}"
BENCH_BIN="${BENCH_BIN:-${BENCH_DIR}/.venv/Scripts/archolith-bench}"
