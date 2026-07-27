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
