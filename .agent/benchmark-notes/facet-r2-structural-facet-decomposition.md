# R2 facet — structural-facet extraction decomposed (2026-07-05)

_Chunk F owed piece: replace hybrid mode's **gold structural-facet stand-in** with **real
derived** structural facets, and see if F still graduates. Companion to
`facet-r2-real-embedder-run.md`. Fixture: `fixtures/facet_r2_draft.json` (50/20)._

## Question

Hybrid mode graduates F by reading `file/symbol/test/repo/project/namespace` from the **gold**
record — a stand-in for "the code graph + Git know these exactly." The pure-`extracted` mode
(regex over prose) collapses (F recall 0.275). So the owed question: **can a cheap deterministic
extractor recover structural facets from real signals, or do they genuinely require the graph?**

## Diagnostic — per-facet extraction recall vs gold (draft fixture)

Measured `FacetExtractor.extract(text)` against each memory's gold structural facets:

```
facet       recall  prec   note
file          0.00   0.00   gold paths (src/menhir/services/recall_service.py) ARE NOT IN THE PROSE
symbol        0.11   0.50   only PascalCase + foo() calls caught; snake/SCREAMING_SNAKE missed
repo          0.71   0.97   vocab-matched (decent)
project       0.71   0.97   vocab-matched
namespace     0.15   0.47   vocab rarely appears literally in text
```

Two distinct failure modes — **not** one "extraction is hard" blob:

- **`file` recall 0.00 — the wall.** The gold file paths are metadata the author *knew* but never
  wrote into the memory text. A regex cannot recover a token that is not there. In production these
  come from the graph's `ANCHORED_TO` edges (structure_project / structure_path), never from text.
- **`symbol` recall 0.11 — under-extraction, fixable.** The symbols *are* in the prose
  (`source_aware_floor`, `weighted_rrf`, `FLOOR_EXEMPT_SOURCES`) but the rules only matched
  PascalCase + `foo(` calls, missing snake_case and SCREAMING_SNAKE bare mentions.

## Fix + measured lift (offline, no graph)

Added snake_case + SCREAMING_SNAKE identifier rules to the deterministic extractor
(`archolith_bench/facet/extractor.py`). Result:

- **symbol extraction recall 0.11 -> 0.55** (prec 0.50 -> 0.48; 60 facet tests green).
- **extracted-mode F recall@5 0.275 -> 0.425** (+0.15) — a real gain from cheap deterministic rules.
- extracted-mode D (file-context stand-in) also rose 0.100 -> 0.425 (better symbols help it too).

But **extracted mode still does NOT graduate** (recall_loss 0.425; wrong_scope regresses), because
**file facets remain absent (0.00)** and the meet-point reranker's scope/support discipline leans on
structural facets it cannot get from prose. Hybrid mode (gold/graph structural) is unchanged and
still graduates (F 0.825, wrong_scope 0.07).

## Conclusion — the structural bottleneck is FILE facets, and they need the graph

| structural facet | source | cheap to derive offline? |
|---|---|---|
| symbol | prose (+ graph) | **yes** — improved 0.11 -> 0.55; more is possible |
| repo / project | small vocab | mostly (0.71) |
| namespace | metadata | weak from text (0.15) |
| **file / test** | **code graph `ANCHORED_TO` only** | **no — not in prose (0.00)** |

So hybrid mode's gold-structural stand-in is the **correct model** for graph-anchored facts, and
"just extract structural facets from text" has a hard ceiling: **file facets require the code
graph's anchoring.** You cannot regex "which file" out of a memory that never named it.

## Owed (now sharpened, graph-gated)

The remaining Chunk F question is **not** "write a better extractor" — it is **production anchoring
coverage**: do real menhir memories reliably carry `ANCHORED_TO` edges to file/symbol nodes so the
structural facets are available (like gold)? Measure that on the live graph, then re-run hybrid mode
with **graph-derived** (not gold) structural facets. If anchoring coverage is high, hybrid's result
holds and `CandidateSource.FACET` is wireable; if it's sparse, facet retrieval only helps the
well-anchored slice. Fixture hardening (Risk #1) is still owed in parallel.

## Live production measurement — ANCHORED_TO coverage (2026-07-05)

Ran the graph-gated half against the **prod-clone dummy** (Neo4j 7687, 23.8k entities, read-only):
does production actually supply structural facets via the code graph, and for how many memories?

```
ANCHORED_TO edges                     11,706   (all memory -> structural, confirmed)
  distinct source memories             1,300
  distinct structural targets            612   (all have structure_path; symbol_kind = 0)
memory nodes (non-structural)          5,314
  anchored (>=1 ANCHORED_TO)           1,300   -> 24.5% coverage
  avg anchors when anchored              9.0   (max 215; 750 memories have >=3)
```

Findings:
- **ANCHORED_TO gives memories their FILE facets** — targets are file/path nodes (`structure_path`),
  not symbols. So the exact `file` facet the text extractor could never recover (recall 0.00) **is**
  available from the graph — via anchoring. Symbol facets are reachable one hop further
  (`file -[:DEFINES]-> symbol`) or from the improved text extraction.
- **But only 24.5% of memories are anchored.** The anchored quarter is richly anchored (avg 9 files,
  750 with >=3); the other **75.5% carry no structural anchors at all**.

### What this means for wiring `CandidateSource.FACET`

Hybrid mode's gold-structural stand-in is **realistic for the ~1/4 of memories that are
file-anchored** — those genuinely get exact `file` facets from the graph, so F's scope/support
discipline works on them. For the unanchored 75.5%, there are no structural facets to gate on and F
degrades to the extracted-mode behavior (which does not graduate). So **`CandidateSource.FACET` is a
bounded win: it helps the code-anchored slice, not the whole corpus.** The lever to grow that win is
**ingest-time anchoring coverage** (more memories getting `ANCHORED_TO` edges), not a better facet
engine or extractor — the engine already works where the anchors exist.

Owed next: decide whether to (a) wire FACET for the anchored slice now (bounded but real), and/or
(b) invest in raising anchoring coverage at ingest; plus ctharvey's fixture hardening (Risk #1).

_Artifacts (regenerable, not committed): `results/facet_r2_derived.json` (improved extraction).
Live query artifacts not persisted (read-only against the dummy 7687)._
