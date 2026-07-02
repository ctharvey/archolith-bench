# Plan: Organize the LongMemEval testing framework in archolith-bench

Status: PLANNED — execute after the running buildout job finishes (see Execution gate).

## Context

The LongMemEval (LME) Mode-B testing capability grew organically across several sessions.
It works, but it is **not reusable by anyone but its author**:

- **Load-bearing scripts are not even committed.** `_lme_build_db.sh` (builds the graph),
  `_lme_progress.sh`, `_run_lme_variant.sh`, `_lme_expected.py`, `_overnight_ab.py` are all
  UNTRACKED — a fresh clone can't run the workflow.
- **The one committed doc is stale.** `scripts/README-longmemeval-modeb.md` describes a
  deepseek-v4-flash + `run_longmemeval_modeb.sh` + throwaway-compose (bolt 7688) flow. The
  real flow today is OpenAI extraction + a *persistent* `menhir-lme-neo4j` graph (bolt 7689)
  built by `_lme_build_db.sh`, then recall-only A/B via `run_lme_recall_ab.sh` (bolt 7689,
  gpt-4o answer, llm-judge), plus the new ingest-code (buildout) A/B.
- **Config is hardcoded and duplicated everywhere.** Container name `menhir-lme-neo4j`,
  bolt `7689`/`7688`, pw `lmedata123`, ports `8102/8103/8105/8106`, absolute
  `/c/Users/thron/...` paths, model names — all copy-pasted across ~10 scripts.
- **No entry point.** A newcomer can't tell which of `run_longmemeval_modeb.sh`,
  `run_lme_recall_ab.sh`, `_run_lme_variant.sh`, `_lme_build_db.sh` to run for what.
- **Two valuable new tools live only in the session temp dir** (not the repo): the buildout
  A/B (`slice_ab.sh`) and the graph backup steps (run manually today).

Outcome: a self-contained `scripts/longmemeval/` package with one config file, one dispatcher,
one authoritative README, and every load-bearing script committed — so anyone can run
build → recall-ab → buildout-ab → backup from a clean checkout.

## Execution gate

**Do not start until the running buildout job (`slice_ab.sh`) finishes** — it is actively using
`_ingest_lme.py` and the harness; moving/editing those mid-run breaks frontier's arm. Also fold
in the already-made uncommitted edit to `_ingest_lme.py` (added `import os` +
`LME_NEO4J_CONTAINER`/`LME_NEO4J_PW` env params).

## Target structure

```
scripts/longmemeval/
  README.md            # single authoritative runbook (replaces README-longmemeval-modeb.md)
  lme.sh               # dispatcher: build | recall-ab | buildout-ab | backup | restore | status | retry | probe
  config.sh            # ALL ports/containers/creds/paths/models — sourced; every value env-overridable
  build_graph.sh       # <- _lme_build_db.sh          (build/extend persistent graph)
  recall_ab.sh         # <- run_lme_recall_ab.sh       (recall-only A/B on a built graph; already writes run_manifest.json)
  buildout_ab.sh       # <- (promote) slice_ab.sh      (main-ingest vs frontier-ingest, fresh graphs)
  backup_graph.sh      # <- (new) today's dump/restore steps -> neo4j-admin dump + RESTORE notes
  status.sh            # <- _lme_progress.sh           (read-only graph/queue state)
  retry.sh             # <- _lme_retry_failed.sh       (reset+drain FAILED episodes)
  lib/
    ingest.py          # <- _ingest_lme.py             (already parameterized this session)
    retry.py           # <- _retry_failed_episodes.py  (parameterize container/pw like ingest.py)
    expected.py        # <- _lme_expected.py           (expected-turn counts for status)
    recall_probe.py    # <- (promote) recall_probe.sh  (single-question recall ranking trace; the root-cause tool)
  legacy/
    run_longmemeval_modeb.sh   # old monolithic deepseek flow — kept for reference, marked DEPRECATED
```

Use `git mv` for tracked files (preserve history); `git add` for the promoted untracked/temp ones.

## Migration mapping (fate of every LME script)

| current | fate |
|---|---|
| `run_lme_recall_ab.sh` (tracked) | → `recall_ab.sh`; strip hardcodes to `config.sh` |
| `_lme_build_db.sh` (untracked) | → `build_graph.sh`; commit; use `config.sh` |
| `slice_ab.sh` (session tmp) | → `buildout_ab.sh`; commit; use `config.sh` |
| `_ingest_lme.py` (tracked, edited) | → `lib/ingest.py`; commit the pending env-param edit |
| `_retry_failed_episodes.py` (tracked) | → `lib/retry.py`; add `LME_NEO4J_CONTAINER/PW` env like ingest |
| `_lme_retry_failed.sh` (tracked) | → `retry.sh`; use `config.sh` |
| `_lme_progress.sh` (untracked) | → `status.sh`; commit |
| `_lme_expected.py` (untracked) | → `lib/expected.py`; commit |
| `recall_probe.sh` (session tmp) | → `lib/recall_probe.py`; commit (debug/trace tool) |
| backup steps (manual today) | → `backup_graph.sh` (new); `neo4j-admin dump`/`load` + RESTORE.md generator |
| `run_longmemeval_modeb.sh` (tracked) | → `legacy/`; header note: superseded by build_graph + recall_ab |
| `_run_lme_variant.sh` (untracked) | archive/drop — superseded by `recall_ab.sh` + `buildout_ab.sh` |
| `_overnight_ab.py` (untracked) | archive/drop — one-off; capability now in `buildout_ab.sh` |
| session tmp: `endgame.sh`,`watchdog.sh`,`fair_ab.sh`,`regen_fair.sh` | do NOT promote — one-off orchestration; their durable ideas live in the README (drain/monitor, resume) |

