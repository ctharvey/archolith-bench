"""Precompute expected episode (turn) counts per LongMemEval item so the progress
tracker can show `episodes X / N` instead of a bare growing number.

Expected episodes for an item == number of haystack turns with non-empty content,
which is exactly how _ingest_lme.py counts `turns` and how menhir creates one
Episodic node per ingested turn. Writes results/lme-ingest/expected_turns.json:
  { "lme-<question_id>": <expected_turns>, ..., "__total__": <sum> }
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Real Windows path from this file's location (see _ingest_lme.py: a "/c/Users/..."
# default is misread by Windows Python open() as C:\c\Users\...).
BENCH_DIR = str(Path(__file__).resolve().parents[1])
if BENCH_DIR not in sys.path:
    sys.path.insert(0, BENCH_DIR)

from archolith_bench.harness.longmemeval import LongMemEvalMemoryAdapter  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=500)
    ap.add_argument("--out", default=f"{BENCH_DIR}/results/lme-ingest/expected_turns.json")
    args = ap.parse_args()

    adapter = LongMemEvalMemoryAdapter()
    items = adapter.load_items(limit=args.limit)

    expected: dict[str, int] = {}
    total = 0
    for n, item in enumerate(items):
        qid = str(item.get("question_id") or f"lme-{n}")
        turns = sum(
            1
            for session in adapter.sessions(item)
            for turn in session
            if turn.get("content", "")
        )
        expected[f"lme-{qid}"] = turns
        total += turns
    expected["__total__"] = total

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(expected, indent=2), encoding="utf-8")
    print(f"wrote {len(expected) - 1} items, total_expected_episodes={total} -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
