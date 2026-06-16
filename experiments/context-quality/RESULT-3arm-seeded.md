# Seeded-Recall A/B — 3-arm run (RESULT)

Per `PROTOCOL.md` (3-arm seeded recall). Agent = opencode on direct DeepSeek (`api.deepseek.com/v1`,
`deepseek-chat`/`v4-flash`). Claude leads each page as a fresh user turn via the harness.

## Run metadata
- **Date:** 2026-06-15
- **Metered helper key baseline (input tokens, before any arm):** 1,839,957
- **Proxy:** :9800, two_curator + worker + deterministic, PREPPER_LATENCY_BUDGET_MS=60000,
  ASSEMBLY_MIN_INPUT_TOKENS=5000, COLD_START_TURNS=3. Restart A = `ASSEMBLER_SCORED_SELECTION=false`.
- **Arms / sessions:**
  - passthrough — `s5-pass-20260615` — route `archolith/deepseek-v4-flash-passthrough`
  - curator-off — `s5-coff-20260615` — route `archolith/deepseek-v4-flash` (scored OFF)
  - curator-on  — `s5-con-20260615`  — route `archolith/deepseek-v4-flash` (scored ON, after Restart B)

## Turn log
(turn -> prompt sent -> per-arm result)

| turn | prompt summary | passthrough | curator-off | curator-on |
|------|----------------|-------------|-------------|------------|

## Recall audit (turns 4-7 comparison pages) — RESTART A COMPLETE
Audited against the ACTUAL generated `.html` files (grep), not agent self-reports. Note: the seed
puts the accent INSIDE `.row-meta` (`.list-row .row-meta{color:var(--accent)}`), so reusing the class
inherits the accent — `var(--accent)`=0 in a page is correct recall (relied on the class), not a miss.

| page (turn) | anchor | passthrough | curator-off |
|-------------|--------|-------------|-------------|
| sealed (4) | list-row / row-meta / helper | 2 / 2 / `sealedList` ✓ | 2 / 2 / `sealedList` ✓ |
| graded (5) | list-row / row-meta / helper | 2 / 2 / `graded` ✓ | 2 / 2 / `graded` ✓ |
| series (6) | list-row / row-meta / helper | 2 / 2 / `series` ✓ | 2 / 2 / `series` ✓ |
| transactions (7) | list-row / row-meta / helper | 2 / 2 / `transactions` ✓ | 2 / 2 / `transactions` ✓ |

**Restart A finding: curator-off recall == passthrough recall == PERFECT (4/4 pages, all anchors).**
The unscored curator (two_curator + deterministic assembler) preserves recall exactly as well as raw
passthrough — it does NOT trade recall for compression on this task. The worry "the curator distills
and loses exact class names" is refuted here.

**Engagement:** curator fired on 5 user turns (`curator_calls=5`, `deterministic_assemblies=5`,
`hot_path_llm_calls=0` — every hot-path read was the LLM-free deterministic assembler from a cached
briefing; `prepper_fires=8`, `briefing_reads=5`).

**Helper cost (curator-off arm):** curator_prompt=82,172 (cached 54,656 = 66%), curator_completion=6,237,
extractor_prompt=26,173, embed=584. ~$0.04 at gpt-4.1-mini rates. passthrough arm = ~0 helper.

**IMPLICATION for the curator-on arm (Phase 4 scored selection):** curator-off is already at the recall
CEILING (perfect). With only ~8 small files (4 seed + generated), the prepper briefing fits everything
inside `ASSEMBLER_TOKEN_BUDGET`, so scored-vs-FIFO ordering does not change WHICH files are included —
it only reorders a set that all fits. Therefore curator-on cannot IMPROVE recall on this task (no
headroom); it can only confirm no regression. To actually exercise scored selection we need a task
whose relevant-file set EXCEEDS the assembler budget, forcing eviction where ranking matters.

