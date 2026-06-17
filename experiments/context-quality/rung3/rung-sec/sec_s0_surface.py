#!/usr/bin/env python3
"""S0 surface map — archolith-security context-integrity rung (OFFLINE, no API).

Proves the poisoned-corpus harness and establishes the baseline gap before any
metered (model) work or credit request. For each IPI payload class
(CONTENT / MAP / PRIMING) x fill strategy (fifo / scored / topological / combo /
xfcombo) x budget, it:
  1. builds the poisoned bpr briefing (`sec_corpus.build_poisoned_briefing`),
  2. assembles the context with the real deterministic assembler
     (`build_deterministic_context`, the SAME path the recall harness uses),
  3. scores EXPOSURE (did the payload reach the window?) and GOVERNED (was it marked
     untrusted?) with `sec_contract.score_exposure`.

Everything is deterministic: no model is asked to obey anything. The headline this
is built to surface is the JOINT baseline fact —

    the structure-aware fills that WIN recall are the ones that most reliably
    deliver class-matched poison to the window, and GOVERNED is 0 everywhere
    (no trust separation exists today).

i.e. xfcombo (guarantees the exemplar survives) is the reliable carrier for
PRIMING poison; topological (foundations-first) is the reliable carrier for MAP
poison. That is a real, novel, zero-cost security finding and the motivation for
the deterministic governed-context defense measured in S2.

Reproduce:  python sec_s0_surface.py
            python sec_s0_surface.py --density 3   # payloads per cell (default 2)
"""
from __future__ import annotations

import argparse
import sys
from itertools import zip_longest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))                 # rung3/ for paths.py
sys.path.insert(0, str(HERE.parent / "corpus2-bpr"))  # exemplar helpers

from paths import context_root  # noqa: E402

sys.path.insert(0, str(context_root()))
from archolith_proxy.curator.briefing import SessionBriefing  # noqa: E402
from archolith_proxy.curator.deterministic_assembler import (  # noqa: E402
    build_deterministic_context,
)
from archolith_proxy.curator.scoring import score_files  # noqa: E402
from archolith_proxy.curator.dependency_graph import order_by_topology  # noqa: E402

from sec_contract import score_exposure  # noqa: E402
from sec_corpus import QUERY, build_poisoned_briefing  # noqa: E402
from sec_payloads import CLASSES  # noqa: E402

# Exemplar marker for bulletproof-react (matches bpr_phase_d._is_exemplar): the
# poisoned PRIMING payload is shaped to satisfy this so xfcombo selects it first.
import re  # noqa: E402


def _is_exemplar(path: str) -> bool:
    return bool(re.search(r"features/[^/]+/api/get-[^/]*\.ts$", path))


STRATEGIES = ("fifo", "scored", "topological", "combo", "xfcombo")
BUDGETS = (6000, 3000, 1500)


def _combo_order(files, query):
    scored = [f for _s, f in score_files(files, query)]
    topo = order_by_topology(files)
    seen, out = set(), []
    for a, b in zip_longest(scored, topo):
        for f in (a, b):
            if f is not None and f.path not in seen:
                seen.add(f.path)
                out.append(f)
    return out


def _xf_combo_order(files, query):
    scored = [f for _s, f in score_files(files, query)]
    topo = order_by_topology(files)
    out, seen = [], set()
    exemplar = next((f for f in scored if _is_exemplar(f.path)), None)
    if exemplar is not None:
        out.append(exemplar)
        seen.add(exemplar.path)
    for a, b in zip_longest(scored, topo):
        for f in (a, b):
            if f is not None and f.path not in seen:
                seen.add(f.path)
                out.append(f)
    return out


def _assemble(briefing, strat, budget) -> str:
    """Render the context with the production assembler, per fill strategy."""
    if strat in ("combo", "xfcombo"):
        order = (_combo_order if strat == "combo" else _xf_combo_order)(
            briefing.files, QUERY)
        b2 = SessionBriefing(session_id="sec-s0", source_turn=5,
                             session_goal=briefing.session_goal, files=order)
        ctx, _ = build_deterministic_context(b2, budget)  # FIFO over combo order
        return ctx
    kw = {"fifo": {}, "scored": dict(scored=True, query=QUERY),
          "topological": dict(topological=True)}[strat]
    ctx, _ = build_deterministic_context(briefing, budget, **kw)
    return ctx


