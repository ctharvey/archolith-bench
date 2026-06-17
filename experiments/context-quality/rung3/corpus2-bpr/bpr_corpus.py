#!/usr/bin/env python3
"""2nd-corpus briefing construction for bulletproof-react (the recall-confirm gate).

Parallel to `../phase_a_foundation_survival.py` `build_briefing`, but for the
bulletproof-react `react-vite` corpus instead of yawn.frontend. Same construction
the rung-3 protocol uses: exemplar feature dirs FIRST (leaves), shared-infra
foundations LAST (worst case for FIFO). The real assembler fills this to a budget in
each strategy's order; the recall harness scores what convention the model recalls
from the surviving briefing.

Set ARCHOLITH_CORPUS to the bulletproof-react react-vite src before running, e.g.
  forked/bulletproof-react/apps/react-vite/src

Foundation-survival (offline, free) pre-flight:  python bpr_corpus.py
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))  # rung3/ for paths.py
from paths import context_root, corpus_root  # noqa: E402

sys.path.insert(0, str(context_root()))

from archolith_proxy.curator.briefing import PreFetchedFile, SessionBriefing  # noqa: E402
from archolith_proxy.curator.deterministic_assembler import build_deterministic_context  # noqa: E402

CORPUS = corpus_root()
EXTS = {".ts", ".tsx", ".js", ".jsx", ".css", ".mjs"}

# Exemplar feature dirs the prepper would pull for "add a list feature" (the
# convention to imitate). teams/auth excluded: teams has no component, auth is forms.
LEAF_DIRS = ["features/comments", "features/discussions", "features/users"]
# Shared layers = where the silent foundations live.
FOUNDATION_DIRS = ["lib", "types", "config", "utils", "hooks"]

# Load-bearing foundations scored for survival (the infra a feature request never
# names). Tracked by path suffix — these are bulletproof-react's apiClient analogs.
TRACKED_FOUNDATIONS = [
    "lib/api-client.ts",
    "lib/react-query.ts",
    "lib/auth.tsx",
    "lib/authorization.tsx",
    "types/api.ts",
    "config/paths.ts",
    "config/env.ts",
    "utils/format.ts",
]

QUERY = ("Add a Notifications feature that lists the user's notifications, "
         "consistent with the rest of the app.")
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
    return SessionBriefing(session_id="bpr-a", source_turn=5,
                           session_goal="add a list feature", files=files)


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
    if not briefing.files:
        print(f"(empty briefing — is ARCHOLITH_CORPUS set to the bulletproof-react "
              f"react-vite src? got CORPUS={CORPUS})")
        return 2
    n_leaves = len(_files_under(LEAF_DIRS))
    print("bulletproof-react Phase A — foundation survival under budget pressure (OFFLINE)")
    print(f"corpus={CORPUS}")
    print(f"briefing: {len(briefing.files)} files "
          f"({n_leaves} feature/leaf files first, foundations LAST = worst case for FIFO)")
    total_chars = sum(len(s[2]) for f in briefing.files for s in f.sections)
    print(f"briefing size ~{total_chars // 4:,} tok vs budgets {BUDGETS} -> pressure check\n")

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

    topo_ge_fifo = all(matrix[b]["topological"][0] >= matrix[b]["fifo"][0] for b in BUDGETS)
    strict_better = sum(1 for b in BUDGETS
                        if matrix[b]["topological"][0] > matrix[b]["fifo"][0])
    print("\nDECISION RULE (pre-registered): topological earns recall test IFF "
          ">= FIFO at every budget AND strictly > at >=2 budgets.")
    print(f"  topological >= FIFO at every budget: {topo_ge_fifo}")
    print(f"  topological strictly > FIFO at {strict_better} budget level(s)")
    verdict = "PASS" if (topo_ge_fifo and strict_better >= 2) else "WEAK (still informative)"
    print(f"  VERDICT: {verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