## Restart B — curator-on (scored selection ON) — COMPLETE
Same 7 turns led identically. Recall audit (actual files):

| page (turn) | list-row | row-meta | correct helper | recall |
|-------------|----------|----------|----------------|--------|
| sealed (4) | yes | yes | `sealedList` | PASS |
| graded (5) | yes | yes | `graded` | PASS |
| series (6) | yes | yes | `series` | PASS |
| transactions (7) | yes | yes | `transactions` | PASS |

**curator-on recall == PERFECT (4/4), same as curator-off and passthrough — NO REGRESSION.**
Pages were leaner (e.g. sealed 19 lines vs 27) — curator-on omitted the static placeholder example row
and kept only the dynamic `.list-row` template (lines 15-17 use the exact pattern + EV in `.row-meta`).
That is generation style, not a recall miss (a separate stochastic agent session).

**Engagement:** prepper_fires=2, briefing_reads=5, **deterministic_assemblies=1, hot_path_llm_calls=4**,
curator_calls=1. Helper: curator_prompt=11,147 (cached 5,248), completion=345, extractor=5,583, embed=186.

### CAVEAT (important — limits this arm's value)
Scored selection lives ONLY in the deterministic assembler (`build_deterministic_context`). On the
curator-on arm the deterministic path ran just ONCE (determ=1); the other 4 curated turns took the LLM
curator hot path (hot_llm=4) because the prepper fired fewer times after the restart (2 vs 8 on
curator-off) — briefings weren't always fresh, so the hot path fell back to the LLM curator where
scoring does not apply. So scored selection was barely exercised. The cost gap (curator-off ~82k vs
curator-on ~11k curator_prompt) is therefore a **prepper-firing-count / restart-timing artifact, NOT a
scored-selection effect** — do not attribute it to Phase 4.

## VERDICT (against the pre-registered decision rule)
1. **Curator vs passthrough:** curator (both modes) recall == passthrough recall == PERFECT on all 4
   under-specified comparison pages. The curator compresses context **without losing recall** — the
   "distills and loses exact class names" hypothesis is REFUTED on this task. Curator earns its keep on
   recall (neutral-or-better), at ~$0.04 helper.
2. **Scored selection (curator-off -> curator-on):** NO REGRESSION (curator-on still perfect recall).
   But the delta is **uninformative** for "does it help": (a) curator-off was already at the recall
   ceiling (no headroom — ~8 small files all fit the assembler budget, so ranking changes nothing about
   what's included), and (b) scored selection was exercised only once on the curator-on arm anyway
   (determ=1). **Conclusion: scored selection is SAFE; whether it HELPS is still unmeasured.**
3. **Required follow-up to actually test Phase 4 scored selection:** a high-file-pressure task whose
   relevant-file set EXCEEDS `ASSEMBLER_TOKEN_BUDGET` (forcing the assembler to drop files, where
   ranking decides survivors), AND a config that keeps the hot path on the deterministic assembler
   (ensure briefings stay fresh so determ >> hot_llm) so scoring is actually exercised on every turn.

## Run cost summary (metered helper key)
Baseline 1,839,957. Restart A (curator-off) added ~108k input + ~6k output (~$0.04). Restart B
(curator-on) added ~17k input + ~0.3k output (~$0.007). passthrough arm ~0 helper. Read the dashboard
delta for ground truth.

---
_legacy header retained below_
| page | anchor | passthrough | curator-off | curator-on |
|------|--------|-------------|-------------|------------|

## Cost (dashboard delta from baseline 1,839,957)
| arm | upstream in/out | helper (curator+extractor+embed) | dashboard delta | priced |
|-----|-----------------|----------------------------------|-----------------|--------|

## Curator-engagement verification (per curator arm)
(proxy_status.py turns <ses> — confirm mode=curator rows, prepper_fires/briefing_reads climbing)

## Verdict (against the pre-registered decision rule)
(curator-off vs curator-on = does scored selection help; both vs passthrough = curator value)
