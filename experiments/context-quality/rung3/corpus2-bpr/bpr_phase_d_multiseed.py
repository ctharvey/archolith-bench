#!/usr/bin/env python3
"""2nd-corpus Phase D — N>=3 multi-seed firm-up (bulletproof-react).

The single-seed gate run (`RESULT-corpus2-bpr-recall.md`) found the xfcombo recall win
does NOT generalize to bulletproof-react — topological won outright — but at N=1/cell.
This re-runs the same frozen-briefing protocol across 3 seeds so the flip gets variance
(mean / floor / stdev) instead of one draw, mirroring the yawn `phase_d_multiseed.py`
that cleared the gate on corpus 1.

5 strategies x 3 tasks x 3 seeds = 45 DeepSeek calls (deepseek-chat, temp=0.2). Metered;
STOPS on a 429 per protocol. Set ARCHOLITH_CORPUS to the bulletproof-react react-vite src.
Reproduce: python bpr_phase_d_multiseed.py   (then --report re-scores offline)
"""
from __future__ import annotations

import json
import shutil
import statistics
import sys
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))  # rung3/ for paths.py
from paths import context_root  # noqa: E402

sys.path.insert(0, str(context_root()))

import bpr_phase_d as d  # noqa: E402  (reuse the exact fill orders, tasks, prompts)
from bpr_corpus import build_briefing  # noqa: E402
from bpr_contract import check_feature, graded_feature_score  # noqa: E402

SEEDS = [7, 8, 9]
OUT = HERE / "phaseD-multiseed-output"


def _call_with_seed(context_block: str, user: str, key: str, seed: int) -> str:
    body = json.dumps({
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": d.SYSTEM.format(context=context_block)},
            {"role": "user", "content": user},
        ],
        "temperature": 0.2, "max_tokens": 4000, "seed": seed,
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.deepseek.com/v1/chat/completions", data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read())["choices"][0]["message"]["content"]


def _score(graded: dict, binary: dict, core: dict) -> None:
    """Score whatever is in OUT (no API calls) into the passed dicts."""
    for s in d.STRATEGIES:
        graded[s].clear(); binary[s].clear(); core[s].clear()
    for seed in SEEDS:
        for fkey, _n, _q in d.TASKS:
            for strat in d.STRATEGIES:
                dest = OUT / f"seed{seed}" / fkey / strat
                feat = d._find_feature(dest, fkey) if dest.exists() else None
                if feat is None:
                    graded[strat].append(0.0); binary[strat].append(0); core[strat].append(0)
                    continue
                rep = check_feature(feat)
                graded[strat].append(graded_feature_score(feat)[0])
                binary[strat].append(rep.recall_score[0])
                core[strat].append(1 if rep.ok else 0)


def _report(graded: dict, binary: dict, core: dict) -> None:
    print("\n" + "=" * 72)
    print(f"{'strategy':<14}{'graded mean':<13}{'min':<7}{'max':<7}{'stdev':<8}"
          f"{'bin mean':<10}{'core-OK':<9}{'n':<4}")
    print("-" * 72)
    for s in sorted(d.STRATEGIES, key=lambda s: -statistics.mean(graded[s])):
        g = graded[s]
        print(f"{s:<14}{statistics.mean(g):<13.2f}{min(g):<7.1f}{max(g):<7.1f}"
              f"{statistics.pstdev(g):<8.2f}"
              f"{statistics.mean(binary[s]):<10.2f}{sum(core[s])}/{len(core[s])}{'':<4}{len(g):<4}")
    print("\n(min = the FLOOR — the load-bearing property; n = tasks x seeds = 9)")


def report() -> int:
    print("bulletproof-react Phase D multi-seed — RE-SCORE of persisted outputs (no API calls)")
    graded = {s: [] for s in d.STRATEGIES}
    binary = {s: [] for s in d.STRATEGIES}
    core = {s: [] for s in d.STRATEGIES}
    _score(graded, binary, core)
    _report(graded, binary, core)
    return 0


def run() -> int:
    key = d._api_key()
    briefing = build_briefing()
    if not briefing.files:
        raise SystemExit("empty briefing — set ARCHOLITH_CORPUS to the bulletproof-react react-vite src")
    if OUT.exists():
        shutil.rmtree(OUT)
    print(f"bulletproof-react Phase D multi-seed — seeds={SEEDS}, tasks={[t[0] for t in d.TASKS]}, "
          f"strategies={d.STRATEGIES}")
    print(f"{len(d.STRATEGIES)*len(d.TASKS)*len(SEEDS)} DeepSeek calls\n")
    try:
        for seed in SEEDS:
            for fkey, noun, query in d.TASKS:
                user = d._user_prompt(noun)
                for strat in d.STRATEGIES:
                    ctx, _sel = d._context(briefing, strat, query)
                    resp = _call_with_seed(ctx, user, key, seed)
                    d.parse_and_write(resp, OUT / f"seed{seed}" / fkey / strat)
            print(f"  seed {seed} done")
    except urllib.error.HTTPError as e:
        if e.code == 429:
            print("\n!! 429 RATE LIMIT from DeepSeek — STOPPING per protocol. "
                  "Partial data persisted; rerun later or use --report.")
            return 2
        raise

    graded = {s: [] for s in d.STRATEGIES}
    binary = {s: [] for s in d.STRATEGIES}
    core = {s: [] for s in d.STRATEGIES}
    _score(graded, binary, core)
    _report(graded, binary, core)
    return 0


if __name__ == "__main__":
    if "--report" in sys.argv:
        raise SystemExit(report())
    raise SystemExit(run())
