# Rung 3 — Exemplar-Signal Exploration: what it takes to determine exemplars per corpus type

**Date:** 2026-06-16
**Type:** Offline probe (no LLM). The production miner uses ONE signal (recurring PascalCase
trailing-word+ext) and finds nothing outside feature-folder React apps. This tries THREE candidate
signals on 3 corpus types to learn what would surface exemplars generally. Reproduce:
`python rung3/explore_exemplar_signals.py <src-root>`.

## Signals
- **A — name-varying template:** recurring `<PascalWord><ext>` suffix across sibling dirs (current miner).
- **B — fixed-name convention:** recurring EXACT basename across dirs, boilerplate filtered
  (`__init__.py`, `index.ts`, `mod.ts`, ...).
- **C — recurring DIR SHAPE:** directories sharing the same SET of file-roles — the "template"
  generalized from one file to a co-located ROLE SET.

## Result (the convention lives in a DIFFERENT signal per corpus type)
Signal A is reported as **#dirs / #files** (both matter — see Java).
| corpus | A (name-varying suffix) | B (fixed-name) | C (dir shape) |
|--------|--------------------------|----------------|---------------|
| yawn.frontend (feature-folder React) | **Page.tsx 15d/15f, Data.ts 15d/24f, Page.module.css 10d** | adapter.ts(3), types.ts(3) | **{Page.tsx, Data.ts, Page.module.css} x4**, +adapter/types x2 |
| yawn.rip (Java / Spring layers) | **Service 2d/31f, Repository 4d/27f, DTO 3d/22f, Request 1d/12f, Controller 1d/10f** | — none | — none |
| opencode (TS domain-modules) | — none | **schema.ts(13), session.ts(10), event.ts(6), error.ts(6), config.ts(5)** | weak (only 2 dirs share a shape) |
| archolith_proxy (Python) | — none | **registry.py(3), models.py(3), base.py(2), schemas.py(2), router.py(2)** | none |

### Java/Spring is a 4th type: role-suffix by FILE count, cross-cutting features
- Java's convention IS the layer-role suffix (`Service`/`Repository`/`Controller`/`DTO`/`Request`) —
  Signal A fires, but **must be ranked by FILE count, not dir count**: `Controller` is `1d/10f` (all
  controllers live in ONE `controller/` package), so dir-count buries it while file-count surfaces it.
  Feature-folder corpora want dir-count; layer-package corpora want file-count. A general miner needs
  BOTH and must recognize which organization it is looking at.
