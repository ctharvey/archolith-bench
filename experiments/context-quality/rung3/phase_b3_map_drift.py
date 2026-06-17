#!/usr/bin/env python3
"""Rung 3 — B3: does a STALE code map degrade NAVIGATION? (the drift rung)

B2/B2b/B2c established the task-ranked map + list_dir as the best navigation design,
but ALWAYS with a FRESH map built from the current corpus. The open production
question (adapted from mex's `path`/`edges`/`staleness` drift checkers,
`.agent/research/archolith-vs-mex-prior-art.md`): a derived map/profile goes STALE as
the code changes — how much does that cost, and how often must we re-profile?

Design: run the SAME B2 navigation loop against the CURRENT corpus, varying ONLY the
map per arm. Two kinds of staleness:
  * AUTHENTIC (real old commit): build the task-map from a ~6-week commit. PRE-FLIGHT
    FINDING — the task-ranked map is naturally drift-RESISTANT: it surfaces only the
    top in-degree foundations + the task exemplar, which are the STABLE core; the real
    refactor churn (~13% of files) is all in the sub-component tail the map never names,
    so the old map's surfaced paths are ~0% dead. So the authentic arm tests SEMANTIC
    drift (an older exemplar gets ranked), not path drift.
  * SYNTHETIC (controlled dose): take the FRESH map and BREAK a fraction of its
    referenced paths (rename them to non-existent files), simulating a map that has gone
    stale on exactly the layer it surfaces. This is the dose-response that finds where a
    stale map becomes worse than plain `ls` — the rigorous version of mex's
    `path`/`edges` checkers.
Arms:
  fresh        : task-map from HEAD                 (the B2b ceiling)
  stale-severe : task-map from a ~6-week commit     (authentic SEMANTIC drift)
  drift50      : fresh map, 50% of its paths broken (synthetic dose)
  drift100     : fresh map, ALL paths broken        (pure poison — worst case)
  ls           : no map, read_file + list_dir       (the discovery baseline to beat)
  blind        : no map, read_file only             (floor)
Hypothesis: misses rise and exemplar-reach decays with the broken-path dose; the
crossover where a stale map drops below `ls`/`blind` is the "must re-profile" threshold.

Reuses `phase_b2_navigation.run_one` (navigates the CURRENT corpus); old maps read from
git blobs (no checkout). Per-arm we report the measured DOSE (% of map paths now dead).

6 arms x 2 tasks x 3 seeds = 36 DeepSeek calls. Metered; STOPs on 429.
Reproduce: python rung3/phase_b3_map_drift.py
"""
from __future__ import annotations

import re
import statistics
import subprocess
import sys
import urllib.error
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from paths import context_root, corpus_root  # noqa: E402

sys.path.insert(0, str(context_root()))

import phase_a_foundation_survival as pa  # noqa: E402
from phase_b2_navigation import (  # noqa: E402
    TASKS, SEEDS, _corpus, _is_exemplar, run_one,
)
from phase_c_frozen_briefing import _api_key  # noqa: E402
from archolith_proxy.curator.briefing import PreFetchedFile  # noqa: E402
from archolith_proxy.curator.dependency_graph import render_task_map  # noqa: E402

REPO = corpus_root().parent          # forked/yawn.frontend (corpus_root() is .../src)
SRC_PREFIX = "src/"
EXTS = {".ts", ".tsx", ".js", ".jsx", ".css", ".astro", ".mjs"}

# Authentic staleness: one ~6-week commit (semantic drift; paths ~0% dead — see header).
STALE_COMMIT = ("stale-severe", "72a501e")


def _git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(REPO), *args],
                          capture_output=True, text=True,
                          encoding="utf-8", errors="replace").stdout


def _old_briefing_files(commit: str) -> list[PreFetchedFile]:
    """Build the briefing files (leaves + foundations) AS OF an old commit, read from
    git blobs. Paths are normalized to be relative to src/ (matching the fresh map)."""
    dirs = [SRC_PREFIX + d for d in pa.LEAF_DIRS] + [SRC_PREFIX + d for d in pa.FOUNDATION_DIRS]
    listed = _git("ls-tree", "-r", "--name-only", commit, "--", *dirs).splitlines()
    files: list[PreFetchedFile] = []
    for path in listed:
        path = path.strip()
        if not path or Path(path).suffix.lower() not in EXTS:
            continue
        content = _git("show", f"{commit}:{path}")
        rel = path[len(SRC_PREFIX):] if path.startswith(SRC_PREFIX) else path
        files.append(PreFetchedFile(path=rel, outline="",
                                    sections=[(1, content.count("\n") + 1, content)],
                                    relevance="score 0.5"))
    return files


