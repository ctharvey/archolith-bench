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

## Decomposition (2026-08-08, same session) — D/F/G/H via `run_arm_rescore.py`

Follow-up: which sub-component of arm E's four changed flags (facet candidates, oracle
ranking + intent lens, warden gate, evidence-anchor hard/soft) drives the regression? Ran
the remaining Recall Lab arms against the same graph (`run_arm_rescore.py`, generalized
from the E-specific script; `no_memory` skipped since it's tuning-independent).

| Arm | Facet candidates | Oracle + intent lens | Warden gate | Evidence-anchor | Score |
|---|---|---|---|---|---|
| canonical (production) | off | off | off | — | **68/78 (0.872)** |
| F | **on** | off | off | on (moot — no warden) | 64/78 (0.821) |
| G | off | **on** | off | on (moot — no warden) | 64/78 (0.821) |
| H | on | on | **off** | soft | 64/78 (0.821) |
| D | on | on | **on** | hard | 63/78 (0.808) |
| E | on | on | **on** | soft | 63/78 (0.808) |

**Findings:**
1. **Facet candidates alone costs ~4 questions** (68→64) — F matches G exactly, though
   without a per-item diff it's not established whether they're the *same* 4 questions.
2. **Oracle ranking + intent lens alone also costs ~4 questions** (68→64) — same magnitude
   as facet candidates, independently.
3. **Combining facet + oracle + intent does not compound the loss** — H (both on, warden
   off) still lands at exactly 64/78, the same floor as either alone.
4. **Warden gate adds one further question of loss on top** (64→63, H vs D/E) —
   and it does so **identically whether evidence-anchor is hard or soft** (D and E are
   byte-for-byte the same score: 63/78, $0.218 vs $0.208, a few tokens apart from ordinary
   LLM variance, not from the flag).
5. **Evidence-anchor's hard/soft setting — the change this session originally set out to
   test as "arm E" — measurably does nothing here.** The softening hypothesis is falsified
   for this slice: D=E exactly. Whatever warden_gate costs, it isn't mediated by evidence
   anchor strictness on this fixture.

The regression is baked into facet_candidates and oracle_ranking/intent_lens individually
(not their combination, and not evidence-anchor mode) — that's where a fix would need to
target, not the evidence-anchor gate.

## Caveats

- Single run per arm, no repeated seeds — the score deltas (4-5 questions) are larger than
  the no_memory control's ~1-question judge-noise spread, so likely real, but not
  statistically hardened.
- No per-item diff was taken between F and G's failures, so "same floor" is observed at the
  aggregate level only — it's not established whether facet candidates and oracle ranking
  fail on the *same* subset of questions or different ones that happen to sum to the same count.
- This is the knowledge-update slice specifically (scalar/authority-heavy); these arms'
  effect on other LME categories (temporal-reasoning, multi-session, etc.) is untested here.

## Artifacts

- `results/lme-ku-buildout/scalar-canonical-ku78-v1-20260806-arm-e-rescore/{results.md,results.json,.checkpoint_*}`
- `results/lme-ku-buildout/scalar-canonical-ku78-v1-20260806-arm-{d,f,g,h}-rescore/{results.md,results.json,.checkpoint_*}`
- `scripts/longmemeval/analysis/run_arm_rescore.py` (generalized D/E/F/G/H runner)
