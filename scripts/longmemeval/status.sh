#!/usr/bin/env bash
# Read-only progress tracker for the LongMemEval persistent-graph ingest.
# Queries the LME Neo4j (Neo4j 5.x MVCC -> reads are safe to run
# concurrently with the ingest writes) plus the resume manifest. Does NOT write to
# the graph and does NOT block the ingest.
#
# Usage:
#   status.sh                 # one-shot snapshot
#   status.sh watch [secs]    # repeat every <secs> (default 30), also logs
#                              # one summary line to results/lme-ingest/progress.log
set -uo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/config.sh"

MANIFEST="${LME_RESULTS_DIR}/manifest.json"
EXPECTED="${LME_RESULTS_DIR}/expected_turns.json"
PROGRESS_LOG="${LME_RESULTS_DIR}/progress.log"

manifest_done() {
  if [ -f "$MANIFEST" ] && [ -s "$MANIFEST" ]; then
    WIN_MANIFEST="$(cygpath -m "$MANIFEST")"
    python -c "import json; print(len(json.load(open('${WIN_MANIFEST}'))))" 2>/dev/null || echo 0
  else
    echo 0
  fi
}

snapshot() {
  local ts done rows
  ts="$(date '+%Y-%m-%d %H:%M:%S')"
  done="$(manifest_done)"

  # Per-namespace processing breakdown (read-only; Neo4j 5.x MVCC -> safe mid-ingest).
  rows="$(docker exec "${LME_NEO4J_NAME}" cypher-shell -u neo4j -p "${LME_NEO4J_PW}" --format plain \
"MATCH (e:Episodic) RETURN e.namespace AS ns, count(*) AS total,
 sum(CASE WHEN e.processing_state='READY' THEN 1 ELSE 0 END) AS ready,
 sum(CASE WHEN e.processing_state='ENRICHING' THEN 1 ELSE 0 END) AS enriching,
 sum(CASE WHEN e.processing_state='FAILED' THEN 1 ELSE 0 END) AS failed
 ORDER BY ns;" 2>/dev/null)"

  if [ -z "$rows" ]; then
    echo "[$ts] items_done=$done | graph: (no episodes / neo4j unreachable)"
    return
  fi

  # Format with python so each namespace shows episodes X / N (expected turns) and an
  # overall line against the full-set expected total. Falls back gracefully if the
  # expected_turns.json cache is missing.
  # Pass rows via env (not stdin): `python -` reads its program from stdin/heredoc,
  # so piping data to stdin would be swallowed by the heredoc.
  ROWS="$rows" python - "$ts" "$done" "$(cygpath -m "$EXPECTED")" <<'PY'
import sys, os, json
ts, done, exp_path = sys.argv[1], sys.argv[2], sys.argv[3]
try:
    exp = json.load(open(exp_path))
except Exception:
    exp = {}
total_expected = exp.get("__total__")
n_items = sum(1 for k in exp if k != "__total__") or None
lines = [l for l in os.environ.get("ROWS", "").splitlines() if l.strip()]
data = []
for l in lines[1:]:  # drop header row
    p = [x.strip().strip('"') for x in l.split(", ")]
    if len(p) < 5:
        continue
    ns = p[0]
    t, r, e, f = (int(v or 0) for v in p[1:5])
    data.append((ns, t, r, e, f))
tt = sum(d[1] for d in data); tr = sum(d[2] for d in data)
te = sum(d[3] for d in data); tf = sum(d[4] for d in data)
done_str = f"{done}/{n_items}" if n_items else done
ep_str = f"{tt}/{total_expected}" if total_expected else str(tt)
print(f"[{ts}] items_done={done_str} | episodes={ep_str} ready={tr} enriching={te} failed={tf} active_ns={len(data)}")
for ns, t, r, e, f in data:
    n = exp.get(ns)
    frac = f"{t}/{n}" if n else str(t)
    pct = f" ({100*t/n:.0f}%)" if n else ""
    print(f"    {ns:<16} episodes={frac}{pct} ready={r} enriching={e} failed={f}")
PY
}

if [ "${1:-}" = "watch" ]; then
  INTERVAL="${2:-30}"
  mkdir -p "$(dirname "$PROGRESS_LOG")"
  echo "watching every ${INTERVAL}s -> Ctrl-C to stop. summary lines appended to $PROGRESS_LOG"
  while true; do
    out="$(snapshot)"
    printf '%s\n\n' "$out"
    # append only the one-line summary (first line) to the durable log
    printf '%s\n' "$out" | head -1 >> "$PROGRESS_LOG"
    sleep "$INTERVAL"
  done
else
  snapshot
fi
