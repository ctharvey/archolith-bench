#!/usr/bin/env python3
"""Rung 3 Phase D — COMBO fill strategy (scored x topological), frozen-briefing recall.

Phase C showed each pure strategy optimizes ONE objective and fails the others:
topological keeps FOUNDATIONS but no exemplar; scored targets a task-relevant
EXEMPLAR but unreliably and ignores foundations; FIFO is recency only. The combo
idea: reserve budget for BOTH by INTERLEAVING the two rankings (round-robin
scored, topological, scored, ...), so the top task-relevant exemplar AND the top
foundations both land in surviving positions.

Tested the same controlled way as Phase C (re-reading denied, budget=3000) across
3 tasks, vs the 3 pure strategies. If combo >= max(pure) it justifies porting a
`combo` fill mode into deterministic_assembler.py. 4 strategies x 3 tasks = 12
DeepSeek calls. Reproduce: python rung3/phase_d_combo.py
"""
from __future__ import annotations

import shutil
import sys
from itertools import zip_longest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from paths import context_root  # noqa: E402

sys.path.insert(0, str(context_root()))

from archolith_proxy.curator.briefing import SessionBriefing  # noqa: E402
from archolith_proxy.curator.deterministic_assembler import build_deterministic_context  # noqa: E402
from archolith_proxy.curator.scoring import score_files  # noqa: E402
from archolith_proxy.curator.dependency_graph import order_by_topology  # noqa: E402
from phase_a_foundation_survival import build_briefing  # noqa: E402
from phase_c_frozen_briefing import call_deepseek, parse_and_write, _api_key  # noqa: E402
from phase_c_multi import _find_feature, _user_prompt, TASKS  # noqa: E402
from feature_contract import check_feature  # noqa: E402

BUDGET = 3000
STRATEGIES = ("fifo", "scored", "topological", "combo", "xfcombo")
OUT = HERE / "phaseD-output"


def _combo_order(files, query):
    """Round-robin interleave of scored ranking and topological ranking, deduped.

    Front-loads the most task-relevant EXEMPLAR (scored #1) and the top FOUNDATION
    (topological #1) together, alternating down both ranked lists.
    """
    scored = [f for _s, f in score_files(files, query)]
    topo = order_by_topology(files)
    seen: set[str] = set()
    out = []
    for a, b in zip_longest(scored, topo):
        for f in (a, b):
            if f is not None and f.path not in seen:
                seen.add(f.path)
                out.append(f)
    return out


def _xf_combo_order(files, query):
    """Exemplar-aware combo: GUARANTEE a structural page exemplar (top-scored
    `*Page.tsx`) survives first, then interleave scored x topological. Fixes the
    naive combo's failure mode (scored #1 may be a non-page file, e.g. a types
    file -> no template)."""
    scored = [f for _s, f in score_files(files, query)]
    topo = order_by_topology(files)
    out, seen = [], set()
    page = next((f for f in scored if f.path.endswith("Page.tsx")), None)
    if page is not None:
        out.append(page)
        seen.add(page.path)
    for a, b in zip_longest(scored, topo):
        for f in (a, b):
            if f is not None and f.path not in seen:
                seen.add(f.path)
                out.append(f)
    return out


def _context(briefing, strat, query):
    if strat in ("combo", "xfcombo"):
        order = (_combo_order if strat == "combo" else _xf_combo_order)(briefing.files, query)
        b2 = SessionBriefing(session_id="d", source_turn=5, session_goal=briefing.session_goal,
                             files=order)
        return build_deterministic_context(b2, BUDGET)  # FIFO over the combo order
    kw = {"fifo": {}, "scored": dict(scored=True, query=query),
          "topological": dict(topological=True)}[strat]
    return build_deterministic_context(briefing, BUDGET, **kw)


def run() -> int:
    import phase_c_frozen_briefing as pc
    key = _api_key()
    briefing = build_briefing()
    if OUT.exists():
        shutil.rmtree(OUT)
    recall: dict[str, list[int]] = {s: [] for s in STRATEGIES}
    core_ok: dict[str, int] = {s: 0 for s in STRATEGIES}
    grid: dict[tuple[str, str], str] = {}

    print("Rung 3 Phase D — COMBO vs pure fills, frozen-briefing recall (re-reading denied)")
    print(f"tasks={[t[0] for t in TASKS]}  strategies={STRATEGIES}  budget={BUDGET}\n")
    for fkey, noun, query in TASKS:
        pc.USER = _user_prompt(noun)
        for strat in STRATEGIES:
            ctx, _sel = _context(briefing, strat, query)
            resp = call_deepseek(ctx, key)
            dest = OUT / fkey / strat
            parse_and_write(resp, dest)
            ddir = _find_feature(dest, fkey)
            if ddir is None:
                grid[(fkey, strat)] = "NOFEAT"
                continue
            rep = check_feature(ddir)
            kr, tot = rep.recall_score
            recall[strat].append(kr)
            core_ok[strat] += 1 if rep.ok else 0
            grid[(fkey, strat)] = f"{kr}/{tot}{'*' if rep.ok else ''}"

    print(f"{'task':<10}" + "".join(f"{s:<14}" for s in STRATEGIES))
    print("-" * 66)
    for fkey, _n, _q in TASKS:
        print(f"{fkey:<10}" + "".join(f"{grid.get((fkey,s),'-'):<14}" for s in STRATEGIES))
    print("-" * 66)
    print("(* = core PASS)\n")
    print(f"{'strategy':<14}{'mean recall':<14}{'core-OK':<10}")
    for s in STRATEGIES:
        v = recall[s]
        print(f"{s:<14}{(sum(v)/len(v) if v else 0):.2f}/6{'':<6}{core_ok[s]}/{len(TASKS)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
