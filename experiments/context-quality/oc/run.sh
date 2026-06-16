#!/usr/bin/env bash
ARM="$1"; MODEL="$2"
WORK="$(cd "$(dirname "$0")" && pwd)/$ARM"
GOAL="$(cat "$(dirname "$0")/GOAL.txt")"
mkdir -p "$WORK"; cd "$WORK"
echo "[$ARM] start $(date +%H:%M:%S) model=$MODEL cwd=$WORK"
T0=$(date +%s)
timeout 1500 opencode run -m "$MODEL" "$GOAL" > agent.log 2>&1
echo "[$ARM] exit=$? elapsed=$(( $(date +%s)-T0 ))s $(date +%H:%M:%S)"
