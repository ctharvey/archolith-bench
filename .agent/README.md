# archolith-bench — Project Context

> **menhir R2 facet work lives here** (`archolith_bench/facet/`). For the cross-repo picture — how this
> ties into menhir's research ladder, what's owed, what not to re-litigate — read the menhir handoff:
> `menhir/.agent/plans/chain-handoff.md`. Local R2 results + caveats: `.agent/benchmark-notes/facet-r2-demo-run.md`.

## Purpose
Unified benchmark suite for the archolith product family. Measures token savings, continuity, compression, and cross-product metrics across proxy, filter, audit, and stack scenarios.

## Suites
- **menhir bootstrap-hygiene**: Deterministic acceptance gate for structural/recent leakage, exact workspace isolation, scoped pins, stale advisories, and off-topic/token diagnostics
- **proxy** (Phase 1, critical path for June 30 launch): Multi-turn token savings + continuity across experiment arms
- **filter** (Phase 2): Compression-ratio product claim on real corpora via archolith-filter
- **stack** (Phase 3): Experimental four-way comparison (direct/filter/proxy/proxy+filter); pending refreshed live run before launch copy
- **audit** (Phase 4): MCP token-waste reduction before/after via archolith-audit
- **industry** (Launch gate): Product-to-benchmark coverage matrix tying Archolith claims to trusted external benchmark families

## Before writing a script, read the index

`projects/archolith/menhir/.agent/scripts-index.md` indexes **every durable script in both repos**
by the question it answers, and defines the naming convention: `_name.py` is a throwaway (delete it
once its finding is written down, never index it), `name.py` is a durable instrument (index it in
the same commit that adds it). **Keep the bench half of that index in sync** when you add, rename,
or remove a script here.

Before writing a new analysis script, check it there first. Two sessions in a row re-derived results
an existing instrument already produced.

The durable offline typed-scalar instrument is
`scripts/measure_deterministic_scalar_shadow.py`. It consumes only JSON captures from Menhir's
`scripts/freeze_scalar_samples.py`, loads the real Menhir proposal/gate/extractor/comparator from an
explicit checkout, reruns the pure deterministic extractor over frozen episode text, and replays
captured LLM proposals through the real gate/comparator. It makes no new LLM, network, Neo4j, Docker,
or service calls. The first held-out input is the versioned non-LME
`fixtures/deterministic_scalar_heldout_v1.json`; its six `2 namespaces × k=3` calls are smoke
evidence only, not a promotion or population gate. The paired Menhir workflow owns the exact
capture/report commands.

The research scalar-identity acceptance panel is deliberately smaller and has no runtime lane. It
feeds source-bound raw candidates through Menhir's pure research adapter and structural composer:

```bash
python scripts/measure_scalar_identity_acceptance_panel.py \
  fixtures/scalar_identity_acceptance_v1.json \
  --menhir-root ../menhir \
  --json-out results/scalar-identity-acceptance/report.json \
  --markdown-out results/scalar-identity-acceptance/report.md
```

The report is source-free and keeps `promotion_status=not_evaluable`; it is a regression panel, not
a population estimate or permission to route/persist deterministic candidates.

The paired noisy-language companion keeps clean and informal cases in separately reported slices:

```bash
python scripts/measure_scalar_identity_noisy_panel.py \
  fixtures/scalar_identity_noisy_v1.json \
  --menhir-root ../menhir \
  --json-out results/scalar-identity-noisy/report.json \
  --markdown-out results/scalar-identity-noisy/report.md
```

It reports paired invariance, perturbation coverage, and false-current-state errors. It remains a
bounded regression panel with `promotion_status=not_evaluable`, not a population estimate.

The opt-in mapped-isolation comparison runs the same fixture through both research paths and reports
identity differences and composition gains without source quotes:

```bash
python scripts/measure_scalar_identity_isolated_comparison.py \
  fixtures/scalar_identity_noisy_v1.json \
  --menhir-root ../menhir \
  --json-out results/scalar-identity-isolated/report.json \
  --markdown-out results/scalar-identity-isolated/report.md
```

The isolated adapter must be present in the selected Menhir checkout; the runner fails loudly rather
than falling back to the canonical adapter. This is research evidence only and never enables routing,
persistence, or scalar authority.

The cumulative-completion holdout reuses the same source-free comparison runner:

```bash
python scripts/measure_scalar_identity_isolated_comparison.py \
  fixtures/scalar_identity_cumulative_v1.json \
  --menhir-root ../menhir \
  --json-out results/scalar-identity-cumulative/report.json \
  --markdown-out results/scalar-identity-cumulative/report.md
```

