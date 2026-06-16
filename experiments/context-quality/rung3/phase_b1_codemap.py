#!/usr/bin/env python3
"""Rung 3 — B1: does surfacing a CODE MAP change recall? (frozen briefing)

The MAP job (a structural overview) was never an experimental variable — every prior
phase varied CONTENT only (RESULT-...: §9 of the decomposition note). Thread 1
(archolith-context ad0612c) now renders a `=== CODE MAP ===` from the discarded
dependency graph. This is the experiment that uses it.

Design (frozen briefing, re-reading DENIED — the regime where briefing effects are
isolated; budget=3000 to force pressure). Factor = MAP presence, crossed with two
fill strategies to see if the map substitutes for good fill:
  cells = {fifo, xfcombo} x {map OFF (M0), map ON (M1 structural)}
  x 3 tasks x 3 seeds = 36 DeepSeek calls (~$0.04).
Decisive: if map ON > map OFF on a fixed fill, the MAP job moves recall even under
re-reading-denied; if not, the decomposition's MAP value is weaker than claimed
(for recall — navigation is a separate metric, not measured here).

Metered. STOPs on 429. Reproduce: python rung3/phase_b1_codemap.py
"""
from __future__ import annotations

import json
import statistics
import sys
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from paths import context_root  # noqa: E402

sys.path.insert(0, str(context_root()))

import phase_c_frozen_briefing as pc  # noqa: E402
from archolith_proxy.curator.briefing import SessionBriefing  # noqa: E402
from archolith_proxy.curator.deterministic_assembler import build_deterministic_context  # noqa: E402
from phase_a_foundation_survival import build_briefing  # noqa: E402
from phase_d_combo import _xf_combo_order  # noqa: E402
from phase_c_multi import _find_feature, _user_prompt, TASKS  # noqa: E402
from feature_contract import check_feature, graded_feature_score  # noqa: E402

SEEDS = [7, 8, 9]
BUDGET = 3000
# (fill label, map on?) — the 2x2 crossed with fill
CELLS = [("fifo", False), ("fifo", True), ("xfcombo", False), ("xfcombo", True)]
OUT = HERE / "phaseB1-output"


def _context(briefing, fill, emit_map, query):
    if fill == "xfcombo":
        order = _xf_combo_order(briefing.files, query)
        b2 = SessionBriefing(session_id="b1", source_turn=5,
                             session_goal=briefing.session_goal, files=order)
        return build_deterministic_context(b2, BUDGET, emit_map=emit_map)
    return build_deterministic_context(briefing, BUDGET, emit_map=emit_map)


def _call(context_block: str, key: str, seed: int) -> str:
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


def _label(fill, emit_map):
    return f"{fill}+{'MAP' if emit_map else 'nomap'}"


def run() -> int:
    import shutil
    key = pc._api_key()
    briefing = build_briefing()
    if OUT.exists():
        shutil.rmtree(OUT)
    graded: dict[str, list[float]] = {_label(f, m): [] for f, m in CELLS}
    print(f"B1 — code map vs recall (frozen). seeds={SEEDS}, tasks={[t[0] for t in TASKS]}, "
          f"cells={[_label(f,m) for f,m in CELLS]}")
    print(f"{len(CELLS)*len(TASKS)*len(SEEDS)} DeepSeek calls\n")
    try:
        for seed in SEEDS:
            for fkey, noun, query in TASKS:
                pc.USER = _user_prompt(noun)
                for fill, emit_map in CELLS:
                    ctx, _sel = _context(briefing, fill, emit_map, query)
                    resp = _call(ctx, key, seed)
                    dest = OUT / f"seed{seed}" / fkey / _label(fill, emit_map)
                    pc.parse_and_write(resp, dest)
                    feat = _find_feature(dest, fkey)
                    graded[_label(fill, emit_map)].append(
                        graded_feature_score(feat)[0] if feat else 0.0)
            print(f"  seed {seed} done")
    except urllib.error.HTTPError as e:
        if e.code == 429:
            print("\n!! 429 RATE LIMIT — STOPPING per protocol. Partial data; rerun later.")
            return 2
        raise

    print("\n" + "=" * 60)
    print(f"{'cell':<18}{'graded mean':<13}{'min':<7}{'max':<7}{'stdev':<8}")
    print("-" * 60)
    for f, m in CELLS:
        g = graded[_label(f, m)]
        print(f"{_label(f,m):<18}{statistics.mean(g):<13.2f}{min(g):<7.1f}{max(g):<7.1f}"
              f"{statistics.pstdev(g):<8.2f}")
    # the two contrasts that matter
    def mean(f, m): return statistics.mean(graded[_label(f, m)])
    print("\nMAP effect (map ON - map OFF), same fill:")
    print(f"  fifo:    {mean('fifo',True)-mean('fifo',False):+.2f}")
    print(f"  xfcombo: {mean('xfcombo',True)-mean('xfcombo',False):+.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
