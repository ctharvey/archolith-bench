# Arm E (Recall Lab) rescore of the 78-item KU slice — 2026-08-08

## What this is

Rescored the most recent canonical 78-item knowledge-update LME slice
(`scalar-canonical-ku78-v1-20260806`) through Menhir's Recall Lab **arm E** tuning
(production base + frontier, soft evidence-anchor: `enable_facet_candidates=True`,
`facet_weight=0.5`, `enable_oracle_ranking=True`, `enable_intent_lens=True`,
`enable_warden_gate=True`, `enable_evidence_anchor=False`) instead of production defaults,
against the **same, already-ingested Neo4j graph** — no reingest, container
`menhir-lme-scalar-canonical-ku78-v1-20260806` restarted from its existing volume and
stopped again afterward.

## Prerequisite fix (menhir commit `4e8cf47`)

Recall Lab's `_serialize_result()` called `recall_service.recall()` directly and never
forwarded `authority_layer`/`event_authority_layer` or the per-memory
`is_superseded_view`/`is_scalar_authority` flags — unlike `/api/recall`, which does. The KU
scoring prompt depends entirely on that `[AUTHORITATIVE CURRENT MEMORY]` / `[SUPERSEDED ...]`
labeling, so running an arm through Recall Lab as-is would have confounded "arm E's tuning"
with "lost the authority formatting." Fixed by adding the three fields (+ redaction for their
free-text sub-fields) before running this rescore, so it's a fair comparison.

## Method

New script `scripts/longmemeval/analysis/run_arm_e_rescore.py`: a thin `HttpMenhirClient`
subclass (`RecallLabArmEClient`) that overrides only `recall()` to POST
`/explorer/api/recall-lab/run` with arm E's tuning instead of `/api/recall`, reusing the
canonical run's exact snippet-formatting helpers (`_recall_item_text`,
`_format_authority_record`) so the answer-model prompt is built identically. Driven through
the same `run_memory_ab` harness, `LongMemEvalMemoryAdapter`, fixture
(`fixtures/longmemeval/knowledge_update_subset.json`), namespace convention
(`lme-{question_id}`), and scorer (`LLMJudgeScorer`, gpt-4o answers / gpt-4o-mini judge) as
`run_knowledge_update_buildout.sh`'s Phase 2 — only the recall transport differs.

## Result — arm E does not beat production defaults on this slice

| Run | Tuning | N | Score | Cost (USD) |
|---|---|---|---|---|
| `scalar-canonical-ku78-v1-20260806` (canonical) | production defaults | 78 | **0.872 (68/78)** | $0.304659 |
| `scalar-canonical-ku78-v1-20260806-arm-e-rescore` (this run) | Recall Lab arm E | 78 | **0.808 (63/78)** | $0.207808 |

**Delta: −0.064 (≈5 fewer correct), arm E underperforms production defaults on this slice.**
Both runs' `no_memory` control landed close (canonical 0.077 / 6 vs this run 0.064 / 5 — a
~1-question spread consistent with gpt-4o-mini judge non-determinism, giving a rough sense of
the noise floor at N=78).

## Caveats

- Single run, no repeated seeds — the ~5-question gap is larger than the no_memory
  control's ~1-question judge-noise spread, so it's likely a real effect, but not
  statistically hardened.
- Facet candidates, oracle ranking, and the softened evidence-anchor gate are all changed
  together in arm E; this result does not isolate which sub-component (if any) drives the
  regression. Recall Lab's isolated arms F (facet-only) and G (oracle-only) would be the next
  step to decompose it.
- This is the knowledge-update slice specifically (scalar/authority-heavy); arm E's effect on
  other LME categories (temporal-reasoning, multi-session, etc.) is untested here.

## Artifacts

- `results/lme-ku-buildout/scalar-canonical-ku78-v1-20260806-arm-e-rescore/results.md`
- `results/lme-ku-buildout/scalar-canonical-ku78-v1-20260806-arm-e-rescore/results.json`
- `results/lme-ku-buildout/scalar-canonical-ku78-v1-20260806-arm-e-rescore/.checkpoint_longmemeval-menhir_s_gpt-4o.jsonl`
