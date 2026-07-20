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

## Verification (this plan's own acceptance)

- Offline: `pytest tests/test_menhir_scalar_state.py -q` green (stub-driven).
- Live: one real run against throwaway :7688 + real LLM producing a PASS evidence artifact with >=1
  current `scalar_state` View in the seeded ns, tier=agent, zero default-silo Views, zero duplicate
  current keys.
