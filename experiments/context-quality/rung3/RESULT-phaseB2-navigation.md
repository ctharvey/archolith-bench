# Rung 3 — B2: Does a Code Map Improve NAVIGATION? (RESULT)

**Date:** 2026-06-16
**Type:** Controlled agentic navigation (re-reading ALLOWED, every fetch observed). The genuine MAP
test B1 couldn't do (B1 was frozen-briefing = nothing to navigate to). Instead of a live proxy/harness
with opaque re-reads, the model gets a `read_file` tool over the corpus and we COUNT the reads. 3 arms
× 2 tasks × 3 seeds = 18 runs (each a multi-call tool loop, MAX_TURNS=8). No 429s. Reproduce:
`python rung3/phase_b2_navigation.py`.

## Arms
- **map** — the `=== CODE MAP ===` (Thread-1 renderer) in the prompt + `read_file`.
- **ls** — no map, `read_file` + `list_dir` (the FAIR baseline: a real agent has directory discovery).
- **blind** — no map, `read_file` only (the floor: no structural information at all).

## Result (mean over n=6 per arm)
| arm | reads | list_dir calls | misses | **exemplar found %** | reads→exemplar |
|-----|-------|----------------|--------|----------------------|----------------|
| map | 25.7 | 0 | 0.3 | **17%** | 10.8 (rough) |
| ls | 10.5 | 11.5 | 0.2 | **100%** | 3.2 |
| blind | 0.0 | 0 | 8.0 | **0%** | — |

What the **map arm actually read** (sample): `domain/models/index.ts, models/Common.ts, models/Card.ts,
models/Market.ts, models/Transaction.ts, models/Set.ts, models/Sealed.ts, formatters.ts` — **all
foundations, zero page exemplars.**

## Findings — the in-degree map helps the WRONG navigation, and it's the same old finding
1. **blind is lost** (0 reads, 8 misses every run): without ANY structural info the agent gropes at a
   275-file repo and never finds a real file. Confirms structure matters — but "no structure" is not
   the realistic baseline.
2. **The map eliminates groping** (0.3 misses vs 8): it hands the agent valid paths, so it stops
   guessing nonexistent files. Real, but a low bar.
3. **The map steers the agent to FOUNDATIONS and away from the EXEMPLAR.** map-arm exemplar-found =
   **17%** (it almost never reads a `*Page.tsx`), and it reads a LOT (25.7 files) — it dutifully walks
   the foundations the map surfaces. Because the map is built from **in-degree**, it advertises
   foundations, so the agent reads foundations. This is **"foundation ≠ recall-critical" again — now on
   the navigation axis.** The in-degree map is an answer to the wrong question.
4. **Plain `ls` WINS at the thing that matters** — exemplar-found **100%**, in ~3.2 reads, with fewer
   total reads (10.5) — by browsing to `features/` and reading an actual page. Cost: ~11.5 `list_dir`
   round-trips (cheap discovery calls). Directory structure is a *better navigation aid than an
   in-degree map* because feature folders are discoverable by name and lead straight to the template.

## Verdict
The genuine navigation test does NOT vindicate the in-degree code map. It beats a blindfolded agent
(no realistic), but **loses to plain `ls`** on the load-bearing metric (reaching the exemplar), and it
actively biases the agent toward foundations — the same misdirection Phase C found for recall. So:
- **Do not ship `assembler_code_map` as-is.** An in-degree/foundation map is recall-neutral (B1) AND
  navigation-misdirecting (B2). Its only win is over "no tools," which agents don't face.
- **The design implication loops back to the exemplar work:** a map that *helps* navigation would need
  to surface **structure/exemplars** (directory shape, the `Page.tsx` template — Signals C/E from the
  exemplar-signal exploration), not dependency in-degree. "Show the agent where the template is," not
  "show it the most-depended-upon files." Or simpler: **just give the agent `list_dir`** — cheap
  discovery beat the precomputed in-degree map outright here.

## Honest limits
- One corpus, 2 tasks, 3 seeds (n=6/arm). `reads→exemplar` is a rough metric (defaults to MAX_TURNS
  when never found while reads can exceed it); **exemplar-found %** is the clean headline.
- The map tested is specifically the **in-degree** map (`render_code_map`). A *structure/exemplar* map
  is untested — B2 motivates building one, it doesn't condemn all maps.
- `ls`'s 11.5 discovery calls are real latency the map saves; if discovery were expensive (huge repo,
  rate limits) the trade could shift. Here, on a 275-file repo, cheap `ls` won clearly.
- Controlled loop (my `read_file`/`list_dir` over the corpus), not a production agent harness — the
  Phase-C-style trade: precision + observability over fidelity.

## Artifacts
- `rung3/phase_b2_navigation.py` — the 3-arm navigation harness.
- `rung3/phaseB2-output/` — (none; this harness scores reads, not generated files).
