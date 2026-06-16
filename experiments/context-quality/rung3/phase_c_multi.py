#!/usr/bin/env python3
"""Rung 3 Phase C (multi-task) — harden the frozen-briefing recall ranking.

Phase C (single Decks task, N=1) found topological WORST / scored BEST for
convention recall when re-reading is denied. Two caveats: N=1, and scored's win
might just be that "Decks browse" shares vocabulary with the sealed browse
exemplar. This varies the TARGET TASK (and the scored query with it) so the
relevant exemplar differs per task; if scored still wins across tasks the finding
is robust, if not we learn the boundary.

3 tasks x 3 strategies = 9 DeepSeek calls. Reuses Phase-C machinery.
Reproduce: python rung3/phase_c_multi.py
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from paths import context_root  # noqa: E402

sys.path.insert(0, str(context_root()))

from archolith_proxy.curator.deterministic_assembler import build_deterministic_context  # noqa: E402
from phase_a_foundation_survival import build_briefing  # noqa: E402
from phase_c_frozen_briefing import call_deepseek, parse_and_write, _api_key  # noqa: E402
from feature_contract import check_feature  # noqa: E402

BUDGET = 3000


def _find_feature(root: Path, fkey: str) -> Path | None:
    """Find the generated feature dir for this task (name contains the task stem)."""
    feats = root / "src" / "features"
    if not feats.exists():
        return None
    stem = fkey.rstrip("s").lower()  # decks->deck, promos->promo, bundles->bundle
    for d in sorted(feats.iterdir()):
        if d.is_dir() and stem in d.name.lower():
            return d
    return None

# (feature key, user-prompt noun phrase, scored query) — query varies WITH the task.
TASKS = [
    ("decks", "a Decks browse screen that lists decks, each showing its total market value",
     "decks browse screen total market value"),
    ("promos", "a Promos browse screen that lists promo cards, each showing its release year",
     "promos browse screen promo cards release year"),
    ("bundles", "a Bundles browse screen that lists product bundles, each showing its discount percent",
     "bundles browse screen product bundles discount percent"),
]
STRATEGIES = ("fifo", "scored", "topological")
OUT = HERE / "phaseC-multi-output"


def _ctx(briefing, strat, query):
    kw = {"fifo": {}, "scored": dict(scored=True, query=query),
          "topological": dict(topological=True)}[strat]
    return build_deterministic_context(briefing, BUDGET, **kw)


def _user_prompt(noun: str) -> str:
    return (
        f"Add {noun}, consistent with the rest of the app. Create the necessary files under "
        "src/features so it fits the app's existing patterns.\n\n"
        "Output EVERY file you create. For each file, emit a line exactly of the form:\n"
        "FILE: <relative/path/from/repo/root>\n"
        "immediately followed by a fenced code block with the file's full contents. Output nothing else."
    )


def run() -> int:
    import phase_c_frozen_briefing as pc
    key = _api_key()
    briefing = build_briefing()
    if OUT.exists():
        shutil.rmtree(OUT)
    results: dict[str, list[int]] = {s: [] for s in STRATEGIES}
    core_ok: dict[str, int] = {s: 0 for s in STRATEGIES}

    print("Rung 3 Phase C multi-task — frozen-briefing recall (re-reading denied)")
    print(f"tasks={[t[0] for t in TASKS]}  strategies={STRATEGIES}  budget={BUDGET}\n")
    grid: dict[tuple[str, str], str] = {}
    for fkey, noun, query in TASKS:
        user = _user_prompt(noun)
        for strat in STRATEGIES:
            ctx, _sel = _ctx(briefing, strat, query)
            # temporarily swap the module USER prompt used by call_deepseek
            pc.USER = user
            resp = call_deepseek(ctx, key)
            dest = OUT / fkey / strat
            parse_and_write(resp, dest)
            ddir = _find_feature(dest, fkey)
            if ddir is None:
                grid[(fkey, strat)] = "NOFEAT"
                continue
            rep = check_feature(ddir)
            kr, tot = rep.recall_score
            results[strat].append(kr)
            core_ok[strat] += 1 if rep.ok else 0
            grid[(fkey, strat)] = f"{kr}/{tot}{'*' if rep.ok else ''}"

    print(f"{'task':<10}" + "".join(f"{s:<16}" for s in STRATEGIES))
    print("-" * 58)
    for fkey, _n, _q in TASKS:
        print(f"{fkey:<10}" + "".join(f"{grid.get((fkey,s),'-'):<16}" for s in STRATEGIES))
    print("-" * 58)
    print("(* = core PASS: page+hook+data-layer+css all present)\n")
    print(f"{'strategy':<14}{'mean recall':<14}{'core-OK count':<14}")
    for s in STRATEGIES:
        vals = results[s]
        mean = sum(vals) / len(vals) if vals else 0
        print(f"{s:<14}{mean:.2f}/6{'':<7}{core_ok[s]}/{len(TASKS)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