- **A feature in Java is CROSS-CUTTING**, the inverse of feature-folders: a "Card" feature =
  `CardController` + `CardService` + `CardRepository` + `CardDto` spread across 4 layer packages. So
  neither Signal C (dir-shape — layers don't replicate a multi-role dir) nor B (names are name-varying)
  fires; the "feature template" would need a NEW signal: group files by STEM PREFIX (the entity name)
  and find stems that appear with multiple role-suffixes across layers (signal E, not built).
- The **DTO/Dto split (22f + 12f)** is a real naming inconsistency the corpus carries; the acronym-safe
  tokenizer surfaced it honestly (previously mis-parsed as `O.java`). Acronym-safe tokenization
  (`CardDTO -> ["Card","DTO"]`) is required for any acronym-heavy language.

## Findings — what it would take
1. **No single signal suffices; the corpus TYPE dictates which signal carries the convention.**
   - Feature-folder apps (yawn): A and C both fire strongly — the most rigidly templated.
   - Domain-module / Python codebases (opencode, archolith): only B fires — their "exemplar" is a
     recurring ROLE FILE (`schema.ts`, `base.py`, `models.py`), NOT a name-varying template.
2. **Signal B (exact-basename recurrence) is the broad generalizer the current miner lacks.** It found
   real conventions on BOTH corpora where signal A found nothing. Adding B would let the miner derive
   `schema.ts` for opencode and `base.py`/`models.py`/`registry.py` for Python — cheap, deterministic.
3. **Signal C (dir-shape) is the most PRINCIPLED notion of "exemplar"** — a feature as a co-located
   ROLE SET ({Page.tsx + Data hook + module.css}). It nails the yawn feature template and also names a
   concrete exemplar INSTANCE (a dir matching the modal shape). But it only fires where dir composition
   is rigid (yawn); opencode/Python domains are too heterogeneous.
4. **Noise filtering is mandatory.** `__init__.py` (15) and `index.ts` (24) are the MOST frequent
   basenames but are framework boilerplate, not templates-to-imitate. Without filtering they dominate B
   as false conventions. The line between "convention boilerplate" and "template to imitate" is a
   judgment call.
5. **The residue that needs an LLM (phase 3):** (a) distinguishing a real role-template from boilerplate
   when frequency alone is ambiguous; (b) corpora with NO surface recurrence at all (a one-off app);
   (c) content-level conventions not visible in filenames (e.g. "files that define a Zod schema + a
   namespace export"). Deterministic A+B+C+noise-filter cover MOST corpora; the LLM is the fallback for
   judgment and no-recurrence cases — sharpening the design note's phase-3 scope.

## Signal E (built + validated): stem-family generalizes dir-shape
Signal E groups files by name-STEM and finds entities carrying >=2 roles from the derived role
vocabulary (the top Signal-A suffix words); the role set is the feature template, the fullest entity
is the canonical exemplar. Restricting to the role vocabulary drops coincidental stem-sharing
(`Delta`/`Api`/`App`).
- **Java (yawn.rip):** 22 features; `Card -> {Controller, Dto, Repository, Service}` (the canonical
  Spring vertical slice), `Set -> {Controller, Dto, Service}`, `VsCardList -> {Controller, Repository,
  Service}`.
- **React (yawn.frontend):** ALSO fires — `CardIndex -> {Data, Page}` (i.e. `CardIndexPage.tsx` +
  `useCardIndexData.ts` share stem `CardIndex`), `MarketReport -> {Data, Island, Page}`.

**Unification:** a feature template is a recurring ROLE SET, bound by some key. Signal C uses the
DIRECTORY as the key (feature-folders); Signal E uses the name-STEM. **E generalizes C** — it catches
React (stem `CardIndex`) AND Java (stem `Card`), where C only catches feature-folders. The general
deterministic recipe is: **A (derive role vocabulary by file+dir count, acronym-safe) -> E (group by
stem, role set = template, fullest = exemplar) -> B (fixed-name fallback for domain-module corpora) ->
in-degree foundations (universal).**

## Concrete recommendation
Extend the deterministic miner from 1 signal to a small ensemble, with two metric/parse refinements the
Java corpus forced out:
- keep **A** (name-varying suffix) — but report BOTH **#dirs and #files** and use an **acronym-safe
  tokenizer** (`CardDTO -> ["Card","DTO"]`). #dirs surfaces feature-folder corpora; #files surfaces
  layer-package corpora (Java/Spring `Controller` = 1 dir / 10 files).
- add **B** (fixed-name role recurrence, noise-filtered) — covers domain-module + backend corpora.
- add **C** (dir-shape) — the principled feature-as-role-set; names an exemplar instance.
- (later) **E** cross-layer stem-family — group files by entity stem across layer packages; the Java
  "feature" (`Card*` across controller/service/repository/dto). Not built.
- **organization detection + rank/merge**: decide feature-folder vs layer-package vs domain-module
  (e.g. dir-count-dominant vs file-count-dominant vs fixed-name-dominant) and pick the matching signal;
  prefer C's shape when a dir template recurs; else A (by the right count); else B; else empty profile
  (foundations-only).
Then the **LLM profiler** only handles the judgment/no-recurrence residue (template-vs-boilerplate,
content-level conventions, one-off corpora). Foundations (in-degree) stay universal across all of this.

## Limits
- 3 corpora, one per type; a probe, not a survey. Signals A/B/C are filename/dir heuristics — content
  signatures (signal D, not tested) would catch convention encoded inside files, not names.
- "Exemplar derived" here is NOT recall-validated on opencode/Python (no frozen-briefing run there);
  the claim is "the convention is detectable," not "guaranteeing it improves recall on those corpora."

## Artifacts
- `rung3/explore_exemplar_signals.py` — the 3-signal probe.
