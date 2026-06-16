# Rung 3 Phase A — Foundation Survival Under Real File Pressure (RESULT)

**Date:** 2026-06-16
**Type:** OFFLINE mechanism test (Q1 of `PROTOCOL-rung3-pressure.md`). No proxy, no agent, no API
calls. Reproduce: `python rung3/phase_a_foundation_survival.py`.
**Corpus:** `projects/forked/yawn.frontend/src` (real Astro+TSX app, HEAD `75ca56b`).

## Setup
A realistic curated briefing was built from the corpus: **115 files** — 60 exemplar feature/leaf
files (whole `features/{set-v3,cards-v3,card-index,graded-v3,sealed}` dirs) placed FIRST, and the
shared `data/`+`domain/`+`layouts/`+`ui/` files placed LAST (worst case for FIFO). Briefing ~70,212
tok, so **every** test budget (6000..1500) forces heavy eviction. We score survival of 8 tracked
foundations — the silent anchors a feature request never names.

## Result — topological is the ONLY strategy that protects foundations
| budget | FIFO | scored | topological |
|--------|------|--------|-------------|
| 6000 | 0/8 | 0/8 | **5/8** |
| 4000 | 0/8 | 0/8 | **5/8** |
| 3000 | 0/8 | 0/8 | **5/8** |
| 2000 | 0/8 | 0/8 | **4/8** |
| 1500 | 0/8 | 0/8 | **3/8** |

(Numbers are post-R3a; pre-R3a 1500 was 4/8 — the small shift is barrel index files now competing for
budget, see the R3a section. The headline is unchanged.)

- **FIFO keeps 0/8 at every budget** — the 60 feature files (inserted first) consume the entire
  budget; every foundation, placed last, is evicted. This is the failure the direction predicted.
- **Scored keeps 0/8 too** — the generative-agents scorer is BLIND to the pure-definition
  foundations: `apiClient`/`slug` share no vocabulary with a "Decks browse screen" query, so
  they score low and lose to query-matching leaves. (The exact blindness `RESULT-pressure-sweep.md`
  found, now confirmed on a real 70k-token briefing.)
- **Topological keeps 3-5/8** — by ordering on dependency in-degree (most-depended-upon first), the
  load-bearing foundations survive truncation with no LLM and no importance signal.

**Pre-registered decision rule: PASS.** Topological >= FIFO at every budget and strictly > FIFO at
all 5 budget levels -> Phase B (live) is justified.

## Why topological keeps 3-5/8, not 8/8 (honest breakdown)
In-degree is computed over the BRIEFING subset. Per-foundation (in-degree within briefing, size):

| foundation | in-deg | chars | topological | reason |
|------------|--------|-------|-------------|--------|
| `data/apiClient.ts` | 10 | 1.8k | **keep** | highest in-degree, small |
| `domain/slug.ts` | 7 | 1.1k | **keep** | high in-degree, small |
| `domain/models/Common.ts` | 6 | 0.6k | **keep** | high in-degree, tiny |
| `domain/formatters.ts` | 4 | 4.1k | **keep** | mid in-degree |
| `data/api-types.ts` | 3 | 14k | DROP | lower rank AND too big for the budget tail |
| `data/repository.ts` | 2 | 11k | DROP | low in-degree + large |
| `domain/color-styles.ts` | **0** | 0.8k | DROP | **no importer IN the briefing subset** (composition) |
| `layouts/Layout.astro` | **0** | 11k | DROP | **no importer IN the briefing subset** (composition) + large |

The 3-4 drops split into two honest buckets:
1. **Composition artifact, NOT an extraction miss (in-degree 0):** `color-styles` and `Layout` have
   zero in-degree *within this briefing subset* only because their importers were not included — the
   chosen leaves are `features/*` React components, but `Layout.astro` is imported by `pages/*.astro`
   and `color-styles` by files outside the five feature dirs. **GLOBALLY the extractor finds them fine**
   (in-degree 21 and 5). The earlier draft of this doc mislabeled these as "@/ alias extraction
   misses"; that was wrong — verified: they are imported via `@/layouts/Layout.astro` (21x) and
   `@/domain/color-styles` (5x), both of which the basename matcher already resolved. Lesson: pick
   tracked foundations that actually have in-subset dependents (only 6 of the 8 here do).
2. **Genuinely lower rank + large (`repository`, `api-types`):** correctly deprioritized relative to
   the higher-in-degree foundations, and too large to fit the remaining budget once the small
   high-in-degree ones are placed. A size/rank interaction, not a bug.

## R3a — extractor coverage upgrade (done 2026-06-16, re-run above)
R3a added relative-path resolution (against the importer's dir, fixing `types.ts` collisions),
alias/absolute SUFFIX matching, and `<dir>/index.*` BARREL resolution to `dependency_graph.py`.
Effect on the real corpus:
- edges **471 -> 562 (+91)**; files with an outgoing edge **58% -> 61%**; depended-upon **240 -> 253**.
- it SURFACED barrel index files as real foundations: `domain/models/index.ts` in-degree **47** (top),
  `ui/index.ts` **36** — previously invisible because `from '@/ui'` resolved to nothing.
- **Phase A foundation-survival was essentially unchanged** (5/5/5/4/3 vs 5/5/5/4/4). This is the
  honest payoff: R3a improved extraction *fidelity* (correct, unit-tested), but did NOT move the Phase A
  number, because that number was limited by briefing COMPOSITION (bucket 1 above), not by extraction.
  The topological-vs-FIFO/scored headline is robust to R3a.

## Verdict
- **Q1 answered: YES.** Under real budget pressure, topological fill protects foundations that FIFO
  and scored protect not at all (0/8 -> 3-5/8). The Rung-2 mechanism works on a real corpus.
- **Strongest single result of the deterministic-layers thread so far:** a pure sort, no LLM, no
  importance signal, is the only strategy that keeps any load-bearing file alive under pressure.
- **R3a done; it was worth it for extraction correctness but is not what gates Phase A.** The real
  Phase-A modeling lever is briefing composition (include the foundations' actual importers). For
  Phase B the live prepper supplies the briefing, so this modeling concern does not transfer.

## Threats (carried)
- **Foundation != recall-critical** remains the open risk: keeping `apiClient`/`slug` matters only if
  the agent needs them to follow conventions. Phase B's contract-checker recall metric, not Phase A,
  settles whether survival -> better output.
- Briefing construction (which leaves/foundations) is a modeling choice; the prepper's real briefings
  may differ. The qualitative result (FIFO/scored 0, topological >0) is robust to the exact set.
