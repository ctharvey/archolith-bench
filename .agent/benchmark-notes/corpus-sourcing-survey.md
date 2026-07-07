# Corpus sourcing survey — can a public dataset feed the R1/R2 data phase?

_2026-07-05. Companion to `r1-dummy-gold-run.md` (R1 gold) and `lme-score-campaign.md`
(LongMemEval). Question: is there an off-the-shelf internet corpus that qualifies for the
corpus-gated half of R1 `hybrid_alpha` tuning and R2 facet graduation — or must we author it?_

## Verdict

**No public corpus qualifies as a drop-in.** Our data phase needs a *union* of four axes,
grounded in the agent's **own** repository memory graph, with per-query gold support IDs and
menhir-specific facet/belief labels. Every public corpus covers **one** axis and none is grounded
in our repos. So the corpus does not "apply" as-is. It is, however, only partly a "write them"
problem: **the fixtures already exist as drafts** (`fixtures/facet_r2_draft.json` 50/20,
`fixtures/r1_dummy_gold.json` 135 queries). What is missing is not authoring — it is graph-gated
*validation* (real embedder + live graph) and adversarial hardening. Public corpora are best used
as **methodology/templates**, not ingested data.

## What the data phase actually requires (the union)

The R1 ladder families (`deferred-verification.md`) and R2 facet fixture (`facet-retrieval.md`)
together demand ALL of:

1. **Code / symbol / structural queries with a semantic gap** — query semantically close but
   lexically distant from a KNOWN-gold code node (`paraphrased_debug_question`,
   `symbol_name_query`, `buried_relevant_memory`). This is where R1's source-aware floor earns its
   keep; a lexical baseline already nails verbatim queries.
2. **Temporal supersession** — stale-vs-current, superseded beliefs, knowledge-update
   (`stale_semantic_neighbor`, `historical_only_vs_current_truth`).
3. **Cross-repo / namespace scope distractors** — the same topic living in two repos, where the
   right answer depends on scope (`wrong_repo_same_topic`; R2 `repo`/`project`/`namespace` facets).
4. **Multi-session synthesized facts** — an answer assembled across sessions, not sitting in one
   memory (the LongMemEval "aggregation is a consolidation problem" slice).

Plus two properties no public benchmark has:
- **Gold grounded in the agent's OWN graph.** `wrong_repo_same_topic` requires our real collisions
  (the `cth.mcp.memory -> yawn_memory -> menhir` rename chain, CE-willow drift, real files/symbols/
  bugs). A generic corpus cannot supply "the wrong repo that shares this exact topic with ours."
- **menhir-specific labels** — R2 facets (`actor/object/operation/file/symbol/test/valid_time/
  learned_time/evidence_type/source_id/repo/project/namespace/belief_bucket`) and belief buckets.

## Public-corpus survey, per axis

| Axis | Best public corpora | Fit verdict |
|------|---------------------|-------------|
| 1. Semantic-gap code retrieval | **CodeSearchNet**, **CoSQA / CoSQA+**, **CoIR** (unifies 10 datasets / 8 tasks), **CoQuIR** | Strong on axis 1 only. Real NL->code query/gold pairs — exactly the paraphrase/symbol methodology. But generic OSS, **not our repos**; no temporal/scope/facets. |
| 2. Temporal supersession / knowledge-update | **SituatedQA** (answer flips with the timestamp), **TimeQA**, **StreamingQA**, **TempLAMA**, **PAT-Questions** (present-anchored, self-updating); **"Supersede: the memory-update gap in LLM agents"** (2026) | Strong template for axis 2 only. Wikipedia/world facts, **not code or agent-memory**; no symbol/scope/facet structure. |
| 3. Cross-repo / repo-level retrieval | **RepoBench-R**, **CORE-Bench** (multi-location retrieval under a repo state + local distractors), **CodeScaleBench** (CSB-Org, 40+ repos), **RANGER** | Closest to structural + cross-repo scope. But gold = **code locations, not memory nodes**; no temporal supersession, no belief buckets, no facets. |
| 4. Long-term multi-session memory | **LongMemEval** (already in use — info-extraction / multi-session / temporal / knowledge-update / abstention), **LoCoMo**, **BEAM** (mem0, 2026), **MSC** | Best single fit for axes 2+4. But **conversational personas, not code**; memories are user preferences/personal facts, not symbols/repos; not grounded in our graph. |

Already vendored as SAMPLES in `fixtures/` (evidence the team surveyed these before):
`longmemeval_sample.json`, `longbench_v2_sample.json`, `swebench_report_sample.json`,
`bigcodebench_hard_sample.json`, `agentdojo_results_sample.json`, `mteb_results_sample.json`,
`cyberseceval_stat_sample.json`. These are reporting/format samples, not graduation corpora.

## Why none qualifies as a drop-in

No public corpus is the *intersection* — code semantic-gap **and** temporal supersession **and**
cross-repo scope **and** facet/belief labels **and** gold grounded in the agent's own repos. Each
covers one column above. Ingesting a foreign corpus into a menhir graph would also **break the
load-bearing property** the bench exists to test: that gold is a real node in the real graph, so
the source-aware floor / scope warden / currentness warden are exercised against genuine
collisions, not synthetic ones. Foreign data can seed *phrasings*; it cannot supply *our* gold.

## What IS borrowable (methodology / templates, not data)

- **CoSQA / CoIR generation recipe** (NL query paraphrasing a code node) — this is already what
  `scripts/mine_r1_gold.py --paraphrase` does (LLM rewrites each gold node's summary into a
  question sharing no identifier words). The public corpora **validate the approach** and can seed
  additional phrasing diversity, but the gold stays our mined node uuids.
- **SituatedQA / PAT-Questions timestamp-flip template** — "answer as of date X vs date Y" is the
  exact construction for the `historical_only_vs_current_truth` / `stale_semantic_neighbor`
  families; instantiate it over our supersession chains (belief buckets), not over Wikipedia.
- **CodeScaleBench / CORE-Bench** — confirm `wrong_repo_same_topic` and multi-location structural
  retrieval with distractors are real, studied failure modes; useful as design corroboration.

## Recommended write actions (the honest remaining work)

The fixtures are written; the remaining work is graph-gated and cannot produce a *valid* result
offline (the semantic-gap thesis needs real embeddings, and a stub-scored hand-authored fixture
just re-saturates like `r1_demo.json`). So:

1. **R1 (item 2, corpus-gated):** scale `paraphrased_debug_question` 40 -> ~150-200 via
   `mine_r1_gold.py --paraphrase` on the live graph; fix/replace the de-CamelCased
   `symbol_name_query` + `wrong_repo_same_topic` families. Optionally cross-check phrasing
   diversity against a CoSQA slice. Then re-run the (now recalibrated) gate; only if the
   source-aware-floor win holds, set `hybrid_alpha`.
2. **R2 (item 3, Chunk F):** harden `facet_r2_draft.json` with ctharvey (avoid the "too clean"
   risk), swap in a real `EmbeddingScorer` + the live-graph retriever, re-run the promotion gate.
3. **Shared prerequisite:** both need the LongMemEval-seeded Neo4j corpus (the "RESUMABLE OVERNIGHT
   TASK" — a persistent graph of ~500 items for recall-only A/B). That is the real unblock; a
   public download is not.

## One-line answer

There is no internet corpus to drop in — our data phase is a menhir-specific union grounded in our
own repos — and we don't need to author from scratch either: the draft fixtures exist. The gap is a
**live-graph validation run**, not a missing dataset. Public corpora contribute methodology
(CoSQA/CoIR paraphrasing, SituatedQA timestamp-flips), not gold.