## config.sh (centralize — every value `${VAR:-default}` so it's overridable)

- **Neo4j**: `LME_NEO4J_NAME=menhir-lme-neo4j`, `LME_BOLT=7689`, `LME_HTTP=7476`,
  `LME_NEO4J_PW=lmedata123`, `LME_NEO4J_VOL=menhir-lme-data`, `LME_NEO4J_IMAGE=neo4j:5.26-community`
- **menhir ports**: `LME_PORT_BUILD=8102`, `LME_PORT_RECALL=8103`, `LME_PORT_BUILDOUT_MAIN=8105`,
  `LME_PORT_BUILDOUT_FRONTIER=8106`
- **paths**: `ARCH_DIR`, `BENCH_DIR`, `MENHIR_MAIN`, `MENHIR_FRONTIER`, venv bins — derive from the
  script's own location where possible (`$(git rev-parse --show-toplevel)` / `../..`), not absolute
- **models**: `LME_EXTRACT_MODEL=gpt-4.1-nano`, `LME_EMBED_MODEL=text-embedding-3-small`,
  `LME_ANSWER_MODEL=gpt-4o`, `LME_JUDGE_MODEL=gpt-4o-mini`, `LME_SCORER=llm-judge`
- **dataset/run**: `LONGMEMEVAL_VARIANT=oracle`, `LME_DATASET=xiaowu0162/longmemeval`, `LME_LIMIT=30`
- **backup**: `LME_BACKUP_DIR=C:/Users/thron/menhir-lme-backup`
- **key sources** (documented, read at runtime, never committed): OpenAI ← `menhir/.env:OPENAI_API_KEY`

## lme.sh dispatcher

`lme.sh <command> [args]` sources `config.sh`, then routes:
- `build [N]` → build_graph.sh (persistent graph, default N=30)
- `recall-ab <branch|path> [N]` → recall_ab.sh
- `buildout-ab [N]` → buildout_ab.sh (main vs frontier)
- `backup` / `restore` → backup_graph.sh
- `status` → status.sh
- `retry` → retry.sh
- `probe <question_id>` → lib/recall_probe.py (recall ranking trace)
- no/`-h` arg → usage from a single help string

## README.md (the runbook — replaces the stale one)

Sections: **What this measures** (recall-only vs buildout A/B, and what each can/can't see —
recall-only on a shared graph is blind to ingest-code changes); **Prereqs** (docker, bench venv +
`[longmemeval]` extra, menhir venv, OpenAI key, HF dataset); **Quickstart** (the 4 `lme.sh` commands);
**Graph lifecycle** (build → backup/restore → recall-ab/buildout-ab, never reset a built graph);
**The run_manifest.json contract** (reproducibility record we added); **Config reference** (the
`config.sh` table); **Interpreting results** (llm-judge vs containment; N=30 is noise; the recall-
ranking bottleneck from the root-cause trace); **Troubleshooting** (per-branch venv guard, the
`LONGMEMEVAL_VARIANT=oracle` gotcha, `include_session=True`, disk space for dumps).

## .agent updates
- `.agent/README.md`: add a pointer to `scripts/longmemeval/README.md` under benchmarks.
- `.agent/CHANGELOG.md`: one line — LME framework consolidated into `scripts/longmemeval/`.

## Verification (end-to-end, cheap)
1. `bash scripts/longmemeval/lme.sh -h` prints usage.
2. `bash scripts/longmemeval/lme.sh status` reports the existing graph (READY≈10924) — proves
   config + status wiring against the live container.
3. `bash scripts/longmemeval/lme.sh recall-ab main 2` runs a 2-question recall A/B against the
   backed-up graph and writes `run_manifest.json` — proves config, serve, harness, manifest.
4. `git status` shows the promoted scripts staged; `git grep -n 7689 scripts/longmemeval` returns
   only `config.sh` (no leaked hardcodes).
5. Commit: `refactor(lme): consolidate LongMemEval framework into scripts/longmemeval/ (config,
   dispatcher, runbook)`.

## Out of scope (note in README as future work)
- Full cross-platform portability (scripts assume Git Bash on Windows + Docker Desktop).
- Making recall `top_k` / `preset` configurable from the launcher (the ranking bottleneck the
  trace exposed) — that is a menhir/harness change, tracked separately, not this reorg.
