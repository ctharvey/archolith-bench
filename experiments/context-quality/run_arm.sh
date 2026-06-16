#!/usr/bin/env bash
# Run one arm of the context-quality experiment.
# Usage: run_arm.sh <arm> <model> <run_n> [budget_s]
#   arm:   direct | mechanical | full   (label only)
#   model: archolith/deepseek-v4-flash-passthrough  (direct)
#          archolith/deepseek-v4-flash              (mechanical/full)
#   run_n: 1,2,3...
set -u
ARM="$1"; MODEL="$2"; RUN="$3"; BUDGET="${4:-1200}"
EXPDIR="/c/Users/thron/IdeaProjects/projects/archolith/archolith-bench/experiments/context-quality"
TASK="$EXPDIR/task-microtemplate"
TRACES="/c/Users/thron/IdeaProjects/projects/archolith/archolith-context/data/traces"
RUNDIR="$EXPDIR/runs/${ARM}-run${RUN}"
rm -rf "$RUNDIR"; mkdir -p "$RUNDIR"
# fresh task copy (stub state) -- agent works here
cp -r "$TASK/microtemplate" "$TASK/tests" "$TASK/SPEC.md" "$RUNDIR/"

PROMPT="You are implementing a feature. Read SPEC.md. Implement the render() function in microtemplate/__init__.py so that every test in tests/test_microtemplate.py passes. Run 'python -m pytest tests/ -q' to check your work, read the failures, and keep iterating until ALL 26 tests pass. Do not modify the tests."

# snapshot existing trace files
ls "$TRACES"/*.jsonl 2>/dev/null | sort > /tmp/traces_before_${ARM}_${RUN}.txt
T0=$(date +%s)
echo "[$ARM run$RUN] start $(date +%H:%M:%S) model=$MODEL budget=${BUDGET}s"
( cd "$RUNDIR" && timeout "$BUDGET" opencode run -m "$MODEL" "$PROMPT" > "$RUNDIR/agent.log" 2>&1 )
RC=$?
T1=$(date +%s)
ELAPSED=$((T1-T0))
echo "[$ARM run$RUN] agent exit=$RC elapsed=${ELAPSED}s"

# score: run the hidden suite on the agent's output
cd "$RUNDIR"
PASS=$(python -m pytest tests/ -q -p no:cacheprovider 2>/dev/null | grep -oE "[0-9]+ passed" | grep -oE "[0-9]+")
PASS=${PASS:-0}
FAILED=$(python -m pytest tests/ -q -p no:cacheprovider 2>/dev/null | grep -oE "[0-9]+ failed" | grep -oE "[0-9]+")
FAILED=${FAILED:-0}

# new trace file(s) -> sum this run's tokens + turns
ls "$TRACES"/*.jsonl 2>/dev/null | sort > /tmp/traces_after_${ARM}_${RUN}.txt
NEW=$(comm -13 /tmp/traces_before_${ARM}_${RUN}.txt /tmp/traces_after_${ARM}_${RUN}.txt)
python - "$ARM" "$RUN" "$ELAPSED" "$PASS" "$FAILED" "$RC" <<PY > "$RUNDIR/result.json"
import sys, json, glob
arm,run,elapsed,passed,failed,rc = sys.argv[1:7]
new_files = """$NEW""".split()
turns=0; up_in=up_out=hit=miss=cur=ext=emb=0
for f in new_files:
    for line in open(f, encoding="utf-8"):
        line=line.strip()
        if not line: continue
        d=json.loads(line)
        if d.get("turn_number") is None: continue
        turns+=1
        up_in += d.get("prompt_tokens_actual") or d.get("input_tokens") or 0
        up_out += d.get("output_tokens") or 0
        hit += d.get("cache_hit_tokens") or 0
        miss += d.get("cache_miss_tokens") or 0
        cur += (d.get("curator_prompt_tokens") or 0)+(d.get("curator_completion_tokens") or 0)
        ext += (d.get("extractor_prompt_tokens") or 0)+(d.get("extractor_completion_tokens") or 0)
        emb += d.get("embedding_tokens") or 0
res=dict(arm=arm,run=int(run),elapsed_s=int(elapsed),tests_passed=int(passed),
         tests_failed=int(failed),agent_exit=int(rc),proxy_turns=turns,
         upstream_in=up_in,upstream_out=up_out,cache_hit=hit,cache_miss=miss,
         helper_curator=cur,helper_extractor=ext,helper_embedding=emb,
         trace_files=[f.split("/")[-1] for f in new_files])
print(json.dumps(res,indent=2))
PY
echo "[$ARM run$RUN] RESULT:"; cat "$RUNDIR/result.json"
