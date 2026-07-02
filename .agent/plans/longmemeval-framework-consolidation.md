# Plan: Organize the LongMemEval testing framework in archolith-bench

Status: READY TO EXECUTE — all gating jobs finished (2026-07-02). Execute in the worktree
`C:/wt/lme-reorg` on branch `lme-framework-reorg`. See the **2026-07-02 UPDATE** at the bottom
for what this session added (analysis harnesses, committed knobs, stratification) — the update
supersedes the original where they differ.

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
- (DONE this session) Recall `top_k` is now launcher-configurable via `LME_RECALL_LIMIT`
  (committed `6cacfa7`, `run_memory_ab`). `preset` remains a future menhir/harness change.

---

## 2026-07-02 UPDATE — supersedes the above where they differ

**Gate cleared.** The buildout job, the answer-accuracy matrix, the MSC sweep, and the oracle
ablation have all finished. Nothing is using `_ingest_lme.py` or the harness. Safe to `git mv`.

**Already done since the original plan was written (do NOT redo — just integrate):**
- One-off scripts are now **committed** (`a64d78d`): `_lme_build_db.sh`, `_lme_progress.sh`,
  `_lme_expected.py`, `_run_lme_variant.sh`, `_overnight_ab.py`, `_lme_retry_failed.sh`. So use
  `git mv` for ALL of them (history preserved) — the original plan marked several "untracked".
- `_ingest_lme.py` env-param edit and `menhir_client.py` source-label: already committed (`51f8abb`).
- `LME_RECALL_LIMIT` env knob in `run_memory_ab`: committed (`6cacfa7`).

**NEW capability layer to promote — the analysis harnesses (this session's real product).**
The framework is no longer just build/recall-ab/buildout-ab; it now has a measurement+analysis
tier that produced the campaign findings. These live in the job tmp dir
`C:/Users/thron/.claude/jobs/a039ffc7/tmp/` and must be promoted into `scripts/longmemeval/`:

| session-tmp artifact | → promote to | what it does |
|---|---|---|
| `answer_matrix.sh` | `analysis/answer_matrix.sh` | config × question-type answer-accuracy grid (llm-judge) |
| `msc_sweep.sh` | `analysis/msc_sweep.sh` | minimal-sufficient-context: accuracy vs recall top-k (uses `LME_RECALL_LIMIT`) |
| `ablation_sweep.sh` | `analysis/ablation_sweep.sh` | per-oracle add-one-in ablation → the routing table |
| `retrieval_quality.py` | `analysis/lib/retrieval_quality.py` | deterministic gold+support presence, menhir vs graphiti-native (no answer-model spend) |

All four hardcode the same config (bolt 7689, pw, ports 8109–8114, absolute paths, model names)
— **strip to `config.sh`** exactly like the runbook scripts. Add `config.sh` values they need:
`LME_ANSWER_MODEL`, `LME_JUDGE_MODEL`, `LME_PER_TYPE` (stratified sample size), and the analysis
port block (`LME_PORT_MATRIX`, `LME_PORT_MSC`, `LME_PORT_ABL`, `LME_PORT_RQ`).

**Dispatcher gains analysis verbs** (`lme.sh`):
- `matrix [per_type]` → analysis/answer_matrix.sh
- `msc <config>` → analysis/msc_sweep.sh
- `ablation` → analysis/ablation_sweep.sh
- `presence` → analysis/lib/retrieval_quality.py (gold+support presence)

**STRATIFICATION is mandatory — the load-bearing lesson.** `--limit N` alone takes the first N
oracle items, which are **100% temporal-reasoning** (the file is grouped by type). Every fair
run MUST sweep all 6 `question_type`s via `--subset` (temporal-reasoning, multi-session,
knowledge-update, single-session-user, single-session-assistant, single-session-preference),
`LME_PER_TYPE` each. The analysis harnesses already loop `--subset`; the README must warn that
bare `--limit` is a **sampling trap** and document the 6 types.

**config.sh corrections from this session's reality:**
- Graph holds the full **500** oracle namespaces (`lme-<question_id>`), not ~10.9k episodic
  nodes for one slice — verification step 2's "READY≈10924" is stale; use "500 namespaces".
- Persistent graph creds/host confirmed: `menhir-lme-neo4j`, bolt 7689, http 7476, pw `lmedata123`.
- Answer/judge models actually used: `LME_ANSWER_MODEL=gpt-4o`, `LME_JUDGE_MODEL=gpt-4o-mini`.

**README additions (Interpreting results):**
- The stratification trap (above) — non-negotiable.
- N=15/cell is ±~0.13 noise; report per-type, not just an average; cross-run reproducibility
  is good (node-plain hit 0.367 on three independent runs).
- The campaign's headline findings belong in a short "What we learned" box: node-only is the
  strongest config (0.367); the frontier `EvidenceAnchorWarden` under `warden_gate` zeroes the
  score on anecdotal (0.000) while every other oracle is score-neutral; MSC plateaus at k=5
  (~400 tok = 95% of ceiling) ⇒ bottleneck is brief-construction, not retrieval.
- Cross-reference the menhir-frontier plan `anecdotal-recall-oracle-ladder.md` (the oracle-router
  + BriefBuilder roadmap those measurements feed).

**Do NOT promote** (one-off orchestration, stays in job tmp): `rung_a.sh`, `rung_b_3arm.sh`,
`rung_c_gated.sh`, `edge_recall_probe*.sh`, `oracle_packet_dump.py`, `edge_search_proof.py`,
`frontier_trace_probe.sh`. Their durable ideas already live in the promoted harnesses + READMEs.

**Scope discipline for the handoff:** this is a **reorg only** — move/rename/de-hardcode/document.
Do NOT change harness logic or menhir code. The one allowed code touch is stripping hardcoded
config into `config.sh`. Verify with the cheap end-to-end steps (§Verification) using
`LME_PER_TYPE=1` so it's a 2-minute smoke test, not a full run.
