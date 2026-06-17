# Rung 3 — 2nd-corpus recall confirm (bulletproof-react) — THE GATE

**Date:** 2026-06-16
**Type:** The standing hard gate on the rung-3 recall findings — a 2nd-corpus recall
confirm. The exemplar-aware combo (**xfcombo**) won briefing-only recall on ONE corpus
(`forked/yawn.frontend`, marker `*Page.tsx`, confirmed N=9). This re-runs the Phase-A
foundation-survival + Phase-D combo-recall protocol on a SECOND, differently-structured
template-convention corpus to test whether the win generalizes.

## Corpus 2
- **`forked/bulletproof-react/apps/react-vite/src`** @ corpus commit `9506629` (275-ish
  src files; the canonical "feature-folder React architecture").
- Convention is genuinely DIFFERENT from yawn.frontend: kebab-case
  `features/<x>/api/{get,create,...}-*.ts` (React Query + a shared axios `@/lib/api-client`
  + `zod` schemas + `@/types/api`) and `components/*-list.tsx`. **No `*Page.tsx`.** So a
  clean re-derivation here tests the MECHANISM, not the `Page.tsx` string.
- Recall contract: `bpr_contract.py` — 4 CORE (C1 query hook / C2 api-client-no-raw-fetch /
  C3 react-query / C4 list component) + 2 SOFT (C5 zod mutation / C6 `@/types/api`).
  Validated: **3/3 real features pass CORE, 0 false positives, 17/18 anchors (94%)**.

## Phase A — foundation survival (OFFLINE, free) — REPLICATES yawn
Briefing = 35 files (23 feature/leaf first, 8 shared-infra foundations LAST), ~11.3k tok
vs budgets {6000…1500}. Tracked foundations = `lib/api-client.ts`, `lib/react-query.ts`,
`types/api.ts`, … (the silent infra a feature request never names).

| budget | fifo | scored | topological |
|-------:|-----:|-------:|------------:|
| 6000 | 0/8 | 0/8 | **8/8** |
| 3000 | 0/8 | 0/8 | **7/8** |
| 1500 | 0/8 | 0/8 | **5/8** |

topological ≥ FIFO at every budget, strictly > at all 5 → **VERDICT PASS** (same as yawn:
foundations-first is the only fill that protects load-bearing files under truncation).

## Phase D — frozen-briefing recall (METERED) — DOES NOT replicate the xfcombo win
5 strategies × 3 new list-features (notifications / projects / tags), budget=3000,
deepseek-chat, temp=0.2, seed=7 (N=1/cell). Re-reading denied. `*` = core PASS.

| task | fifo | scored | topological | combo | xfcombo |
|------|------|--------|-------------|-------|---------|
| notifications | 4/6 | 4/6 | **5/6\*** | 3/6 | 4/6 |
| projects | 5/6\* | 4/6 | **5/6\*** | 4/6 | 5/6\* |
| tags | 4/6 | 4/6 | **5/6\*** | 4/6 | 5/6\* |

| strategy | mean recall | core-OK |
|----------|-------------|---------|
| **topological** | **5.00/6** | **3/3** |
| xfcombo | 4.67/6 | 2/3 |
| fifo | 4.33/6 | 1/3 |
| scored | 4.00/6 | 0/3 |
| combo (naive) | 3.67/6 | 0/3 |

## The finding (the gate result)
1. **The xfcombo recall win does NOT generalize.** On bulletproof-react **topological wins**
   outright (5.00/6, the ONLY arm core-OK on all 3 tasks); xfcombo is 2nd (4.67/6, 2/3).
   On yawn, xfcombo was THE winner and topological a strong-but-losing arm — the ranking
   FLIPS across corpora. naive combo is worst on both (3.67/6 here), consistent with yawn.
2. **Mechanism (traced per-anchor, not just aggregate).** Where xfcombo loses to topological
   it fails exactly **C1 — the query-template anchor** (the `useQuery`+`queryOptions`+`use<X>`
   hook), the very thing a good exemplar should prime. Two reinforcing causes:
   - On bpr the recall-critical convention (React Query + the api-client) is carried by the
     **FOUNDATIONS** (`lib/api-client`, `lib/react-query`, `types/api`), so foundations-first
     topological surfaces it directly. On yawn the convention lived in the **EXEMPLAR page**
     (a leaf), so the exemplar guarantee mattered and foundations didn't carry it.
   - xfcombo's deterministically-picked exemplar was `get-comments.ts` — bpr's **infinite-query
     variant** (`useInfiniteQuery`/`infiniteQueryOptions`). Guaranteeing it primed the WRONG
     query sub-pattern. **A wrong exemplar actively hurts** — the recall-axis echo of B2's
     "a misleading map is worse than none."
3. **Meta-vindication — this is what the gate was FOR.** The single-corpus xfcombo win was
   corpus-specific. The headline rung-3 lesson **"foundation ≠ recall-critical" is itself
   yawn-specific**: on bpr, foundation IS recall-critical. No single fill strategy wins both
   corpora; the locus of the recall-critical convention (foundation vs exemplar) is a
   corpus property.

## Robust takeaway for production
- **topological is the more robust default** across the two corpora (strong on yawn, winner
  on bpr). The **exemplar guarantee is high-variance and exemplar-SELECTION-sensitive** —
  worth it only where a single clean exemplar exists AND is correctly identified; a wrong
  pick (infinite vs plain query) regresses the exact anchor it targets.
- Implication for the corpus-profile design: the profiler must pick the RIGHT exemplar
  (e.g. exclude infinite-query/edge variants), or the guarantee backfires. Where it can't,
  fall back to topological, not naive combo.

## Honest caveats / limits
- **N=1 per cell (seed=7).** yawn's xfcombo win was confirmed at N=9; this is single-seed.
  The DIRECTION (topological wins, xfcombo doesn't dominate, naive combo worst) is clear and
  core-driven; exact means need a multiseed pass to firm up. A `seed∈{7,8,9}` rerun is the
  obvious follow-up before treating the flip as quantitatively settled.
- **Contracts differ by corpus** (they must — different conventions), so recall NUMBERS are
  not cross-corpus comparable; only the WITHIN-corpus ranking is. Within bpr:
  topological > xfcombo > fifo > scored > combo.
- Scores cluster 4–5/6 (mild ceiling); **core-OK count is the sharper discriminator**
  (topological 3/3 vs xfcombo 2/3 vs others 0–1/3).
- One feature family (list/browse screens), one model (deepseek-chat). Generalization across
  task families is still open (roadmap C1).

## Reproduce
```
git clone --depth 1 https://github.com/alan2207/bulletproof-react   # corpus @ 9506629
export ARCHOLITH_CORPUS=.../bulletproof-react/apps/react-vite/src
cd archolith-bench/experiments/context-quality/rung3/corpus2-bpr
python bpr_contract.py                 # contract self-validation (offline)
python bpr_corpus.py                   # Phase A foundation survival (offline)
python bpr_phase_d.py                  # Phase D recall (15 deepseek-chat calls; STOPs on 429)
python bpr_phase_d.py --rescore        # re-score persisted phaseD-output offline
```

## Artifacts
- `bpr_contract.py` (recall scorer), `bpr_corpus.py` (Phase A + briefing), `bpr_phase_d.py`
  (Phase D + `--rescore`), `phaseD-output/` (the 15 generated features, committed as evidence).