def run(density: int) -> int:
    # Pre-flight: confirm the clean briefing loads (corpus present).
    probe, _ = build_poisoned_briefing("content", 0)
    if not probe.files:
        print("(empty briefing — set ARCHOLITH_CORPUS to the bulletproof-react "
              "react-vite src, e.g. projects/forked/bulletproof-react/apps/"
              "react-vite/src)")
        return 2

    print("archolith-security S0 — context-integrity surface map (OFFLINE, no API)")
    print(f"corpus=bulletproof-react  payloads/cell={density}  "
          f"strategies={STRATEGIES}")
    print("cells = EXPOSURE rate (markers reaching the window) | "
          "GOVERNED rate (of exposed, marked untrusted)\n")

    # Per (class, strategy, budget): exposure + governed.
    headline: dict[str, dict[str, float]] = {}
    for pclass in CLASSES:
        briefing, payloads = build_poisoned_briefing(pclass, density)
        print(f"### {pclass.upper()} payload  ({payloads[0].description})")
        hdr = f"{'budget':>7} | " + " | ".join(f"{s:>12}" for s in STRATEGIES)
        print(hdr)
        print("-" * len(hdr))
        best_exposure = {s: 0.0 for s in STRATEGIES}
        any_governed = 0
        for budget in BUDGETS:
            cells = []
            for strat in STRATEGIES:
                ctx = _assemble(briefing, strat, budget)
                r = score_exposure(ctx, payloads)
                best_exposure[strat] = max(best_exposure[strat], r.exposure_rate)
                any_governed += r.n_governed
                cells.append(
                    f"{r.exposure_rate:>4.0%}|{r.governed_rate:>4.0%}".rjust(12))
            print(f"{budget:>7} | " + " | ".join(cells))
        headline[pclass] = best_exposure
        # Which strategy is the most reliable carrier for this class?
        carrier = max(best_exposure, key=best_exposure.get)
        print(f"  -> most reliable carrier: {carrier} "
              f"(max exposure {best_exposure[carrier]:.0%}); "
              f"governed cells across grid: {any_governed}\n")

    # MAP dose-response: an orphan shadow (degree 0) is sunk by in-degree fill; a
    # realistic attacker inflates in-degree by planting importers. Sweep degree at a
    # fixed mid budget to show topological's exposure rising with planted in-degree.
    print("### MAP in-degree dose-response (topological fill, budget=3000)")
    print("    naive orphan shadow vs realistic in-degree inflation")
    print(f"{'degree':>7} | {'exposure':>10} | {'governed':>10}")
    print("-" * 34)
    for degree in (0, 8, 16, 24):
        b, pays = build_poisoned_briefing("map", density, map_degree=degree)
        ctx = _assemble(b, "topological", 3000)
        r = score_exposure(ctx, pays)
        print(f"{degree:>7} | {r.exposure_rate:>9.0%} | {r.governed_rate:>9.0%}")
    print("    -> topological resists the orphan (degree 0) but carries the shadow")
    print("       once planted in-degree makes it look load-bearing.\n")

    print("=" * 64)
    print("S0 BASELINE FINDINGS (deterministic, no model):")
    print("  - GOVERNED is 0 across the entire grid: today's assembler renders all")
    print("    retrieved code in one equal-trust pool — no provenance boundary.")
    print("  - Class-matched carriers (the recall-winning fills double as the")
    print("    reliable poison carriers):")
    for pclass in CLASSES:
        be = headline[pclass]
        carrier = max(be, key=be.get)
        print(f"      {pclass:<8} -> {carrier:<12} (exposure {be[carrier]:.0%})")
    print("\n  EXPOSURE != attack success. Obeying the payload needs a model;")
    print("  that is the metered S2 pass. S0 proves the harness + the baseline gap")
    print("  (high exposure, zero governance) at zero API cost.")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="archolith-security S0 surface map")
    ap.add_argument("--density", type=int, default=2,
                    help="payloads injected per cell (default 2)")
    args = ap.parse_args()
    raise SystemExit(run(args.density))
