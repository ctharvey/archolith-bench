# Arm E (Recall Lab) rescore of the 78-item KU slice — 2026-08-08

> **SUPERSEDED (2026-08-08, later same day).** Everything below "Decomposition" was measured
> before a second missing-field bug was found and fixed (menhir `d0c6752`: `_serialize_result`
> also omitted each memory's `temporal_facts`, which the KU prompt's "previously vs now" /
> supersession reasoning depends on, dropped for every Recall Lab arm regardless of tuning).
> **See "CORRECTED results" below for the real, deconfounded numbers** -- the original
> decomposition table understated every arm's score and mischaracterized which tuning
> actually costs anything. Kept for the record, not as current guidance.

## CORRECTED results (2026-08-08, after menhir `d0c6752` — temporal_facts fix)

Reran D/E/F/G/H against the same graph (`LME_RUN_SUFFIX=-v2`, results in
`results/lme-ku-buildout/scalar-canonical-ku78-v1-20260806-arm-{arm}-rescore-v2/`), after
confirming live (not just via the unit tests) that the real Recall Lab endpoint now returns
`temporal_facts` for the exact case that was broken before (`c4ea545c`'s superseded gym
schedule fact).

| Arm | Facet candidates | Oracle + intent lens | Warden gate | Evidence-anchor | Score |
|---|---|---|---|---|---|
| canonical (production) | off | off | off | — | **68/78 (0.872)** |
| F | **on** | off | off | on (moot — no warden) | **68/78 (0.872)** — no cost |
| G | off | **on** | off | on (moot — no warden) | **65/78 (0.833)** — real −3 |
| H | on | on | **off** | soft | **68/78 (0.872)** — recovered |
| D | on | on | **on** | hard | 67/78 (0.859) |
| E | on | on | **on** | soft | 67/78 (0.859) |

**This is a materially different picture from the confounded run:**

1. **Facet candidates alone has zero measurable cost** (F = canonical exactly). The earlier
   64/78 was almost entirely the missing-`temporal_facts` artifact, not a real facet-ranking
   defect.
2. **Oracle ranking + intent lens alone has a real, non-artifact cost of 3 questions**
   (68→65, G). Regressed: `6071bd76`, `c4ea545c`, `e61a7584`.
3. **Adding facet candidates on top of oracle+intent (H) recovers 2 of those 3 questions**
   (`6071bd76`, `c4ea545c`) — facet candidates appear to compensate for something oracle
   ranking alone gets wrong, landing H back at 68/78, matching canonical. `e61a7584`
   ("How long have I had my cat, Luna?", gold "9 months") stays wrong in G, H, *and* D/E — a
   genuine oracle_ranking-caused failure that facet candidates cannot rescue.
4. **Warden gate still costs something on top of the recovered H baseline** — D and E both
   drop to 67/78 (one further question below H). Real, but far smaller than the confounded
   run suggested (that showed D/E at 63/78, a 5-question gap from canonical; the real gap is
   1 question from H, 2 from raw oracle-only G's floor).
5. **D=E still holds** (both 67/78) — the evidence-anchor hard/soft verification from earlier
   this session is unaffected by this fix; that finding was never confounded by the
   `temporal_facts` gap since it only affects whether Guard 5 is in the chain at all, not
   candidate content.

**Revised bottom line:** the KU-slice "regression" this session set out to explain was
mostly a measurement artifact (missing `temporal_facts`). Once corrected, the only genuine
per-arm cost left is oracle_ranking+intent_lens's 3-question hit — largely, but not
completely, offset when facet_candidates is also on — plus a small additional warden-gate
cost. Facet candidates and evidence-anchor mode are not the story.

## What this is (original run, now historical — see correction above)

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

## Verified this is not a misconfiguration (2026-08-08)

D=E was suspicious enough to check the wiring rather than assume the flag is a no-op bug.
Traced the full chain in `src/menhir` and confirmed live against the graph:

- `RecallLabTuning.enable_evidence_anchor` -> `RetrievalTuningConfig` -> `AssertionPipeline.
  __init__` (`services/assertion_pipeline.py:104-105`): `if evidence_anchor:
  default.append(EvidenceAnchorWarden())` -- correctly gates whether Guard 5 is even in the
  warden chain. Confirmed correct, not the issue.
- `EvidenceAnchorWarden` only REFUSEs when a candidate's `SupportProfile` is synthetic-only
  (`domain/self_reinforcement.py`: `is_synthetic_only` / `has_external_anchor` against
  `ANCHOR_KINDS = {"user", "log", "test", "git", "file", "external", "manual", "timestamp"}`,
  `domain/truth/kinds.py`).
- **Live query against the actual graph** (`menhir-lme-scalar-canonical-ku78-v1-20260806`,
  restarted read-only for this check, stopped again after):
  ```cypher
  MATCH (e:Episodic) WHERE e.group_id STARTS WITH 'lme-'
  RETURN e.source, count(*)
  -- "user": 1826, "remote-api": 58, "message": 6
  ```
  **96.6% of episodes carry `source="user"`** -- confirmed in the ingest code too
  (`scripts/longmemeval/lib/ingest.py:264`: `source=("user" if is_user else None)`).
  `"user"` is in `ANCHOR_KINDS`, so nearly every candidate already has a legitimate external
  anchor by construction (LongMemEval haystacks are simulated user statements). Guard 5 in
  hard mode (D) therefore ADMITs almost everything already, the same as soft mode (E) --
  there's barely any synthetic-only population for the hard/soft distinction to act on. The
  remaining ~64 non-`user` episodes (2-4 per namespace, scattered thinly across ~30
  namespaces) plausibly explain D's slightly higher token count vs E ($0.218 vs $0.208) but
  weren't enough to flip any answer.

**Verdict: arm E is configured correctly.** The D=E result is a genuine property of this
corpus (heavily user-anchored by construction), not a wiring bug. Evidence-anchor strictness
would plausibly show a real difference on a corpus with a meaningful share of purely
agent-inferred/LLM-summarized content lacking user/git/test/file provenance -- this fixture
isn't that.

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
