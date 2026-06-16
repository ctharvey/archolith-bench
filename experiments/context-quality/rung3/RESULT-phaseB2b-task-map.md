# Rung 3 — B2b: Task-Ranked Map Fixes the Navigation Misdirection (RESULT)

**Date:** 2026-06-16
**Type:** Iteration on B2 (`RESULT-phaseB2-navigation.md`). Same controlled navigation harness, +1 arm.
B2 found the in-degree map steers the agent to FOUNDATIONS, away from the exemplar. The iteration
(owner's idea): rank the map by **relevance to the current task** instead of in-degree — "show what's
needed for THIS task," not "what's most depended-upon." 4 arms × 2 tasks × 3 seeds. No 429s (added a
transient-error retry; a 429 still STOPs). Reproduce: `python rung3/phase_b2_navigation.py`.

## The new arm
`render_task_map(files, query, exemplar_suffixes=("Page.tsx",))` — ranks files by scored relevance to
the task, tags `[exemplar]`, lists a short "START HERE (most relevant)" block + a "Shared foundations"
line for orientation. **Ranks/annotates, does not filter** (foundations still shown; the agent can read
anything). For "Decks browse screen" it renders:
```
START HERE (most relevant to this task):
  features/sealed/SealedPage.tsx [exemplar]
  features/graded-v3/GradedV3Page.tsx [exemplar]
  ...
Shared foundations: data/apiClient.ts, domain/models/index.ts, ui/index.ts, ...
```

## Result (mean, n=6 per arm)
| arm | reads | list_dir | misses | **exemplar found %** | **reads→exemplar** |
|-----|-------|----------|--------|----------------------|--------------------|
| map (in-degree) | 24.3 | 0 | 0.8 | 17% | 8.5 |
| **map-task (relevance)** | 16.7 | 0 | 6.3 | **100%** | **1.0** |
| ls (read+list_dir) | 10.2 | 10.8 | 0.3 | 100% | 4.0 |
| blind | 0.0 | 0 | 8.0 | 0% | 8.0 |

map-task's first read is the exemplar every run (reads→exemplar = 1.0); sample: `SealedPage.tsx,
GradedV3Page.tsx, ...` read first.

## Findings — the iteration works, and beats `ls` on the metric that matters
1. **Task-ranking FIXES the in-degree map's core failure.** exemplar-found 17% → **100%**; the agent
   reads the template FIRST (reads→exemplar 8.5 → **1.0**) because the map says "START HERE:
   SealedPage.tsx [exemplar]". This directly confirms the owner's hypothesis: a map is useful when it
   ranks **task priority**, not dependency in-degree.
2. **map-task beats `ls` on the load-bearing axis at ZERO discovery cost.** It reaches the exemplar in
   ~1 read vs `ls`'s ~4, and with **0 `list_dir` round-trips** vs `ls`'s ~11. A task-ranked map is the
   always-present, zero-round-trip form of "browse to find the template."
3. **New tradeoff (honest): map-task's misses rose to 6.3** (vs `ls` 0.3). After reading the priority
   list, the agent gropes for SECONDARY files (components, siblings) the ranked map doesn't enumerate —
   it's a "start here" pointer, not a complete directory listing. So it nails the exemplar but wastes
   some calls on non-listed files.
4. **The in-degree map remains the worst useful arm** (17% exemplar, 24.3 reads of mostly foundations)
   — superseded by map-task.

## B2c — the synthesis: task-map + `list_dir` (the "untested ideal", now tested)
Added a 5th arm combining the priority map with directory discovery. Result (n=6/arm):
| arm | reads | list_dir | misses | exemplar % | reads→exemplar |
|-----|-------|----------|--------|-----------|----------------|
| map (in-degree) | 23.2 | 0 | 0.8 | 0* | 8.0 |
| map-task | 16.7 | 0 | 4.8 | 100 | 1.0 |
| **map-task + ls** | 18.3 | **4.7** | **0.0** | **100** | **1.0** |
| ls | 10.2 | 11.2 | 0.3 | 100 | 4.0 |
| blind | 0.0 | 0 | 8.0 | 0 | 8.0 |
(*in-degree map's exemplar-reach is seed-fragile — 17% in B2b, 0% here; either way the worst useful arm.)

**The synthesis is the best arm on every quality axis at once:**
- **exemplar 100% in ~1 read** — the task-map's "START HERE" gives the sharp start (kills reads→exemplar).
- **0.0 misses** — `list_dir` supplies the complete discovery the ranked map lacked (kills the groping
  that gave bare map-task 4.8 misses).
- **~4.7 `list_dir` calls vs plain `ls`'s ~11.2** — the map means the agent browses LESS; it already
  knows where to start, so discovery is confirmatory, not exploratory. The map roughly halves the
  discovery round-trips.
So the priority map and directory discovery are complementary, not redundant: the map fixes
*reaches-the-exemplar* and *discovery cost*; `list_dir` fixes *completeness*. Recommended navigation
design = **task-ranked map + a `list_dir` tool.**

## Verdict & next
- **The owner's "rank by task priority" iteration is validated:** it turns the map from
  navigation-misdirecting (B2) into the FASTEST route to the exemplar — better than `ls` on
  exemplar-reach and free of discovery round-trips.
- **The clean synthesis (next, untested): task-map + `list_dir`.** Priority ranking for the sharp
  "start here" (kills reads→exemplar) PLUS directory discovery for completeness (kills the 6.3 misses).
  Best of both: sharp start, no groping.
- **Port candidate:** `render_task_map` is the map worth wiring into `assembler_code_map` (replacing /
  alongside the in-degree `render_code_map`), since it's the version that helps. Experiment-first
  pattern satisfied — it won; porting is the follow-on. `render_task_map` shipped in
  `archolith-context` with a unit test; not yet wired as the assembler's emit mode.

## Honest limits
- One corpus, 2 tasks, 3 seeds (n=6/arm). `reads→exemplar` defaults high when never found; **exemplar
  found %** is the clean headline (and it's a clean 100 vs 17).
- map-task's relevance ranking inherits scored's dependency on query↔exemplar vocabulary overlap (the
  Phase-C/D caveat) — it worked here because browse-page tasks share vocab with browse-page exemplars.
- Controlled loop, not a production harness; the residual-miss finding motivates the task-map+ls combo,
  which is untested.

## Artifacts
- `rung3/phase_b2_navigation.py` — now 4 arms (map / map-task / ls / blind), with transient-retry.
- `archolith-context` `render_task_map` + unit test.
