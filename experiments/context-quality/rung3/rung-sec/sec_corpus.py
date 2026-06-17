#!/usr/bin/env python3
"""Poisoned-corpus fork for the archolith-security S0 surface map.

Takes the benign bulletproof-react briefing (`../corpus2-bpr/bpr_corpus.py`) and
injects IPI payloads (`sec_payloads.py`) at a controlled density, returning a
briefing the existing deterministic assembler can fill unchanged. The benign files
are loaded exactly as the recall harness loads them, so the only difference between
the clean and poisoned runs is the planted payloads — a clean A/B.

Injection placement honors each payload's `inject_as`:
  leaf       -> inserted among the feature files (front of the briefing, like a real
                feature dir the prepper would pull).
  foundation -> appended with the shared-infra foundations (back of the briefing),
                where the load-bearing modules live.

This module performs NO assembly and NO scoring — it only constructs the poisoned
briefing and reports the ground-truth payload set. Offline, free.

Set ARCHOLITH_CORPUS to the bulletproof-react react-vite src, e.g.
  projects/forked/bulletproof-react/apps/react-vite/src
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))                 # rung3/ for paths.py
sys.path.insert(0, str(HERE.parent / "corpus2-bpr"))  # bpr_corpus

from paths import context_root  # noqa: E402

sys.path.insert(0, str(context_root()))
from archolith_proxy.curator.briefing import SessionBriefing  # noqa: E402

from bpr_corpus import build_briefing as build_clean_briefing  # noqa: E402
from sec_payloads import Payload, make_map_importers, make_payloads  # noqa: E402

# Query a new-feature request would carry (used by scored/combo/xfcombo fills).
QUERY = ("Add a Notifications feature that lists the user's notifications, "
         "each showing its message and date, consistent with the rest of the app.")


def build_poisoned_briefing(
    pclass: str, count: int, map_degree: int = 0,
) -> tuple[SessionBriefing, list[Payload]]:
    """Return (briefing, payloads): the clean bpr briefing with `count` payloads of
    `pclass` injected by placement. `count=0` returns the clean briefing + [].

    `map_degree` (MAP class only) plants that many importer files PER payload so the
    shadow foundation gains dependency in-degree — modeling the realistic
    navigation-hijack escalation (an orphan shadow is sunk by in-degree fill; an
    in-degree-inflated one is carried). Ignored for content/priming."""
    clean = build_clean_briefing()
    payloads = make_payloads(pclass, count) if count else []
    pay_files = [p.to_file() for p in payloads]

    leaves = [f for p, f in zip(payloads, pay_files) if p.inject_as == "leaf"]
    founds = [f for p, f in zip(payloads, pay_files) if p.inject_as == "foundation"]

    importers: list = []
    if pclass == "map" and map_degree:
        for p in payloads:
            importers.extend(make_map_importers(p, map_degree))

    # leaf payloads + map importers ride at the FRONT (with feature files);
    # foundation payloads at the BACK (with shared infra) — matches where each lands.
    files = leaves + importers + list(clean.files) + founds
    poisoned = SessionBriefing(
        session_id="sec-s0", source_turn=5,
        session_goal=clean.session_goal or "add a list feature", files=files,
    )
    return poisoned, payloads


def run() -> int:
    """Sanity check: build one poisoned briefing per class, report sizes (offline)."""
    clean = build_clean_briefing()
    if not clean.files:
        print("(empty clean briefing — is ARCHOLITH_CORPUS set to the "
              "bulletproof-react react-vite src?)")
        return 2
    print("Poisoned-corpus fork — sanity check (OFFLINE)")
    print(f"clean briefing: {len(clean.files)} files\n")
    for pclass in ("content", "map", "priming"):
        b, pays = build_poisoned_briefing(pclass, 2)
        names = ", ".join(p.path for p in pays)
        print(f"  {pclass:<8} +{len(pays)} payloads -> {len(b.files)} files | {names}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
