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

> **READ THIS FIRST — the single-seed read below was CORRECTED by the multi-seed firm-up.**
> The N=1 (seed=7) table first read as "xfcombo did not generalize; topological won outright."
> The N=9 multi-seed run (`bpr_phase_d_multiseed.py`, see the **Multi-seed firm-up** section)
> shows that was an **N=1 artifact**: xfcombo and topological are **co-leaders** on bpr. The
> retained-as-history single-seed analysis follows; the corrected conclusion is the multi-seed one.

## Phase D — frozen-briefing recall (METERED) — single-seed (N=1), SUPERSEDED
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

## Single-seed read (N=1) — RETAINED AS HISTORY, corrected below
At seed=7 the table read as: topological wins outright (5.00/6, 3/3 core), xfcombo 2nd
(4.67/6, 2/3), and xfcombo failed exactly the **C1 query-template anchor** on the cell it
lost — its guaranteed exemplar was `get-comments.ts`, bpr's **infinite-query variant**, which
appeared to prime the wrong query sub-pattern. That looked like "the win does not generalize;
foundation IS recall-critical here." **The multi-seed firm-up shows this was an N=1 draw, not
a real flip** (DeepSeek's `seed` is best-effort, not deterministic — re-running "seed 7" in the
multi-seed pass did not even reproduce that miss). Read the next section as the real result.

## Multi-seed firm-up (N=9) — the CORRECTED conclusion (`bpr_phase_d_multiseed.py`)
3 seeds {7,8,9} × 3 tasks × 5 strategies = 45 calls, n=9/strategy. Graded score in [0,6].

| strategy | graded mean | floor (min) | stdev | binary mean | core-OK |
|----------|-------------|-------------|-------|-------------|---------|
| **xfcombo** | **4.94** | 4.5 | **0.16** | 4.89 | 8/9 |
| **topological** | 4.89 | 4.0 | 0.31 | 4.89 | **9/9** |
| fifo | 4.67 | 4.5 | 0.24 | 4.33 | 3/9 |
| scored | 4.39 | 3.5 | 0.31 | 3.56 | 0/9 |
| combo (naive) | 4.17 | 3.5 | 0.47 | 3.67 | 0/9 |

1. **xfcombo did NOT fail to generalize — it is co-best with topological on bpr.** They tie on
   binary recall (4.89); xfcombo edges the graded mean (4.94) with the tightest variance
   (stdev 0.16, floor 4.5); topological edges core reliability (9/9 vs 8/9 — xfcombo broke core
   on 1/9 cells: tags @ seed9, the C1 anchor). The single-seed "topological wins outright" was
   the N=1 mirage the gate's own caveat predicted.
2. **What DOES hold firmly across both corpora:** the two STRUCTURE-AWARE arms (xfcombo,
   topological) are the reliable top tier; **scored / naive-combo / fifo are unreliable**
   (core-OK 0/9, 0/9, 3/9 — they collapse on some cells). naive combo worst, as on yawn.
3. **The exemplar-selection caveat survives, softened.** A wrong exemplar (the infinite-query
   variant) can still cost a cell — it did, 1/9 — but it does NOT systematically break xfcombo.
   "Pick the right exemplar" remains a real profiler concern, not a disqualifier.

## Robust takeaway for production (multi-seed)
- **Both xfcombo and topological are good cross-corpus defaults.** topological has the best core
  RELIABILITY on bpr (9/9) and was strong on yawn; xfcombo has the best graded mean + tightest
  variance on bpr AND was the decisive winner on yawn. The decisive-margin xfcombo win is
  yawn-specific, but xfcombo's TOP-TIER standing generalizes. There is no flip — both
  structure-aware arms travel.
- The clear, generalizing negative: **do not ship scored / naive-combo / fifo** as the recall
  fill — they're unreliable on both corpora.
- corpus-profile implication (unchanged, softened): the profiler should pick the RIGHT exemplar
  (exclude infinite/edge variants); where it can't, topological is the safe fallback — never
  naive combo.

## Honest caveats / limits
- **Two corpora, one feature family (list/browse), one model (deepseek-chat).** Multi-seed (N=9)
  now covers both corpora; task-family generalization is still open (roadmap C1).
- **`seed` is best-effort on DeepSeek** — even fixed-seed runs vary, which is exactly why the
  multi-seed pass (not a single fixed seed) is the trustworthy unit. The single-seed section is
  kept only to document the correction.
- **Contracts differ by corpus** (different conventions), so recall NUMBERS are not cross-corpus
  comparable; only the WITHIN-corpus ranking + the qualitative tiering travel.
- Scores cluster 4–5/6 (mild ceiling); **core-OK count is the sharper discriminator** (xfcombo
  8/9, topological 9/9 vs scored/combo 0/9).

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
