#!/usr/bin/env python3
"""Rung 3 Phase D — N>=3 multi-seed confirm (the standing hard gate).

Phase D (RESULT-phaseD-combo.md) ranked the fill strategies on N=1 per cell. This
re-runs the same frozen-briefing protocol across 3 seeds so the load-bearing claims
(xfcombo wins; its edge is the FLOOR, not the mean) get variance instead of a single
draw. 5 strategies x 3 tasks x 3 seeds = 45 DeepSeek calls (~$0.05).

Metered (direct DeepSeek). Obeys the 429 protocol: STOP on a rate-limit error.
Reproduce: python rung3/phase_d_multiseed.py
"""
from __future__ import annotations

import statistics
import sys
import urllib.error
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from paths import context_root  # noqa: E402

sys.path.insert(0, str(context_root()))

import phase_c_frozen_briefing as pc  # noqa: E402
from phase_a_foundation_survival import build_briefing  # noqa: E402
from phase_d_combo import _context, STRATEGIES  # noqa: E402  (reuse the exact fill orders)
from phase_c_multi import _find_feature, _user_prompt, TASKS  # noqa: E402
from feature_contract import check_feature, graded_feature_score  # noqa: E402

SEEDS = [7, 8, 9]
OUT = HERE / "phaseD-multiseed-output"


def _call_with_seed(context_block: str, key: str, seed: int) -> str:
    """call_deepseek with an explicit seed (overrides the module default)."""
    import json
    import urllib.request
    body = json.dumps({
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": pc.SYSTEM.format(context=context_block)},
            {"role": "user", "content": pc.USER},
        ],
        "temperature": 0.2, "max_tokens": 4000, "seed": seed,
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.deepseek.com/v1/chat/completions", data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read())["choices"][0]["message"]["content"]


def run() -> int:
    import shutil
    key = pc._api_key()
    briefing = build_briefing()
    if OUT.exists():
        shutil.rmtree(OUT)

    # graded[strategy] = list of per-(task,seed) graded scores
    graded: dict[str, list[float]] = {s: [] for s in STRATEGIES}
    binary: dict[str, list[int]] = {s: [] for s in STRATEGIES}
    print(f"Phase D multi-seed confirm — seeds={SEEDS}, tasks={[t[0] for t in TASKS]}, "
          f"strategies={STRATEGIES}")
    print(f"{len(STRATEGIES)*len(TASKS)*len(SEEDS)} DeepSeek calls\n")
    try:
        for seed in SEEDS:
            for fkey, noun, query in TASKS:
                pc.USER = _user_prompt(noun)
                for strat in STRATEGIES:
                    ctx, _sel = _context(briefing, strat, query)
                    resp = _call_with_seed(ctx, key, seed)
                    dest = OUT / f"seed{seed}" / fkey / strat
                    pc.parse_and_write(resp, dest)
                    feat = _find_feature(dest, fkey)
                    if feat is None:
                        graded[strat].append(0.0)
                        binary[strat].append(0)
                        continue
                    rep = check_feature(feat)
                    graded[strat].append(graded_feature_score(feat)[0])
                    binary[strat].append(rep.recall_score[0])
            print(f"  seed {seed} done")
    except urllib.error.HTTPError as e:
        if e.code == 429:
            print(f"\n!! 429 RATE LIMIT from DeepSeek — STOPPING per protocol. "
                  f"Partial data collected; rerun later.")
            return 2
        raise

    print("\n" + "=" * 64)
    print(f"{'strategy':<14}{'graded mean':<13}{'min':<7}{'max':<7}{'stdev':<8}{'n':<4}")
    print("-" * 64)
    # rank by graded mean
    rows = sorted(STRATEGIES, key=lambda s: -statistics.mean(graded[s]))
    for s in rows:
        g = graded[s]
        print(f"{s:<14}{statistics.mean(g):<13.2f}{min(g):<7.1f}{max(g):<7.1f}"
              f"{(statistics.pstdev(g)):<8.2f}{len(g):<4}")
    print("\n(min = the FLOOR — the load-bearing property; n = tasks x seeds)")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
