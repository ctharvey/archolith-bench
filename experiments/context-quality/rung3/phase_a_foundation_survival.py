#!/usr/bin/env python3
"""Rung 3 Phase A — OFFLINE foundation-survival mechanism test.

Tests Q1 of PROTOCOL-rung3-pressure.md: under budget pressure on a REAL corpus,
does topological fill keep the high-in-degree FOUNDATIONS in the assembled context
block more often than FIFO / scored? No proxy, no agent, no API calls.

Construction (per the protocol):
  - leaves     = whole feature directories (the exemplar screens), placed FIRST.
  - foundations = the shared data/ + domain/ + layouts/ files, placed LAST
                  (worst case for FIFO).
  briefing.files = leaves + foundations. The real assembler fills this to a budget
  in each strategy's order; we record which TRACKED foundations survive.

Run from anywhere; it adds archolith-context to sys.path.
    python phase_a_foundation_survival.py
"""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure local modules are importable.
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from paths import context_root, corpus_root  # noqa: E402

_CTX_ROOT = context_root()
sys.path.insert(0, str(_CTX_ROOT))

from archolith_proxy.curator.briefing import PreFetchedFile, SessionBriefing  # noqa: E402
from archolith_proxy.curator.deterministic_assembler import (  # noqa: E402
    build_deterministic_context,
)

CORPUS = corpus_root()
EXTS = {".ts", ".tsx", ".js", ".jsx", ".css", ".astro", ".mjs"}

# Exemplar feature screens the prepper would plausibly pull for "add a browse screen".
LEAF_DIRS = ["features/set-v3", "features/cards-v3", "features/card-index",
             "features/graded-v3", "features/sealed"]
# Shared layers = where foundations live.
FOUNDATION_DIRS = ["data", "domain", "layouts", "ui"]

# The load-bearing foundations we score survival on (the silent anchors a feature
# request never names). Tracked by path suffix.
TRACKED_FOUNDATIONS = [
    "data/apiClient.ts",
    "data/repository.ts",
    "data/api-types.ts",
    "domain/slug.ts",
    "domain/models/Common.ts",
    "domain/formatters.ts",
    "domain/color-styles.ts",
    "layouts/Layout.astro",
]

QUERY = ("Add a Decks browse screen, consistent with the rest of the app. "
         "It lists decks, each showing its total market value.")
BUDGETS = [6000, 4000, 3000, 2000, 1500]
STRATEGIES = ["fifo", "scored", "topological"]


def _load(rel: str) -> PreFetchedFile | None:
    p = CORPUS / rel
    if not p.is_file():
        return None
    t = p.read_text(encoding="utf-8", errors="replace")
    return PreFetchedFile(path=rel.replace("\\", "/"), outline="",
                          sections=[(1, t.count("\n") + 1, t)], relevance="score 0.5")


def _files_under(dirs: list[str]) -> list[str]:
    out: list[str] = []
    for d in dirs:
        base = CORPUS / d
        if not base.exists():
            continue
        for p in sorted(base.rglob("*")):
            if p.suffix.lower() in EXTS and p.is_file():
                out.append(str(p.relative_to(CORPUS)).replace("\\", "/"))
    return out


def build_briefing() -> SessionBriefing:
    leaves = [_load(r) for r in _files_under(LEAF_DIRS)]
    foundations = [_load(r) for r in _files_under(FOUNDATION_DIRS)]
    files = [f for f in leaves if f] + [f for f in foundations if f]  # foundations LAST
    return SessionBriefing(session_id="r3a", source_turn=5,
                           session_goal="add a browse screen", files=files)


def _survivors(briefing: SessionBriefing, budget: int, strategy: str) -> set[str]:
    kw = {"topological": dict(topological=True),
          "scored": dict(scored=True, query=QUERY),
          "fifo": dict()}[strategy]
    _text, selected = build_deterministic_context(briefing, budget, **kw)
    return {f["path"] for f in selected}


def _foundation_rate(surv: set[str]) -> tuple[int, int]:
    kept = sum(1 for f in TRACKED_FOUNDATIONS if f in surv)
    return kept, len(TRACKED_FOUNDATIONS)


def run() -> int:
    briefing = build_briefing()
    n_leaves = len(_files_under(LEAF_DIRS))
    print("Rung 3 Phase A — foundation survival under budget pressure (OFFLINE)")
    print(f"corpus={CORPUS}")
    print(f"briefing: {len(briefing.files)} files "
          f"({n_leaves} feature/leaf files first, foundations LAST = worst case for FIFO)")
    print(f"tracked foundations: {len(TRACKED_FOUNDATIONS)}")
    total_chars = sum(len(s[2]) for f in briefing.files for s in f.sections)
    print(f"briefing size ~{total_chars // 4:,} tok vs budgets {BUDGETS} -> pressure at every budget\n")

    print(f"{'budget':>7} | " + " | ".join(f"{s:>14}" for s in STRATEGIES))
    print("-" * (9 + 17 * len(STRATEGIES)))
    matrix: dict[int, dict[str, tuple[int, int]]] = {}
    for budget in BUDGETS:
        cells = []
        matrix[budget] = {}
        for strat in STRATEGIES:
            kept, total = _foundation_rate(_survivors(briefing, budget, strat))
            matrix[budget][strat] = (kept, total)
            cells.append(f"{kept}/{total} found.".rjust(14))
        print(f"{budget:>7} | " + " | ".join(cells))

    # Per-foundation detail at the tightest budget.
    tight = BUDGETS[-1]
    print(f"\nper-foundation survival at budget={tight}:")
    print(f"  {'foundation':<26} " + " ".join(f"{s:>12}" for s in STRATEGIES))
    surv_by_strat = {s: _survivors(briefing, tight, s) for s in STRATEGIES}
    for f in TRACKED_FOUNDATIONS:
        marks = " ".join((" keep" if f in surv_by_strat[s] else " DROP").rjust(12)
                         for s in STRATEGIES)
        print(f"  {f:<26} {marks}")

    # Pre-registered decision rule.
    topo_ge_fifo = all(matrix[b]["topological"][0] >= matrix[b]["fifo"][0] for b in BUDGETS)
    strict_better = sum(1 for b in BUDGETS
                        if matrix[b]["topological"][0] > matrix[b]["fifo"][0])
    print("\nDECISION RULE (pre-registered): topological earns Phase B IFF "
          ">= FIFO at every budget AND strictly > at >=2 budgets.")
    print(f"  topological >= FIFO at every budget: {topo_ge_fifo}")
    print(f"  topological strictly > FIFO at {strict_better} budget level(s)")
    verdict = "PASS -> Phase B justified" if (topo_ge_fifo and strict_better >= 2) \
        else "FAIL -> investigate extraction coverage (R3a) before paying for Phase B"
    print(f"  VERDICT: {verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
