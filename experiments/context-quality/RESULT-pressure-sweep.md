# Scored-selection file-budget pressure sweep (Phase 5 follow-up)

Offline, deterministic, no LLM/cost. Driver: `archolith-context/scripts/scored_selection_pressure.py`
(`PYTHONPATH=. python scripts/scored_selection_pressure.py`). Answers the question the live A/B could
not: once the briefing EXCEEDS the assembler budget, does scored selection (Phase 4) protect the
convention-defining files better than FIFO insertion order — and where does recall crack?

## Setup
- Convention (recall-critical) files = the 4 REAL seed files (`mobile.css`, `api.js`, `cards.html`,
  `card-detail.html`). + 14 synthetic distractor `component_*.js` files (~400 tok, generic, no
  conventions). Briefing places distractors FIRST, convention files LAST = worst case for FIFO.
- Query = the under-specified Sealed-page intent ("...sealed products... expected value (EV)").
- Metric = how many of the 4 convention files survive `build_deterministic_context` at each budget.

## Result

```
=== UNIFORM importance (prepper did not differentiate, 0.5 all) ===
  budget  #files |  FIFO conv kept           |  SCORED conv kept
    6000      18 |  4/4 (all fit, no pressure)|  4/4
    4000      18 |  1/4 [mobile]             |  2/4 [api,cards]
    3000      18 |  0/4 []                   |  2/4 [api,cards]
   <=2000     18 |  0/4 []                   |  2/4 [api,cards]   (stable down to 500)

=== PREPPER-FAVORED (conv files 0.85, distractors 0.5) ===
    4000      18 |  1/4 [mobile]             |  4/4 [all]
    3000-1500 18 |  0/4 []                   |  4/4 [all]
    1000- 700 18 |  0/4 []                   |  3/4 [mobile,api,cards]
     500      18 |  0/4 []                   |  2/4 [api,cards]
```

Per-file score (uniform regime): `cards.html` rel=0.21, `api.js` rel=0.07 (matches "sealed"->sealedList),
`mobile.css` rel=0.00, `card-detail.html` rel=0.00, distractors rel=0.00.

## Findings (the informative failure)

1. **The boundary:** pressure begins below ~4000 tokens (with 14 distractors). At/above 6000 everything
   fits — which is exactly why the live Phase-5 seeded A/B showed no scored-selection effect (~8 small
   files, ~4k tok, never pressured). To exercise scored selection you MUST exceed the budget.

2. **FIFO fails catastrophically under pressure:** with distractors ahead, FIFO keeps 1/4 at 4000 and
   **0/4 at <=3000** — every convention-carrying file evicted. Recall would crack completely. This is the
   failure mode the curator could hit on a large, file-heavy session.

3. **Scored selection strictly beats FIFO** wherever pressure exists (0/4 -> 2-4/4). The Phase-4
   mechanism works and matters — once there is something to evict.

4. **Scored selection's OWN limitation (exposed):** under realistic UNIFORM importance, keyword
   relevance keeps exactly the files whose vocabulary overlaps the query — `api.js` ("sealed"->
   `sealedList`) and `cards.html` (list/card). That is recall-SUFFICIENT (the agent sees `.list-row` in
   cards.html and the helper in api.js). BUT **`mobile.css` is always dropped** (rel=0.00): CSS
   class-name vocabulary never matches a feature-oriented query, so keyword relevance is **blind to the
   foundational stylesheet**. If a turn needed the exact `--accent` value or a class not shown in a
   surviving usage file, scored selection would NOT protect it.

5. **Importance is what protects the definition file, not relevance.** In the prepper-favored regime
   (conv files scored 0.85) scored selection keeps 4/4 down to 1500. So the value of scored selection
   under pressure depends on the PREPPER assigning good importance to foundational files — keyword
   relevance alone cannot rescue a pure-definition file. (Mirrors the cth.mcp.memory importance finding:
   intrinsic importance matters precisely where query-vocabulary overlap is absent.)

## Implications / next rungs
- **Phase 4 scored selection is validated as net-positive under pressure** (vs FIFO catastrophe), with a
  known blind spot: vocabulary-mismatched definition files rely on the prepper's importance score.
- **Hardening candidate:** give file-type a floor in scoring (e.g. a stylesheet/config a small importance
  boost, or always keep >=1 `.css`), OR have the prepper explicitly rate "foundational" files. Test the
  same sweep after.
- **For a live confirmation:** a file-heavy seeded session (20+ components) at a reduced
  `ASSEMBLER_TOKEN_BUDGET` (e.g. 2000) with briefings kept fresh (deterministic hot path) would show the
  FIFO-vs-scored recall gap end-to-end. Cheaper/clearer to keep finding boundaries offline first.
