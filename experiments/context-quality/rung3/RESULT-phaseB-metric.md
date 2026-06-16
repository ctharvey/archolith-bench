# Rung 3 Phase B — Recall Metric (feature contract) — VALIDATED, offline

**Date:** 2026-06-16
**Purpose:** Build + validate the automated recall scorer Phase B needs BEFORE spending on live
agent runs. Applies the Rung-1 "contract as recall metric" idea to the real `forked/yawn.frontend`
corpus. Offline, no agent, no API. Reproduce: `python rung3/feature_contract.py`.

## The contract (`rung3/feature_contract.py`)
A new feature screen in this app is a FOLDER, so the contract scores a directory, not a single file.
Conventions derived from the real conforming features (cards-v3 / set-v3 / graded-v3 / sealed /
card-index / series / home / graded):

| id | anchor | tier | rule |
|----|--------|------|------|
| F1 | page default export | retry | a `<Name>Page.tsx` with `export default` |
| F2 | data hook | annotate | a `use<Name>Data.ts` exporting `use<Name>Data` (view/data split) |
| F3 | data layer | annotate | data via `@/data/apiClient`/`repository`; NO raw `fetch(` in the feature |
| F4 | css module | annotate | a `*.module.css` imported `import s from './*.module.css'` |
| F5 | ui barrel (soft) | annotate | imports from `@/ui` |
| F6 | domain reuse (soft) | annotate | imports from `@/domain/*` |

CORE = F1-F4 (a core FAIL = a broken convention). F5/F6 are SOFT (counted in the recall score, not a
hard FAIL — a simple feature may legitimately skip them). Per-feature recall = PASS anchors / scored
anchors; Phase B's per-arm recall = mean across the generated screens.

### Layer-3 boundary, made concrete (honest)
Every anchor here is **annotate/retry**, none are regex **auto-fix** — the opposite mix from the seed
HTML contract (where `.card-row`->`.list-row` and hex->token WERE auto-fixable). Lesson: Layer-3
mechanical auto-fix shines for token/class conventions; **architectural structure** (folder layout,
view/data split, data-layer routing) is detect + prevent/annotate, not auto-fix.

## Validation
| | result |
|--|--|
| ground-truth conforming features | **8/8 pass CORE, 0 false positives** |
| ground-truth mean recall | **47/48 anchors (97%)** (lone miss: `graded` soft F6 `@/domain`) |
| divergence fixture (`divergent_feature/DecksPage.tsx`) | **FAILs core** F2/F3/F4 (no hook, raw `fetch`, no css module) |

The fixture passes F1 (it does default-export a `DecksPage`) — correct; it only breaks the
hook/data-layer/css conventions, and the contract flags exactly those.

### A real discrimination signal (not a false positive)
`transactions` was initially listed as ground truth and the contract FAILed it on F1. Investigation
showed `transactions` is a genuine structural VARIANT — table components
(`FlatTransactionTable.tsx`...) consumed directly by `pages/transactions.astro`, with no `*Page.tsx`.
The contract was right to flag it; it was excluded from ground truth as not-the-target-convention.
This is evidence the contract discriminates real structure, not just surface tokens.

## Status
Phase-B recall metric is READY and validated. When Phase B runs (live 3-arm: passthrough vs
curator+FIFO vs curator+topological), point `feature_contract.py <generated-feature-dir>` at each
arm's output; per-arm recall = mean core+soft anchors. Decision rule per `PROTOCOL-rung3-pressure.md`
(topological earns its keep IFF A3 recall > A2 recall at no material extra cost; combo beats doing
nothing IFF >= passthrough).

## Artifacts
- `rung3/feature_contract.py` — the feature-level contract + validation harness.
- `rung3/divergent_feature/DecksPage.tsx` — divergence fixture.
