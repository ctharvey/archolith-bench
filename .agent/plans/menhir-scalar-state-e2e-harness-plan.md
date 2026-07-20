# Plan: `menhir-scalar-state` e2e bench harness

**Status:** ACTIVE (2026-07-20)
**Project:** archolith-bench (+ menhir launch profile)
**Origin:** `menhir/.agent/for-review/HANDOFF-2026-07-20-scalar-state-end-to-end-testing.md`;
successor to the CLOSED lexical typed-value sidecar line (`scripts/longmemeval/analysis/TYPED-VALUE-ARM.md`).

## Goal

Exercise Menhir Piece C (ScalarStateView) **end to end** through archolith-bench: real LLM perceiving
typed scalars from **real ingested `:Episodic` episodes** -> binding -> materialized `scalar_state`
Views via the **real background scheduler**, then verify over bolt. This is the acceptance/integration
test the handoff sets up; it is NOT part of Menhir's frozen gate and must not modify frozen `src/` or
existing tests.

## Why the existing `menhir-phase3` harness can't do this

Typed-scalar perception runs ONLY inside scheduled personal-memory consolidation gated by
`MENHIR_PERSONAL_MEMORY_SCALAR_STATE_ENABLED=1`. The HTTP `POST /api/phase3/run` route does NOT pass
`enable_scalar_state`, so the black-box phase3 surface cannot trigger it. Chosen trigger (user
decision): **run the throwaway menhir with the flag on + the background scheduler on (benchmark mode
OFF) and a short consolidation interval; the scheduler tick materializes the Views.**

## Verified anchors

- Producer: scalar-dirty detection = `MATCH (e:Episodic) WHERE e.content STARTS WITH 'user:'`
  (`personal_memory_queries.py:88`). Bench `HttpMenhirClient.ingest(ns, "user", text, source="user")`
  builds `episode="user: <text>"` -> exactly the shape scalar perception consumes.
- Trigger: `runtime.py:79-110` starts `MaintenanceScheduler` with
  `scalar_state_enabled=settings.personal_memory_scalar_state_enabled` when
  `personal_memory_consolidation_enabled` is on; scheduler tick -> `consolidate_personal_memory(...,
  enable_scalar_state=True)` -> `TypedScalarPerceptionService.perceive_and_persist`.
- Suppressor: `MENHIR_BENCHMARK_MODE=1` disables the scheduler (`runtime.py:400`). MUST be off here.
- Interval: `MENHIR_PERSONAL_MEMORY_CONSOLIDATION_INTERVAL_S` (default 300s) -> set low (e.g. 5s).
- Verification is bolt-only (recall will NOT surface shadow Views) -- handoff Cypher in section 7.
- neo4j python driver is an OPTIONAL bench extra (`pyproject.toml` content-vector), NOT installed ->
  add it to the harness's deps / bench venv.

## Deliverables

1. **Menhir throwaway launch profile** (runbook, benchmarks/): serve on a throwaway port against the
   throwaway Neo4j (`docker-compose.benchmark.yml`, bolt 7688) with:
   `MENHIR_BENCHMARK_MODE=0`, `MENHIR_PERSONAL_MEMORY_CONSOLIDATION_ENABLED=1`,
   `MENHIR_PERSONAL_MEMORY_SCALAR_STATE_ENABLED=1`,
   `MENHIR_PERSONAL_MEMORY_CONSOLIDATION_INTERVAL_S=5`, real LLM. Activation self-runs via
   `ensure_activated()`; the DB must be fresh/clean (activation refuses legacy stores).
2. **Bolt reader** (`archolith_bench/harness/scalar_bolt.py`): a thin neo4j read-only helper with the
   three handoff queries -> `read_typed_assertions(ns)`, `read_scalar_state_views(ns)`,
   `read_pending_advisories(ns)`. Read-only; refuses a prod URI (mirror the `:7688`-only discipline).