def _task_map(files, noun: str) -> str:
    return render_task_map(files, noun, exemplar_suffixes=("Page.tsx",))


_PATH_RE = re.compile(r"[\w./-]+\.(?:tsx?|jsx?|css|astro|mjs)")


def _live(p: str, corpus: dict) -> bool:
    return p in corpus or p.removeprefix("src/") in corpus or ("src/" + p) in corpus


def _dead_pct(code_map: str, corpus: dict) -> tuple[int, int]:
    """How many distinct file paths the map mentions are NOT in the current corpus."""
    paths = {m.group(0).lstrip("/") for m in _PATH_RE.finditer(code_map) if "/" in m.group(0)}
    if not paths:
        return 0, 0
    return sum(1 for p in paths if not _live(p, corpus)), len(paths)


def _corrupt_map(code_map: str, frac: float, corpus: dict) -> str:
    """Break ``frac`` of the map's LIVE referenced paths by inserting a dead segment,
    simulating a map gone stale on the exact layer it surfaces. Deterministic (paths
    sorted), so the same fraction breaks the same paths across seeds."""
    live = sorted({m.group(0) for m in _PATH_RE.finditer(code_map)
                   if "/" in m.group(0) and _live(m.group(0).lstrip("/"), corpus)})
    n = round(len(live) * frac)
    for p in live[:n]:
        d, _, base = p.rpartition("/")
        code_map = code_map.replace(p, f"{d}/_moved/{base}")
    return code_map


def run() -> int:
    key = _api_key()
    corpus = _corpus()                       # CURRENT corpus (navigation target)
    fresh_files = pa.build_briefing().files  # CURRENT briefing (fresh map source)
    stale_lbl, stale_commit = STALE_COMMIT
    old_files = _old_briefing_files(stale_commit)

    ARMS = ["fresh", stale_lbl, "drift50", "drift100", "ls", "blind"]
    print(f"B3 map-drift — corpus {len(corpus)} files, seeds={SEEDS}, "
          f"tasks={[t[0] for t in TASKS]}, arms={ARMS}")
    print(f"{len(ARMS)*len(TASKS)*len(SEEDS)} DeepSeek calls\n")

    agg: dict[str, list[dict]] = {a: [] for a in ARMS}
    dose: dict[str, tuple[int, int]] = {}
    try:
        for seed in SEEDS:
            for tkey, noun in TASKS:
                fresh_map = _task_map(fresh_files, noun)
                arm_map = {
                    "fresh": fresh_map,
                    stale_lbl: _task_map(old_files, noun),
                    "drift50": _corrupt_map(fresh_map, 0.5, corpus),
                    "drift100": _corrupt_map(fresh_map, 1.0, corpus),
                    "ls": "", "blind": "",
                }
                if seed == SEEDS[0]:
                    for arm, cm in arm_map.items():
                        if cm:
                            d = _dead_pct(cm, corpus)
                            dose[arm] = tuple(map(sum, zip(dose.get(arm, (0, 0)), d)))
                for arm in ARMS:
                    r = run_one(corpus, code_map=arm_map[arm], with_ls=(arm == "ls"),
                                task_noun=noun, key=key, seed=seed)
                    agg[arm].append(r)
                    print(f"  seed{seed} {tkey:<8} {arm:<13} "
                          f"reads={r['reads']} miss={r['misses']} "
                          f"exemplar@{r['reads_to_exemplar'] if r['hit_exemplar'] else '-'}")
    except urllib.error.HTTPError as e:
        if e.code == 429:
            print("\n!! 429 RATE LIMIT — STOPPING per protocol. Partial; rerun later.")
            return 2
        raise

    print("\n" + "=" * 74)
    print(f"{'arm':<13}{'dead-paths':<12}{'reads':<8}{'misses':<9}{'exemplar%':<11}"
          f"{'reads->exmpl':<12}")
    print("-" * 74)
    for arm in ARMS:
        rs = agg[arm]
        dd, dt = dose.get(arm, (0, 0))
        dstr = f"{dd}/{dt}" if dt else "-"
        print(f"{arm:<13}{dstr:<12}"
              f"{statistics.mean(r['reads'] for r in rs):<8.1f}"
              f"{statistics.mean(r['misses'] for r in rs):<9.1f}"
              f"{100*sum(r['hit_exemplar'] for r in rs)/len(rs):<11.0f}"
              f"{statistics.mean(r['reads_to_exemplar'] for r in rs):<12.1f}")
    print("\n(dead-paths = map references not in the CURRENT corpus = the staleness dose;\n"
          " lower misses / reads->exemplar = sharper; the hypothesis: as dead-paths rise,\n"
          " misses rise and exemplar-reach decays toward/below `ls`.)")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
