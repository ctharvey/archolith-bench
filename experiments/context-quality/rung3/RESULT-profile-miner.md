# Rung 3 — Corpus Profiler (Phase 2): derive the combo's exemplar marker, no hardcoding

**Date:** 2026-06-16
**Type:** Offline validation of the deterministic corpus profiler
(`archolith-context/archolith_proxy/curator/corpus_profile.py`). No LLM. Reproduce:
`python rung3/derive_profile.py`.

## Why
The exemplar-aware combo fill (Phase D winner) needs to know the EXEMPLAR marker (the template the
model imitates). Phase D hardcoded it (`assembler_exemplar_suffixes="Page.tsx"`). The corpus-profile
design note's premise: a codebase declares its conventions BY REPEATING them, so the marker can be
mined deterministically — the filename pattern that recurs across the most sibling feature dirs.

## Result on the real corpus (`forked/yawn.frontend/src`, 275 files)
Derived exemplar marker: **`Page.tsx`** — exactly the previously-hardcoded value, with no hardcoding.

Top recurring component patterns (pattern -> # distinct sibling dirs):
| #dirs | pattern | role |
|------:|---------|------|
| 15 | `Data.ts` | hook (`use*Data.ts`) — recurs, but `.ts` (not a component) -> NOT an exemplar |
| 15 | `Page.tsx` | **the screen template -> derived exemplar marker** |
| 10 | `Page.module.css` | the page's co-located styles |
| 6 | `Chart.tsx` | a secondary component template |
| 5 | `Table.tsx` | ... |

Foundations (top in-degree): `domain/models/index`, `ui/index`, `data/apiClient`, `domain/slug`,
`data/repository`, `layouts/Layout.astro`, ... — matches the topological analysis.

## What this validates
- The miner derives the SAME marker the human hardcoded (`Page.tsx`), from corpus repetition alone —
  so `assembler_exemplar_suffixes` no longer has to be hand-authored.
- The component-extension filter correctly distinguishes the EXEMPLAR (a `.tsx` template, `Page.tsx`)
  from an equally-recurring NON-template convention (`Data.ts`, the hook — a `.ts`). In-degree gives
  the foundations. The three roles (exemplar / foundation / relevant) are now derivable, not hardcoded.
- Because the derived marker == the hardcoded one, the Phase-D recall win transfers by construction
  (no need to re-spend on the recall experiment).

## Honest limits / next
- **Generalization unproven:** "most-recurring sibling component pattern" is validated on ONE corpus
  (a v3-feature React app). Validate on a 2nd, differently-structured corpus before trusting the miner
  as primary; the LLM profiler (design note) is the fallback for corpora whose conventions are not
  surface-recurring.
- **Not yet wired to a cached profile on the hot path** — this commit replaces hand-authoring of the
  marker; the cached-profile + memory-graph integration (design note Option B) is the later step.

## Artifacts
- `rung3/derive_profile.py` — reproducible runner.
- `archolith-context/.../corpus_profile.py` + `tests/test_curator/test_corpus_profile.py` (4 tests).