`fixtures/scalar_identity_cumulative_v1.json` is a 24-case, 12-pair non-LME contract with six
train and six holdout pairs. Positive cases use only source-authored present-perfect completion
forms with strict `so far`/`to date` wording and typed operation `absolute`; adversarial cases
cover past, negation, modality/future, history, coordination, and subset/empty-target risks.
The validated result is baseline clean 12/12 (6 composed), baseline noisy 6/12 (0 composed), and
isolated clean/noisy 12/12 (6 composed each), with a +6 noisy composition gain and 0/0
false-current-state errors. It is a bounded regression instrument, not a production-promotion gate.

The dependency-evidence bridge has a separate offline measurement runner:

```bash
python scripts/measure_dependency_scalar_bridge.py --menhir-root ../menhir \
  --json-out results/dependency-bridge/report.json \
  --markdown-out results/dependency-bridge/report.md
```

It strictly verifies the 48-case fixture SHA/version, builds raw candidates from supplied subject,
operation/value, claim text, and locators, and loads the real Menhir adapter, immutable evidence
models, and Phase-A dependency rule. It has no LLM, network, runtime, Neo4j, cache, or
bridge-to-baseline fallback lane. Gold candidate locators are supplied explicitly, so span
recognition is reported as `not_measured_gold_locator_supplied`; role and operation
classification remain `not_measured`. Outputs refuse overwrite and create parent directories.

The authoritative r2 execution is recorded in
`results/dependency-scalar-bridge/phase-a-v1-20260806-r2/report.{json,md}` for fixture SHA
`bde118508cf55c94bbd10fc88fbc625a0f465859a545f3ca79deb391a25ba57b`: 48 cases, 5/6 supported
identities/provenance exact, 0/14 unsupported composed, 0/28 false-current, 45/45 evidence
provenance, 45/45 bridge provenance, 179/192 cue exact, and edges 135 TP / 180 predicted / 144
gold (P .75/R .9375/F1 .8333). Proposal parity was 45/48 (three `temporal_past_only` adapter
drops); composer replay was stable 45/45; baseline composition was 2/48 (43 abstain, 3 drops).
R1 was the historical first execution with incomplete git provenance; r2 changed instrumentation
only and aggregates/cases are identical. Promotion remains `not_evaluable`, and recognition,
role/operation, performance, cache, and full replay gates remain unmeasured. The one supported miss
is bare `retain`; no post-hoc holdout tuning is permitted—broader support requires an independent
policy panel. Report SHA256: JSON
`53aff17ecd1d758f2d808050e9ac8e2512f269a3254ae2fee99f25d2696fc412`; Markdown
`3284c6d81d47e22907c7fcd6fe79993ca65fa386a7206366d9d079ac78999287`.

## menhir ScalarStateView instruments (live here, documented in menhir)

`scripts/scalar_state_coverage.py` and its siblings (`run_scalar_state_e2e.sh`,
`inspect_scalar_state_graph.py`, `scalar_view_authority_live.py`, `scalar_leads_authority_live.py`,
`scalar_phase_d.py`) measure menhir's scalar/View ingest path. They live here because they import
`archolith_bench.harness.menhir_scalar_state` fixtures and the `scalar_bolt` prod guard.

Anyone working in menhir looks for them there and does not find them, then re-derives the answers by
hand. The index that prevents that is
`projects/archolith/menhir/.agent/workflows/scalar_state_measurement.md` — **keep it in sync when
adding, renaming, or removing an instrument here.**

Frozen methodology: every measured run uses a FRESH ISOLATED menhir+neo4j stack. Stacking rounds on
one stack is invalid for comparative yield.

## How to Run
```bash
pip install -e .
python -m pip install -e ../archolith-filter
python -m pip install -e ../archolith-mcp-audit
pip install -e ".[all]"                 # optional filter/audit suite deps after sibling editable installs
archolith-bench proxy --list          # list scenarios (no proxy needed)
archolith-bench proxy --all --arms direct,proxy_only  # run against live proxy
archolith-bench industry --launch-only                # generate launch benchmark coverage matrix
archolith-bench menhir bootstrap-hygiene --offline   # deterministic startup hygiene gate
```