3. **Harness module** (`archolith_bench/harness/menhir_scalar_state.py`): fixtures (known typed-scalar
   sentences spanning the 9 ValueKinds), `ScalarStateCase`/`ScalarStateResult` dataclasses, driver
   `run_scalar_state(...)`, invariant validators, `write_scalar_state_evidence(...)` reporter,
   `MenhirScalarStateAdapter` (benchmark_id `menhir-scalar-state`) + `is_scalar_state()`.
4. **Offline stub** (`StubScalarStateClient` / fake bolt) for a network-free CI smoke of the harness
   itself (mirrors `StubPhase3Client`).
5. **CLI wiring** (`cli.py`): register the adapter + a `_run_scalar_state_harness` dispatch mirroring
   `_run_phase3_harness`; require `--menhir-url`, `--neo4j-uri` (bolt), `--confirm-menhir-reset`.
6. **Tests** (`tests/test_menhir_scalar_state.py`): offline, stub-driven, mirror
   `test_menhir_phase3.py`. No live calls in CI.
7. **Runbook** (`benchmarks/RUNBOOK-scalar-state-e2e.md`): launch profile + repro command + teardown.

## Driver flow (`run_scalar_state`)

1. Guard `reset_confirmed`; pick fresh namespace `scalar-e2e-<hex>`.
2. Teardown ns (best-effort) for a clean slate.
3. Ingest N known typed-scalar episodes via `/api/memory` (`role="user"`, `source="user"`, grounded
   with a recorded `:TurnEvidence` uuid so entity resolution + admission behave like production).
   Space `occurred_at` so cursor ordering is deterministic.
4. Poll bolt until `scalar_state` Views appear for the ns OR a bounded timeout (~ N intervals + margin);
   the scheduler runs the pass asynchronously.
5. Read `:TypedAssertion` rows + current `scalar_state` Views + pending advisories over bolt.
6. Validate INVARIANTS (not exact stochastic values): exactly one current View per (subject, slot);
   Views land in the seeded ns (never `default`); `evidence_tier='agent'`; no duplicate current keys;
   `binding_pending=false` for resolvable-entity statements; advisories are the `unbound:` sentinel;
   seeded `value_kind`/`value` present among assertions for the unambiguous cases. Expected abstains
   (no clear entity / low k-agreement / non-scalar) are recorded, not failed.
7. Teardown ns; emit evidence (markdown + json) + repro command.

## Fixtures (known inputs -> expected)

Span the 9 ValueKinds with unambiguous, single-entity sentences so binding is deterministic, e.g.:
`"I own 37 rare coins"` (count), `"my character's HP is 80"` (hp), `"I paid $250 for it"` (money),
plus a rating/quantity/duration example, one deliberate no-entity advisory case, and one non-scalar
control that must produce nothing. Keep prompts verbatim + hashed (`fixture_hash`) for reproducibility.

## Non-goals / guardrails

- No changes to frozen Menhir `src/` or existing Menhir/bench tests. Harness is additive.
- Never point the bolt reader or ingest at prod (`:7687` / `:8090`); throwaway only.
- Stochastic perception -> assert invariants, pin temp low-but->0; don't hard-assert exact values.
- Piece D (recall authority) is out of scope.

## Live run findings (2026-07-20)

First live run (throwaway menhir :8098, fresh ephemeral Neo4j bolt :7691, gpt-4o-mini). Surfaced two
LAUNCH-PROFILE blockers (both fixed in `scripts/run_scalar_state_e2e.sh`) and one Menhir BEHAVIORAL
result:

1. **Docker daemon must be up** (obvious, but the script fails fast if not).
2. **Scheduler-lease collision (non-obvious, important).** The maintenance-scheduler lease is a
   cross-process SQLite lease (`scheduler_lease.py`) in a SHARED telemetry DB
   (`.agent/mcp_telemetry.db`, override `MENHIR_MCP_TELEMETRY_DB`), keyed by `lease_name`. The
   operator's LIVE menhir (pid holding the lease) blocks a throwaway that shares the DB -> the
   throwaway's scheduler never starts -> zero consolidation -> zero scalar Views. Fix: the script
   exports a per-run `MENHIR_MCP_TELEMETRY_DB` so the throwaway gets its own empty lease table.
3. **Behavioral result (open):** with the scheduler running, perception produced only **2 typed
   assertions from 9 view-episodes, both `binding_pending` (unbound)** -> **0 committed Views**,
   verdict FAIL. Controls/advisory cases behaved correctly. This is the entity-resolution wall the
   sidecar research (`TYPED-VALUE-ARM.md`) predicted: typed scalars perceived but not bound to
   resolved entities. Root cause not yet isolated (perception yield vs binding vs model). Needs a
   `--keep` graph inspection + DEBUG perception logs; possibly a stronger extraction model than
   gpt-4o-mini, and/or grounding that guarantees resolvable entities. NOT a harness defect -- the
   harness correctly reported the negative result over bolt.

Secondary (cosmetic): uvicorn access-log emits a `client_addr` KeyError under menhir's log format
(noise, unrelated to scalar); the harness picks up a stray bearer key even against an auth-disabled
server (harmless).

### Root cause of the 0-View result (--keep graph inspection, 2026-07-20)

Inspected the preserved namespace over bolt (`scripts/inspect_scalar_state_graph.py`, added
`--scalar-no-cleanup` to keep the namespace). Definitive two-part cause:

1. **Low typed-scalar perception yield.** All 11 episodes are correct `:Episodic` `user:` bodies and
   the scalar watermark advanced (the pass ran), but the typed-scalar perceiver emitted only **2**
   assertions: `finished_reading=Dune` (status) and `remaining_books=12` (count, misread from "there
   are 12 of them left"). The clean first-person "my X is N" statements (height 180, commute 45, gym
   3x, wake 7:30, weekday Wednesday, car red) produced NO typed scalar. Meanwhile the NUMERIC counter
   path captured coins=37 and headphones spend=250 as `view_kind=counter` Views -- so extraction works,
   the *typed-scalar* perceiver is what under-fires.
2. **No bindable entity -> 0 Views.** Both emitted assertions have `subject_display='user'` and
   `subject_uuid='unbound:<hash>'` (`binding_pending=true`). The namespace contains ONLY 13 `:Entity`
   nodes (11 `admission_audit` bookkeeping + 2 `counter` Views) besides the 11 episodes and two
   watermarks -- there is NO resolved subject/self entity to bind to. So self-referential ("user"/"my")
   typed scalars cannot bind, and nothing folds into a `scalar_state` View.

Net: on a first-person fixture in this config the scalar_state e2e path materializes 0 Views. The
harness correctly reported it over bolt. The Piece-C gaps this surfaces, for the menhir owner:
(a) typed-scalar perception yield is low vs the counter path; (b) the binder has no resolved entity
-- especially no "user"/self entity -- to attach user-property scalars to. Likely next levers: a
self/"user" entity to bind first-person scalars, and/or stronger extraction; a fixture with named
third-party subjects would test binding independent of the self-entity gap.

### Lever 3 result: named third-party fixture (2026-07-20) -- FIRST MATERIALIZED VIEW

Ran the `third-party` fixture (`Alice owns 37 coins` / `Alice has read 12 books` / `Alice wakes up at
7:30 AM`) live with `--keep`, four-checkpoint bolt inspection. **Piece C's bind->fold->View machinery
is PROVEN to work end to end** -- but a precise multi-fact linkage blocker was isolated:

Checkpoint results:
- **Graphiti entity extraction WORKS.** Plain KG `:Entity` nodes `Alice`, `37 coins`, `12 books` were
  extracted (so Lever 0 -- "no entity extraction" -- is REFUTED). (`:Episodic` nodes carry no
  status/enrichment fields on this path, so `processing_completed_at` is not a usable control; entity
  existence is the processing evidence.)
