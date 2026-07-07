"""Arm C delta report — diff two D0 entropy runs around a gated-perception write pass.

The read half of the capstone measurement (write half: `perception_write.py`). Takes the BASELINE
and POST entropy rows (produced by `entropy.sh both` / `entropy.py` with LME_ENTROPY_OUT set) plus
the write manifest, and reports, per slice:

  * counting slice — the honest collapse: per-qid DELIVERED transitions (rank/memories/tokens,
    censored->reached), medians before/after, split by whether the gate WROTE into that namespace
    (abstained namespaces are the control: they must be unchanged).
  * held-out slice — the Goodhart guard: a true-but-irrelevant committed View must NOT push gold
    support out of reach (rank/tokens must not regress materially).

Pure file diff — no graph, no LLM, free to re-run. Exit code 1 if any held-out qid regresses
(reached->censored, or rank worsens), so the runner can gate on it.

Env: PD_BASELINE, PD_POST (entropy rows json), PD_WRITES (perception_write.py manifest).
"""

from __future__ import annotations

import json
import os
import statistics
import sys

_HERE = os.path.dirname(__file__)
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.abspath(os.path.join(_HERE, "..", "..", "..", "..", "menhir-frontier", "src")))

import entropy  # noqa: E402
import perception_tune as pt  # noqa: E402

BASELINE = os.getenv("PD_BASELINE", os.path.expanduser("~/capstone-baseline-rows.json"))
POST = os.getenv("PD_POST", os.path.expanduser("~/capstone-post-rows.json"))
WRITES = os.getenv("PD_WRITES", os.path.expanduser("~/perception-write.json"))


def _delivered(row) -> dict | None:
    return row.get("delivered") if row and not row.get("censored") else None


def _fmt(d: dict | None) -> str:
    if d is None:
        return "censored"
    return f"rank {d['rank']:>2}, {d['memories']:>2} mem, {d['tokens']:>4} tok"


def _med(rows, key):
    vals = [(_delivered(r) or {}).get(key) for r in rows]
    vals = [v for v in vals if v is not None]
    return statistics.median(vals) if vals else None


def main() -> int:
    base = {r["qid"]: r for r in json.load(open(BASELINE))}
    post = {r["qid"]: r for r in json.load(open(POST))}
    writes = {r["qid"]: r for r in json.load(open(WRITES))}

    items = {str(i["question_id"]): i for i in entropy._items()}
    count_qids = [q for q in items if pt._is_count_answer(items[q]["answer"])]
    written = {q for q, w in writes.items() if w.get("committed")}
    heldout_qids = [q for q, w in writes.items() if w.get("tag") == "heldout"]

    regressed = []

    print(f"===== ARM C DELTA (baseline={os.path.basename(BASELINE)} -> post={os.path.basename(POST)}) =====")
    for label, qids in (("COUNTING", [q for q in count_qids if q in base]),
                        ("HELD-OUT (Goodhart guard)", [q for q in heldout_qids if q in base])):
        print(f"\n--- {label} ---")
        for q in qids:
            b, p = _delivered(base[q]), _delivered(post.get(q, {}))
            wrote = "W" if q in written else " "
            changed = (b or {}).get("rank") != (p or {}).get("rank") or (b is None) != (p is None)
            mark = "  <-- " if changed else ""
            print(f"  [{wrote}] {q:14s} {_fmt(b):>28s}  ->  {_fmt(p):<28s}{mark}")
            # regression: reached -> censored, or rank strictly worse
            if (b is not None and p is None) or (b and p and p["rank"] > b["rank"]):
                regressed.append((label, q))
        sub_b = [base[q] for q in qids]
        sub_p = [post[q] for q in qids if q in post]
        for name, rows in (("baseline", sub_b), ("post    ", sub_p)):
            reached = sum(1 for r in rows if _delivered(r))
            print(f"      {name}: reached {reached}/{len(qids)}, "
                  f"median rank {_med(rows,'rank')}, memories {_med(rows,'memories')}, "
                  f"tokens {_med(rows,'tokens')}")

    n_views = sum(len(w.get("committed", [])) for w in writes.values())
    print(f"\nwrites: {n_views} Views across {len(written)} namespaces "
          f"({sum(1 for q in written if q in count_qids)} counting, "
          f"{sum(1 for q in written if q in heldout_qids)} held-out)")
    if regressed:
        print(f"\n!!! REGRESSIONS ({len(regressed)}): " + ", ".join(f"{l}:{q}" for l, q in regressed))
        return 1
    print("\nno regressions: every unchanged/abstained namespace held; Goodhart guard clean.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
