# R1 dummy gold harness — run R1 on the real graph, not a toy

## Status

active — tooling built + first runs done 2026-06-29. The R1 ladder finally runs on a
non-saturating corpus. NOT yet a `hybrid_alpha` ship decision (see "Path to graduation").

## Why this exists

R1 (hybrid candidate generation + source-aware floor) has been scaffolded three times but
never graduated: the only fixture (`fixtures/r1_demo.json`) is a tiny seeded corpus that
saturates at recall=1.0, so `evaluate_win_gate` can never fire and `hybrid_alpha` stays at
the untuned neutral `0.5`. The blocker was never the harness — it was the absence of a real,
labeled, non-saturating corpus.

This harness solves that by scoring against the **dummy**: a full bolt clone of the live
menhir graph (~23.8k real Entity nodes), with gold labels **mined from the graph itself** so
no hand-authoring is required for the bulk of the families.

## The two scripts

```text
scripts/mine_r1_gold.py     READ-ONLY graph mine -> fixtures/r1_dummy_gold.json
scripts/run_r1_dummy.py     READ-MODE recall over the dummy -> results/r1_dummy_run.json
```

Both are hard-pinned to the dummy (bolt 7687) and refuse to run elsewhere. `run_r1_dummy.py`
never seeds and never writes; `mine_r1_gold.py` only runs `MATCH ... RETURN` (plus, with
`--paraphrase`, N one-shot LLM calls to author questions). Prod is a different bolt host in
`menhir/.env` and is never contacted.

### How gold is derived (no seed-episode grounding)

Memory ids ARE node uuids, so recalled uuids map straight back to gold. Families:

| family | how gold is mined | drives |
|---|---|---|
| `symbol_name_query` | globally-unique class name | symbol_recall |
| `exact_error_string` | globally-unique underscore identifier (fn/method) | exact_string_recall |
| `wrong_repo_same_topic` | a symbol in EXACTLY two projects; query scoped to A, B is the distractor | wrong_scope_injection_rate |
| `paraphrased_debug_question` | LLM rewrites a node's own `summary` into a question with NO identifier overlap (rejected if it leaks the name); gold = that uuid, `target_symbol` = its name | symbol_recall on a real semantic gap |

`paraphrased_debug_question` is the load-bearing family: it is the only one with real
headroom (the structural families are either lexically trivial — baseline saturates — or lose
the single gold node once paraphrased). It is what actually exercises R1's source-aware floor.

NOT mined: stale/historical (the clone's `conflict_status` has no superseded marker) and
`buried_relevant_memory` (needs an LLM judge). Hand-authored gold can be dropped into the same
JSON — the runner scores it identically.

## How to run (end to end)

```bash
PY="C:/Users/thron/IdeaProjects/projects/archolith/menhir/.venv/Scripts/python.exe"

# 0. dummy up (clone of prod). If the container is stopped (Docker dies on session
#    boundaries — see the menhir-frontier session-handoff GOTCHA):
docker start menhir-neo4j-dummy          # bolt 7687, pwd menhirdummy123
#    or rebuild the clone from scratch:  python scripts/_clone_to_dummy.py  (in menhir-frontier)

# 1. mine the gold answer set (structural families + 40 LLM paraphrases)
$PY scripts/mine_r1_gold.py --paraphrase 40        # -> fixtures/r1_dummy_gold.json

# 2. run the ladder (A_current vs E_hybrid alpha sweep), score + win gate
$PY scripts/run_r1_dummy.py                         # -> results/r1_dummy_run.json
```

`mine_r1_gold.py` flags: `--symbols 40 --exact 30 --scope 25 --paraphrase 40 --out PATH`.
`run_r1_dummy.py` flags: `[fixture] --k 5 --candidate-k 50 --out PATH`.

## Current findings (run 2, 135 queries)

Full run log: [`.agent/benchmark-notes/r1-dummy-gold-run.md`](../benchmark-notes/r1-dummy-gold-run.md).

`E_hybrid_a0` (alpha=0, source-aware floor ON) beats `A_current` on the metrics with headroom,
zero regression:
- paraphrase recall@5 **0.550 -> 0.600 (+0.050)** — R1's thesis confirmed (the floor rescues
  buried-but-relevant candidates on lexically-distant queries).
- symbol_recall 0.300 -> 0.325; overall recall@5 0.400 -> 0.415; stale/scope 0.000, no regression.

Two real, separately-true findings:
1. **exact_error_string saturates the baseline at 1.0** — graphiti's internal RRF already fuses
   BM25+cosine, so R1's `enable_bm25` is largely redundant on verbatim-lexical queries. The
   win gate's "strictly beat exact_string_recall" clause can therefore never fire on this
   corpus — a gate-calibration artifact, not an R1 failure.
2. The R1 win is **real but narrow**: only `alpha=0` beats baseline (`alpha>=0.25` regresses);
   the dominant lever is the source-aware floor, not the alpha value.

## Path to graduation (next session — do NOT auto-ship hybrid_alpha)

1. **Recalibrate `evaluate_win_gate`** to ignore saturated metrics (compare only metrics where
   `baseline < 1.0`), so a genuine semantic-gap win isn't blocked by exact-string saturation.
2. **Scale paraphrase queries to ~150-200** for a stable estimate (40 is directional only).
3. **Fix the symbol_name + scope families** — the de-CamelCased query text breaks them (gold
   falls out of top-50); raw identifiers saturate like exact, so paraphrase is the better vehicle.
4. Re-run; **only if** the source-aware-floor win survives 1-3, set `hybrid_alpha` to the best
   surviving config in `menhir/src/menhir/domain/retrieval_tuning.py` and flip R1
   `in-progress -> done` in the execution ladder.

## Repo discipline

Research harnessing lives here (archolith-bench), never in menhir `src`. These scripts import
menhir as a library (frontier `src` first, for the R0 trace + hybrid path). `results/` is
gitignored; the fixture + run note are committed as the reproducible record.
