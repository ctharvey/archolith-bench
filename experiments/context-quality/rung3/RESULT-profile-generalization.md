# Rung 3 — Corpus Profiler Generalization (3 corpora)

**Date:** 2026-06-16
**Type:** Offline validation of `derive_corpus_profile` across 3 differently-structured corpora — the
generalization test flagged as a Phase-2 limit. No LLM. Reproduce: `python rung3/derive_profile.py <root>`.

## Corpora
| corpus | kind / structure | files |
|--------|------------------|------:|
| `forked/yawn.frontend/src` | Astro + React, **feature-folder** convention | 275 |
| `forked/opencode/packages/opencode/src` | TS CLI/agent, **domain-module** structure (session/, bus/, config/, util/) | 507 |
| `archolith-context/archolith_proxy` | **Python** modules (snake_case) | 135 |

## Result
| corpus | derived exemplar marker | foundations (top in-degree) |
|--------|--------------------------|------------------------------|
| yawn.frontend | **`Page.tsx`** (recurs 15 sibling dirs) | apiClient, models/index, ui/index, slug, repository, Layout |
| opencode | **`[]`** (no recurring template) | util/filesystem, util/schema, bus/global, config/config |
| archolith_proxy (py) | **`[]`** (snake_case, no template) | config.py, extractor/base, memory/models, graph/backend, metrics |

## Findings
1. **The exemplar miner fires ONLY where a repeated-template convention actually exists.** yawn.frontend
   repeats `Page.tsx` across ~15 feature dirs -> derived. opencode is organized by one-off domain
   modules (no repeated template) -> correctly **`[]`**. Python is snake_case modules (no PascalCase
   template-by-filename) -> correctly **`[]`**. **No false markers** on either non-template corpus —
   the honest-degradation property holds: it returns nothing rather than inventing a template.
2. **Foundations (in-degree) generalize UNIVERSALLY.** Meaningful, correct foundations were derived for
   all three — across language (TS, Python) and structure (feature-folder, domain-module). In-degree is
   the structure-agnostic half; the exemplar marker is the structure-specific half.
3. **Implication for the combo.** The exemplar GUARANTEE (the thing that won Phase D recall) only
   engages on template-convention corpora. Elsewhere the combo degrades to scored x topological (≈
   scored) — safe and honest, no false exemplar. So the combo's recall win is SPECIFIC to corpora that
   imitate a repeated template; "convention recall" is a different (or absent) problem on domain-module
   / library corpora.

## What this means for the design
- The deterministic miner is validated as PRIMARY for template-convention corpora and as a clean no-op
  (foundations-only) elsewhere — exactly the boundary the design note predicted.
- The **LLM profiler (phase 3)** is where a NON-surface exemplar/convention notion would have to come
  from, for corpora whose conventions are not filename-recurring (or it correctly concludes there is no
  single template to guarantee).
- Foundations being universal supports the **shared code-graph substrate (design Option B)**: in-degree
  is the language-agnostic primitive both memory and the curator want.

## Limits
- 3 corpora, one of each kind; not a survey. The qualitative boundary (fires on repeated-template
  corpora, no-ops cleanly elsewhere, foundations universal) is the robust takeaway.
- The miner's component-pattern regex is PascalCase-oriented (JS/TS/component idiom); a corpus with a
  repeated snake_case template (e.g. Django `views.py` per app) would currently be missed — a known
  extension if such corpora matter.

## Artifacts
- `rung3/derive_profile.py` (now language-general after adding .py/.kt/.java/.go/.rs to the loader).