- **MENTIONS linkage is consolidated onto ONE episode.** ALL three entities are `MENTIONS`-linked from
  the LAST episode ("Alice wakes up..."), NOT from the episodes that stated them. Episodes 1-2 have zero
  linked entities.
- **Binding + View WORK when the entity is linked to the assertion's episode.** The `wake_time`
  assertion (episode 3, which owns the Alice link) bound to a real Alice UUID
  (`binding_pending=false`) and **materialized a `scalar_state` View** -- the first View this harness
  has ever produced. The `coins` assertion (episode 1, no linked entity) stayed `unbound`, and the
  episode-scoped `repair_pending_bindings` pass CANNOT rescue it (it re-resolves against episode-1's
  links, which are empty). Verified stable across two inspections minutes apart -- permanent, not a
  timing artifact.

Refined conclusions for the menhir/Piece-C owner:
1. **Machinery is sound** -- bind -> fold -> `scalar_state` View works against a real linked entity.
2. **The multi-fact binding blocker is entity->episode MENTIONS LINKAGE**, not extraction: Graphiti
   attaches all batch entities to one episode, so typed-scalar assertions on the other source episodes
   have an empty binding-candidate set and go permanently unbound. This is the top lever now.
3. **First-person additionally needs a self/"user" entity** (no `user` KG entity is ever extracted) --
   but do NOT implement it before the linkage issue: a self-entity would mask the linkage gap.
4. **Yield still partial**: `12 books` produced a counter View but NO typed assertion (2/3 typed
   assertions emitted).
5. **Bug (new):** the materialized clock_time View has `view_value=0.0` -- the `07:30` clock_time did
   not carry into the numeric `view_value`. Possible clock_time View-materialization defect.

Harness additions for this: `third_party_scalar_state_cases()` + `--scalar-fixture {default,third-party}`
(runner `SS_FIXTURE`); the inspector now emits the four-checkpoint bundle (processing state, linked
non-View entities, MENTIONS direction, assertions, Views).

### Bounded root-cause pass -> HANDED OFF (2026-07-20)

Per-call MENTIONS capture (`scripts/diagnose_mentions_provenance.py`, `SS_DIAG=1` runner mode): ingested
the three Alice statements one at a time and snapshotted after each. The Graphiti extraction payloads
(server logs) pinpoint the FIRST incorrect boundary: **a lone `"Alice owns 37 coins."` persists ZERO
entities** — the extractor emits a derived possessive entity (`Alice's coins`) + an edge sourced at
`Alice` (absent from `extracted_entities`), graphiti_core resolves to zero nodes, and menhir logs
`Zero-extraction (success)`. The subject only materializes when a LATER episode pulls prior episodes as
context and re-extracts them attributed to the latest episode (bucket 4: context/provenance contract);
plus a whole-batch `CombinedExtraction` ValidationError can zero an episode on one malformed edge. This
is an INGESTION/PROVENANCE defect at the menhir<->Graphiti extraction boundary, NOT a Piece C reopen (the
bind/fold/View machinery is proven). Full handoff (reproducer, per-call args, per-call graph state,
earliest incorrect state, suspected owning functions, minimal regression, invariant):
`menhir/.agent/for-review/HANDOFF-2026-07-20-scalar-state-mentions-provenance-defect.md`. Levers remain
paused (no self entity, no perceiver tuning, no Phase D). Bench task complete — do not fix in Bench.

## Verification (this plan's own acceptance)

- Offline: `pytest tests/test_menhir_scalar_state.py -q` green (stub-driven).
- Live: one real run against throwaway :7688 + real LLM producing a PASS evidence artifact with >=1
  current `scalar_state` View in the seeded ns, tier=agent, zero default-silo Views, zero duplicate
  current keys.