Offline deterministic scalar shadow measurement:
```bash
python scripts/measure_deterministic_scalar_shadow.py frozen.json \
  --menhir-root C:\path\to\projects\archolith\menhir \
  --json-out report.json --markdown-out report.md
```
The command defaults to exactly the candidate 2/3 threshold with span alignment enabled. Reconciliation
and canonical-self switches are opt-in and are recorded as effective report settings. A namespace
with any fallback episode retains its entire k-call batch in the conservative savings calculation.
The optional v1 sidecar is capture-bound by a required exact set of unique canonical SHA-256 hashes.
Its `false_positive` and `false_current` rows are human-labeled known-negative targets; the report
uses target-hit fields, never an overall/population false-positive or false-current rate, and does
not claim the plan's population precision/confidence-interval gate.

Offline compositional scalar semantic panel:
```bash
python scripts/measure_compositional_scalar_panel.py \
  fixtures/compositional_scalar_generic_v1.json \
  --menhir-root C:\path\to\projects\archolith\menhir \
  --json-out panel-report.json --markdown-out panel-report.md
```
This is the capture-independent, source-labeled lane. Its v1 generic holdout has 12 positive and 12
negative cases, four relation groups, and at least three perturbations per group. It reports exact
join and semantic quality separately and is permanently descriptive until a separately
preregistered population gate exists.

### Progress on long runs
Long bench loops (R1/facet ladders, live recall) print a live heartbeat via
`archolith_bench/progress.py` — `ProgressReporter` / `track` / `run_ladder`. Progress goes
to **stderr**, so run the script directly (don't pipe stdout through `tail` — it buffers to
EOF and hides everything). Full usage + adoption guide:
[`.agent/workflows/bench-progress.md`](workflows/bench-progress.md).

## LongMemEval Framework

Memory-specific A/B testing for menhir's recall and ingest, consolidated under
`scripts/longmemeval/` (one `config.sh`, one `lme.sh` dispatcher, one runbook). See
`scripts/longmemeval/README.md` for the full runbook and `lme.sh -h` for all verbs.

Quickstart:
```bash
./scripts/longmemeval/lme.sh -h                 # all commands
./scripts/longmemeval/lme.sh status             # read-only graph/queue state
./scripts/longmemeval/lme.sh build 500          # persistent graph (~1 day for oracle)
./scripts/longmemeval/lme.sh recall-ab main 30  # recall-only A/B against that graph
./scripts/longmemeval/lme.sh matrix             # analysis: accuracy × config × question-type
```

**⚠️ Stratification (load-bearing):** the dataset is grouped by `question_type`, so a bare
`--limit N` samples only `temporal-reasoning` (the hardest type) — a fair run MUST sweep all 6
types via `--subset`. The `matrix`/`msc`/`ablation` verbs already do; see the runbook's
Stratification section. Every value in `config.sh` is env-overridable; nothing is hardcoded in
the scripts. OpenAI key is read at runtime from `menhir/.env`, never committed.

## Headline Numbers Policy

**`HEADLINE-NUMBERS.md` is the canonical source for any stat used in marketing copy or README headlines.**
Before writing any percentage or token count into archolith.dev or a product README:
1. Check `HEADLINE-NUMBERS.md` — if it isn't there, it isn't verified.
2. Run the benchmark, paste the result row into the table, note the commit.
3. Fixture data (from bundled `fixtures/`) is NOT a headline number — it demonstrates report format only.

## KU-Buildout Ledger

**`results/lme-ku-buildout/LEDGER.md` must be updated after every knowledge-update
buildout run.** This includes the scoreboard, per-item results, fixture provenance,
and infrastructure details. See `scripts/longmemeval/README.md` § "KU-Buildout Ledger"
for the full checklist. Do not end a session that ran a buildout without updating the
ledger.

## Launch Readiness

Use `.agent/launch-readiness-tracker.md` as the active pre-launch checklist.
The current posture is imminent pre-launch: fix Critical and High items first,
and defer polish unless it blocks installability, reproducibility, or trust.

## FOLLOW-UP
- GitHub remote `archolith/archolith-bench` still needs creating. Add with: `git remote add origin git@github.com:archolith/archolith-bench.git`
- `archolith-filter` and the `archolith-audit` distribution are optional extras (`filter`, `audit`, `all`) so base install remains usable before those sibling packages are published. For source checkouts, install sibling repos editable from `../archolith-filter` and `../archolith-mcp-audit` before `pip install -e ".[all]"`. The audit distribution imports as `archolith_mcp_audit`.
- The industry benchmark registry is launch-facing. Candidate benchmarks are gates, not completed evidence, until a tracked artifact exists under `benchmarks/`.
