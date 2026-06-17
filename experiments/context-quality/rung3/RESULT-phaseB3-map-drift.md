# Rung 3 — B3: map DRIFT → navigation (how stale is too stale?)

**Date:** 2026-06-16
**Type:** Metered navigation experiment (extends B2/B2b/B2c). The task-ranked map +
`list_dir` is the best navigation design — but always tested with a FRESH map. Open
production question (adapted from mex's `path`/`edges`/`staleness` drift checkers,
`.agent/research/archolith-vs-mex-prior-art.md`): a derived map goes stale as code
changes — how much does that cost, and how often must we re-profile?
**Harness:** `phase_b3_map_drift.py` (reuses `phase_b2_navigation.run_one`; navigates the
CURRENT `forked/yawn.frontend` corpus, varying ONLY the map per arm). 6 arms × 2 tasks
(decks, bundles) × 3 seeds = 36 deepseek-chat calls, N=6/arm.

## Two kinds of staleness tested
- **Authentic** — task-map built from a real ~6-week commit (`72a501e`, before the v3
  pages existed) via git blobs. **Pre-flight finding:** the task-ranked map is naturally
  drift-RESISTANT — it surfaces only the top in-degree foundations + the task exemplar,
  which are the STABLE core; the real refactor churn (~13% of files, `e5a5057` "organize
  sub-components into components/ dirs") is all in the sub-component TAIL the map never
  names. So the old map's surfaced paths are ~0–18% dead, and the arm tests SEMANTIC drift
  (an older exemplar gets ranked), not path drift.
- **Synthetic dose** — take the FRESH map and BREAK a fraction of its referenced paths by
  moving them to a non-existent dir (`features/sealed/SealedPage.tsx` →
  `features/sealed/_moved/SealedPage.tsx`). This models the DOMINANT real refactor (a file
  changes directory but keeps its name) at a controlled dose (50%, 100%).

## Result (mean, N=6/arm)
| arm | dead-paths (dose) | reads | misses | **exemplar %** | **reads→exemplar** |
|-----|------------------|-------|--------|----------------|--------------------|
| fresh | 0/23 | 16.3 | 6.2 | 100 | **1.0** |
| stale-severe (6wk) | 4/22 | 15.0 | **4.3** | 100 | **1.0** |
| **drift50** | 12/23 | 14.3 | **9.0** | **50** | 4.5 |
| drift100 | 23/23 | 16.5 | 8.3 | 100 | 1.0 |
| ls (read+list_dir) | – | 11.0 | **0.5** | 100 | 4.5 |
| blind | – | 0.0 | 8.0 | 0 | 8.0 |

## Findings
1. **A realistically-stale map does NOT degrade navigation.** The authentic 6-week-old map
   matches fresh — 100% exemplar, exemplar on the first real read (1.0), and FEWER misses
   than fresh (4.3 vs 6.2). Task-ranked maps are **drift-resistant** because the layer they
   surface (high-in-degree foundations + a valid exemplar page) is exactly the layer
   refactors leave alone; churn happens in the sub-component tail the map omits. **Production
   answer: re-profiling can be INFREQUENT** — realistic drift barely touches the surfaced set.
2. **Partial staleness is the DANGER ZONE — worse than a fully-broken map.** drift50 is the
   worst arm: exemplar-reach **halves (50%)**, misses peak (9.0), and it is now WORSE than
   plain `ls` (100% exemplar, 0.5 misses). drift100 — every path obviously broken — RECOVERS
   to 100% exemplar @ 1.0. The mechanism: a 50%-stale map is **deceptive** (the working half
   keeps the agent trusting it, the broken half silently strands it on the task whose exemplar
   went stale); a 100%-broken map is **self-evidently junk**, so the agent discards the dir
   paths and recovers the real files from the still-intact FILENAMES (our corruption moves
   dirs, keeps names — the dominant real-refactor shape). **The map's durable signal is the
   set of filenames (what exists); the fragile signal is the directory path.**
3. **`ls` stays the safe floor** (100% exemplar, 0.5 misses) but is SLOWER to the exemplar
   (reads→exemplar 4.5 vs fresh/stale 1.0). The fresh/lightly-stale map's value — exemplar on
   the FIRST read — is real and survives realistic aging; the risk is not age but a
   PARTIALLY-broken surfaced set.

## Production implication (the answer to "how often re-profile?")
- **Frequency matters less than a freshness GUARD.** Because realistic churn doesn't break the
  surfaced paths, frequent re-profiling buys little. Because a PARTIALLY-stale map is worse
  than no map, the protective move is a mex-style `path`/`edges` check before surfacing: if
  more than a small fraction of the map's referenced paths are dead, **drop the whole map and
  fall back to `ls`** — do NOT surface it half-broken (that is the drift50 failure). Dropping
  individual dead entries is fine; surfacing a deceptively-partial map is the trap.
- This directly backs the corpus-profile design's "freshness guard before emit" note and the
  commit-triggered re-profile being a CHEAP guard, not a frequent necessity.

## Honest caveats / limits
- **N=6/arm (2 tasks × 3 seeds)**, one corpus, one model (deepseek-chat). Directionally clear;
  the non-monotonic drift50 > drift100 cost is consistent across seeds but deserves a wider
  dose sweep (10/25/75%) to map the full curve.
- **drift50's exemplar loss is task-split** (decks reaches the exemplar every seed; bundles
  never does) because the DETERMINISTIC corruption broke the bundles-relevant paths in all
  seeds. So "50% exemplar" = "the task whose exemplar landed in the stale half is stranded,"
  not a smooth 50% per task. The lesson (partial staleness silently strands) holds; the exact
  % is an artifact of which paths went stale.
- The synthetic corruption is **filename-preserving (dir-move)** — the dominant refactor, and
  why drift100 recovers. A DELETE/RENAME-the-file staleness would not leave a recoverable
  filename hint and would likely hurt more at 100%; that is a separate dose to run.

## Reproduce
```
export ARCHOLITH_CORPUS=.../forked/yawn.frontend/src      # (or leave unset — it's the default)
cd archolith-bench/experiments/context-quality/rung3
python phase_b3_map_drift.py          # 36 deepseek-chat calls; STOPs on 429
```

## Artifacts
- `phase_b3_map_drift.py` — the drift harness (authentic old-commit map via git blobs +
  synthetic dose via `_corrupt_map`; reuses the B2 navigation loop).
