# R1 dummy gold run — 2026-06-29

## What this is

First R1 ladder run against the **dummy** (full prod-clone Neo4j, bolt 7687, ~23.8k real
Entity nodes) using a **mined gold answer set** instead of a seeded toy corpus. The point was
to break the recall=1.0 saturation that blocks graduation on `fixtures/r1_demo.json`.

- gold miner: `scripts/mine_r1_gold.py` -> `fixtures/r1_dummy_gold.json` (95 queries / 120 mems)
- read-mode runner: `scripts/run_r1_dummy.py` (recall only, never seeds, hard-pinned to 7687)
- artifact: `results/r1_dummy_run.json`

## Result — DOES NOT GRADUATE (and why that's informative)

```
condition         recall@5  exact_str  symbol  stale  wrong_scope  latency_ms
A_current            0.337      1.000    0.050  0.000        0.000     810
E_hybrid_a0          0.337      1.000    0.050  0.000        0.000     277
E_hybrid_a0.25       0.326      1.000    0.025  0.000        0.000     695
E_hybrid_a0.5        0.284      0.900    0.000  0.000        0.000     685
E_hybrid_a0.75       0.000      0.000    0.000  0.000        0.000     655
E_hybrid_a1          0.000      0.000    0.000  0.000        0.000     549
```

Per-family recall@5 (baseline): exact_error_string **1.00**, symbol_name_query **0.05**,
wrong_repo_same_topic **0.00**.

### Two distinct failure modes, both diagnosed

1. **exact_error_string saturates the BASELINE at 1.0.** The query is the verbatim identifier
   (e.g. `test_lifecycle_actions_reference_existing_nodes`) and today's fused recall already
   nails it — because graphiti's underlying `search_scored` RRF already fuses BM25 + cosine
   (the `node_reranker_scores` finding in `deferred-verification.md`). The win gate requires
   "E beats A on exact_string_recall", which is **impossible when A is already 1.0**. So R1's
   `enable_bm25` attributed-hybrid layer is largely **redundant with graphiti's internal RRF**
   on verbatim-lexical queries — a real architectural finding, not a tuning gap.

2. **symbol_name_query / wrong_repo collapse to ~0 because the mined query text was
   de-CamelCased** (`PricingModel` -> "Pricing Model"). That paraphrase removed the lexical
   signal AND the gold node never even entered top-50 (`in50=False`) in a 23.8k-node graph —
   the semantic match alone can't isolate one structural node. This is a **fixture-design
   artifact**, not a retrieval truth.

### The deeper conclusion

Auto-mining gold from structural metadata yields families that are either (a) trivially
lexical — baseline saturates, no headroom — or (b) if you paraphrase to add difficulty, the
single gold node is lost in the corpus. **R1's actual headroom lives in the semantic-gap
families** (`paraphrased_debug_question`, `buried_relevant_memory`): a query that is
semantically close but lexically distant from a KNOWN-gold node, where the source-aware floor
keeps a rank-floored-but-relevant candidate alive. Those can't be purely structure-mined —
they need either an LLM judge (the `_eval_frontier.py` nDCG path, already runs on the dummy)
or LLM-paraphrased queries over the mined gold uuids (auto-gold + semantic gap).

## Honest scope / caveats

- `stale_hit_rate` = 0 everywhere: the clone's `conflict_status` has no superseded/historical
  marker, so no stale family was mined. The gate's "no stale regression" check is trivially
  satisfied — documented, not earned.
- alpha endpoints behave as expected: alpha=0 (BM25-weighted) tracks baseline; alpha>=0.75
  (vector-weighted) collapses recall to 0 on these identifier queries — confirms the families
  are lexical, not semantic.
- One judge / structural gold; directional, not a promotion decision.

## Update — paraphrase family added (2026-06-29, run 2)

Added `paraphrased_debug_question` to `mine_r1_gold.py` (`--paraphrase N`): gpt-4.1-nano
rewrites each gold node's own `summary` into a natural question that shares NO identifier
words with the node (rejected if the model leaks the name). gold = the node uuid;
`target_symbol` = its name (so a semantic-gap rescue moves `symbol_recall`, which has
headroom). 40 such queries; fixture now 135 queries / 159 memories.

Example: gold `_anchor_to_structural_entities` <- query "How can I find the function that
converts anchors to structural entities?" (zero lexical overlap, semantically exact).

### Result — a real, narrow R1 win on the headroom family

```
condition        recall@5  exact  symbol  stale  scope   | paraphrase recall@5
A_current           0.400  1.000   0.300  0.000  0.000   | 0.550
E_hybrid_a0         0.415  1.000   0.325  0.000  0.000   | 0.600   <- best
E_hybrid_a0.25      0.319  1.000   0.163  0.000  0.000   | ...
E_hybrid_a0.5       0.230  0.900   0.050  ...
E_hybrid_a0.75      0.015  0.000   0.025
E_hybrid_a1         0.015  0.000   0.025
```

**E_hybrid_a0 (alpha=0, source-aware floor ON) beats A_current on the metrics that have
headroom, with zero regression:**
- paraphrased_debug_question recall@5: **0.550 -> 0.600 (+0.050)** — R1's thesis confirmed:
  the source-aware floor rescues buried-but-relevant candidates on lexically-distant queries.
- symbol_recall: 0.300 -> 0.325 (+0.025); overall recall@5: 0.400 -> 0.415 (+0.015).
- stale_hit_rate / wrong_scope_injection_rate: 0.000 both, no regression.

### Why the hardcoded gate still says "does not graduate"

`evaluate_win_gate` requires E to STRICTLY beat A on `exact_string_recall` — but exact is
saturated at 1.000 (baseline already perfect via graphiti's internal RRF), so `1.0 > 1.0`
is false and the gate can never fire on this corpus. **That is a gate-calibration artifact,
not an R1 failure.** The gate was written assuming the exact family has headroom (true on
the seeded demo, false on the real clone).

### Honest verdict (do NOT auto-set hybrid_alpha from this)

- The win is **real but narrow**: only the `a0` config beats baseline; `a>=0.25` regresses;
  +0.015 overall recall@5; single-judge / structural-gold; 40 paraphrase queries.
- The dominant lever is the **source-aware floor** (shared by all E configs), not the alpha
  value; `a0` is merely the best of the swept fusion weights, and vector-heavy (`a>=0.75`)
  collapses on these queries.
- `symbol_name_query` (0.05) and `wrong_repo_same_topic` (0.0) are still broken by the
  de-CamelCased query text — redesign needed (raw identifier saturates like exact; paraphrase
  is the better vehicle, already proven).

So R1 has, for the first time, a graduating-direction signal on a non-saturating real corpus —
but it is not yet a confident "ship hybrid_alpha=0" decision. To make it one:
1. recalibrate the gate to ignore saturated metrics (compare only metrics with baseline < 1.0),
2. scale the paraphrase family to ~150-200 queries for a stable estimate,
3. fix/replace the symbol_name + scope families,
then re-run and, only if the source-aware-floor win holds, set `hybrid_alpha` to the best
surviving config in `src/menhir/domain/retrieval_tuning.py`.
