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
| corpus | A (name-varying) | B (fixed-name) | C (dir shape) |
|--------|------------------|----------------|---------------|
| yawn.frontend (feature-folder React) | **Page.tsx(15), Data.ts(15), Page.module.css(10)** | adapter.ts(3), types.ts(3) | **{Page.tsx, Data.ts, Page.module.css} x4**, +adapter/types x2 |
| opencode (TS domain-modules) | — none | **schema.ts(13), session.ts(10), event.ts(6), error.ts(6), config.ts(5)** | weak (only 2 dirs share a shape) |
| archolith_proxy (Python) | — none | **registry.py(3), models.py(3), base.py(2), schemas.py(2), router.py(2)** | none |

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

## Concrete recommendation
Extend the deterministic miner from 1 signal to a small ensemble:
- keep **A** (name-varying template) — best where it fires (React features);
- add **B** (fixed-name role recurrence, with the noise filter) — covers domain-module + backend corpora;
- add **C** (dir-shape) — the principled feature-as-role-set + names an exemplar instance;
- **rank/merge**: prefer C's shape when a dir template recurs; else A; else B's top role files; emit an
  empty profile (foundations-only) when nothing recurs.
Then the **LLM profiler** only handles the judgment/no-recurrence residue. Foundations (in-degree) stay
universal across all of this (the generalization result).

## Limits
- 3 corpora, one per type; a probe, not a survey. Signals A/B/C are filename/dir heuristics — content
  signatures (signal D, not tested) would catch convention encoded inside files, not names.
- "Exemplar derived" here is NOT recall-validated on opencode/Python (no frozen-briefing run there);
  the claim is "the convention is detectable," not "guaranteeing it improves recall on those corpora."

## Artifacts
- `rung3/explore_exemplar_signals.py` — the 3-signal probe.
