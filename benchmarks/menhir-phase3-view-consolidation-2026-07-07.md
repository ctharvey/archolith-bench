# Menhir Phase 3 View Consolidation — 2026-07-07

**Type:** Consumer-pipeline validation (NOT a proxy A/B, NOT a model score). Validates the
selective-capture *consumer* end to end against a throwaway menhir:

```
:TurnEvidence -> Phase 3 consolidation -> View writes
             -> abstention receipts   -> supersession/currentness -> recall
```

The producer (the host `UserPromptSubmit` triage) is **frozen**; fixtures encode its verdicts,
so junk is dropped exactly as the live triage drops it. What is measured is the consumer: given
the producer's decisions, does consolidation write the right Views, abstain *visibly* (never
silently), supersede on correction, and stay idempotent.

**Harness:** `archolith-bench harness menhir-phase3` (in-repo; `archolith_bench/harness/menhir_phase3.py`).
Black-box HTTP — no menhir import, no Cypher. Mirrors the live `menhir/scripts/validate_phase3_realdata.py`
scenario (`b144381`).

**Under test (commits):**
- menhir `e12a0af` (Phase 3 HTTP endpoints) + `1965997` (docs) — `main`
- archolith-bench `72fea60` (on `claude/menhir-chain-handoff-doc-7iuat2`): `9cfe2ef` benchmark, `9633c33` bearer, `72fea60` robustness

**Menhir endpoints exercised** (added `e12a0af`): `POST /api/turn-evidence`, `POST /api/phase3/run`,
`GET /api/phase3/status`, `GET /api/views`, `POST /api/phase3/reset`.

## Scenario

One isolated namespace per run: `reset -> capture phase-A candidates -> run#1 -> idempotent
re-fold (run#2) -> capture phase-B correction -> run#3 -> inspect Views / receipts / history`.
Each run self-isolates (namespace-scoped `turn_key`) and self-cleans (teardown).

## Cases

| Case | Prompt | Expected consumer outcome |
|------|--------|---------------------------|
| stated measure | `I have 25 movies on my watch list.` | View `movies/watchlist = 25` |
| fold SUM | `I bought one bike for $50 and another for $75.` | View `bike_spend = 125` (canonical key) |
| correction / supersession | `Actually it is 20, not 25.` | current `= 20`, prior `25` superseded (`expired_at` set) |
| junk / drop | `write the handoff` | dropped by triage; no evidence, no View |

## Result

**Verdict: PASS — 3/3 consecutive live runs** against a throwaway menhir (`:8099`, `MENHIR_BENCHMARK_MODE=1`,
sharing `yawn-neo4j` but isolated namespace + teardown; the live WSL menhir on `:8090` was not touched).

| Case | Result |
|------|--------|
| stated measure | PASS |
| fold SUM | PASS |
| correction / supersession | PASS (25 -> 20, `expired_at` set) |
| junk / drop | PASS |

### Safety invariants (0 every run — these are the verdict gates)

| Invariant | Value |
|-----------|-------|
| `wrong_view_writes` | 0 |
| `silent_abstentions` | 0 |
| `duplicate_writes_on_rerun` | 0 |

## Known stochastic behavior (by design, not a defect)

The k-sample extractor (`gpt-4o-mini @ k=3`) commits the *derived* SUM ~8/10 and **fails closed**
otherwise — menhir's own extractor matrix (menhir CHANGELOG 2026-07-07). Observed live: the fold
abstained on some passes with **visible receipts** (`silent_abstentions=0`), then committed `125`
on another pass. The benchmark therefore validates the correct value across **all** consolidation
passes (batch re-fold is idempotent; committed Views persist), which strictly requires `125`/`25`
to have committed without penalizing a single stochastic miss. Counter-key drift
(`bike_purchase` vs canonical `bike_spend`) is reported as a **warning**, not a failure — the
value is the hard gate.

## Bug found and fixed (the reason the benchmark was worth running)

A live throwaway re-run — which a pure service-layer mock would likely have missed — found a
**persistence/idempotency bug**:

- menhir `MERGE`s `:TurnEvidence` on a **global** `turn_key` derived from prompt text (no namespace).
- A second run with the same fixture prompts under a fresh namespace bound to the *prior* run's
  node (`created=false`), so the new namespace captured nothing (`turn_evidence_created=0`,
  `phase3_selected=false`) and consolidation wrote nothing.
- **Fix (`72fea60`):** scope the posted `turn_key` by namespace (`{namespace}:{case_id}`), plus
  end-of-run teardown so no residue lingers between runs. Regression test added.

This validates benchmarking through the real HTTP/API path rather than service-layer tests only.

Two secondary corrections in the same commit:
- `duplicate_writes` false positive: a measure that abstained on run#1 then committed on the
  idempotent re-fold was miscounted as a divergent write. Now counts only value **changes** on
  measures present in both passes; new commits are tracked as `late_commits` (informational).
- Report model label: the LLM under test is menhir's **server-side** personal-memory model, not
  the harness `--model`.

## Expanded scenario suite (2026-07-07, offline-verified)

Beyond the core 4-case flow, `archolith_bench/harness/phase3_scenarios.py` adds a declarative
suite of consumer stress scenarios (`Scenario` = scripted `Post` phases + typed assertions,
with a `gate` vs **characterization** split). Gate scenarios fold into the run's exit code;
characterization scenarios document menhir's current behavior on genuinely-uncertain paths and
never fail the verdict.

| Scenario | Kind | Checks |
|----------|------|--------|
| `ambiguous-correction` | gate | two Views == 25 -> a bare `20, not 25` touches NEITHER (F2 abstain) |
| `currency-worded-sum` | gate | `50 dollars and 75 dollars` folds to `bike_spend = 125` |
| `multi-namespace` | gate | identical fixtures in two namespaces capture independently |
| `count-vs-spend` | characterization | `2 bikes for $125` -> count(2) and spend(125) do not merge |
| `negative-correction` | characterization | `Not 25 anymore, it is 20` supersedes only via the connective rule |

The two characterization scenarios are marked non-gate because whether menhir extracts a
separate count from one sentence, and whether the connective rule recognizes the negative
phrasing, are exactly what the benchmark is there to *measure*. Offline-tested against a per-
namespace fake modeling the F1/F2 behavior; **live characterization run is pending** (real LLM
spend — see Reproduce).

## Verification

- menhir route tests: **21/21** (`tests/test_api_routes.py`, incl. `TestPhase3` +7).
- archolith-bench: **389 passed** full suite; core driver tests **9/9**
  (`tests/test_menhir_phase3.py`, incl. namespace-scoped `turn_key` regression) + scenario suite
  **8/8** (`tests/test_phase3_scenarios.py`, incl. gate/characterization split).

## Reproduce

```bash
# 1. Throwaway menhir (separate from any live instance), from the menhir repo venv:
ENV_FILE=./.env MENHIR_BENCHMARK_MODE=1 .venv/Scripts/python.exe -m menhir.main serve --port 8099

# 2. Benchmark (MENHIR_AGENT_KEY = menhir's agent-tier bearer if auth is enabled):
archolith-bench harness menhir-phase3 \
  --menhir-url http://127.0.0.1:8099 \
  --confirm-menhir-reset \
  --format markdown --out results/menhir_phase3_view_consolidation.md
```

The generated `results/` report is gitignored (local evidence); this file is the durable summary.
