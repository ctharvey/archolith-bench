# Layer-3 Output-Contract — Retroactive Test (RESULT)

**Date:** 2026-06-15
**Rung:** #1 of `archolith/.agent/plans/archolith-context-deterministic-layers-direction.md`
(Layer-3 validation; offline; no agent runs; no model calls).
**Harness:** `contract/contract_check.py` (pure stdlib) + `contract/divergent_sample.html`.
Reproduce: `cd experiments/context-quality/contract && PYTHONIOENCODING=utf-8 python contract_check.py`.

## Question (from the direction doc)
"Build a contract from the seed vocabulary and run it against the existing Phase-5 generated
pages: does it PASS the convention-following pages, and would it FLAG divergence?" This validates
the "unit tests for LLM output" idea against real artifacts, at zero cost.

## The contract (derived from `seeded/_seed/` + PROTOCOL.md convention table)
A resident ~40-token convention card (the PREVENT layer) plus six machine-checkable anchors, each
tagged with a remediation tier from the design's cost ladder:

| id | anchor | tier | rule |
|----|--------|------|------|
| C1 | row-class reuse | **auto-fix** | list pages use `.list-row`, not an invented `*-row`/`*-item` class |
| C2 | row children | annotate | `.list-row` carries `.row-body/.row-name/.row-meta` |
| C3 | metric slot | annotate | the metric (price/EV) sits in `.row-meta` |
| C4 | color tokens | **auto-fix** | no hardcoded hex that DUPLICATES a theme token (`#16a34a`->`var(--accent)`) |
| C5 | detail header | annotate | detail pages use `<header class=detail-header><a class=back-btn>` |
| C6 | api helper | annotate | import + call the correct named `./api.js` helper; no raw `fetch()` in a page |

Checks return PASS / FAIL / **NA** (not applicable to that page type — e.g. C5 on a list page).
A page passes the contract iff it has zero FAILs.

### The false-positive guard (the load-bearing design choice)
The seed sets the accent INSIDE `.list-row .row-meta`, so a page that correctly reuses the class
has zero `var(--accent)` of its own — that is correct recall, not a miss (this is exactly the trap
the manual grade in `RESULT-3arm-seeded.md` called out). The contract therefore does NOT require
`var(--accent)` per page; C4 only fails on hex literals that **duplicate an existing token**. A hex
with no token (e.g. `market.html`'s `#ef4444` for a negative delta) is reported as an accepted
*extension*, not a violation. Without this distinction the contract would false-positive on
`market.html`.

## Results

### Seed self-check — 2/2 OK
The files that DEFINE the conventions pass their own contract (`cards.html`, `card-detail.html`).
`card-detail.html` exercises C5 (detail-header/back-btn) PASS — the only page in the corpus that is
a detail page; all 18 generated pages are list pages, so C5 is NA there.

### 18 generated pages (3 arms x 6 pages) — 18/18 OK, ZERO false positives
| arm | sealed | graded | series | transactions | sets | market |
|-----|--------|--------|--------|--------------|------|--------|
| passthrough | OK | OK | OK | OK | OK | OK |
| curator-off | OK | OK | OK | OK | OK | OK |
| curator-on  | OK | OK | OK | OK | OK | OK |

The contract passes every convention-following page across all three context arms with no false
positives. `market.html` passes C4 via the extension-hex rule above.

### Divergence fixture — FLAGGED, then auto-repaired
`divergent_sample.html` (a sealed page violating every mechanical anchor) is flagged on
**C1, C3, C4, C6** (C2 starts NA because, with no `.list-row`, the child-element check has nothing
to attach to).

Deterministic auto-fix (zero model calls) applied:
- `C4 #16a34a -> var(--accent)`
- `C1 .card-row -> .list-row (2x)`

After auto-fix: C1 PASS, C4 PASS. Remaining FAILs are C2/C3/C6 — correctly left to the *annotate*
tier (they need structural or endpoint knowledge a regex cannot safely supply). Note the honest
emergent behavior: repairing the row class (C1) UNMASKS the C2 child-element violation that was
hidden while the row class was wrong — the contract gets stricter, not laxer, after a fix.

## Verdict (against the rung's two questions)
1. **Passes convention-following pages?** YES — 18/18 with zero false positives, plus the 2 seed
   files. The contract is usable, not noisy.
2. **Flags divergence?** YES — every mechanical violation in the fixture was detected, and the two
   auto-fix-tier violations were repaired deterministically at zero model cost; the rest were
   correctly routed to annotate.

This validates Layer 3 ("output contracts as unit tests for LLM output") against real artifacts:
the detect + mechanical-auto-fix + annotate ladder behaves as the design claims, at zero cost.

## Honest limits (do not lose)
- **Only 1 detail page in the corpus.** C5 is exercised once (seed `card-detail.html`); the 18
  generated pages are all list pages, so the detail-header anchor is under-tested on agent output.
- **The corpus is "clean."** All 18 pages already follow conventions (the manual grade found perfect
  recall), so the false-positive test is strong but the detection test rests on the synthetic
  fixture, not on real agent divergence. Real divergence would be the stronger evidence — capture it
  if a future agent run produces a non-conforming page.
- **Auto-fix covers mechanical divergence only** (hex->var, invented row class). Structural misses
  (missing `.row-meta`, raw `fetch` needing an endpoint->helper mapping) are detect+annotate, not
  auto-fix — matching the design's stated boundary.
- This is a RETROACTIVE validation of the checker, not the production Layer-3 module. Wiring a
  contract module into the proxy/`archolith-audit` line and proving it earns its keep live remains a
  later rung.

## Artifacts
- `contract/contract_check.py` — contract + checker + deterministic auto-fixer + retro-test harness.
- `contract/divergent_sample.html` — checked-in divergence fixture.
- (`contract/divergent_sample.fixed.html` is regenerated by each run; not committed.)
