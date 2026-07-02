# Handoff — LongMemEval framework consolidation (2026-07-02)

For a reviewer or fresh-context session picking up the LME framework reorg. Everything below is
**committed and pushed** on `claude/menhir-chain-handoff-doc-7iuat2` (both the reorg's own branch
`lme-framework-reorg` and the working branch it fast-forward-merged into). Repo:
`ctharvey/archolith-bench`.

## TL;DR

The LongMemEval (LME) Mode-B testing capability had grown organically across sessions into ~15
scripts with **hardcoded config duplicated everywhere**, several **load-bearing scripts
uncommitted**, a **stale README**, and **no entry point**. This reorg consolidates all of it into a
self-contained `scripts/longmemeval/` package: one `config.sh`, one `lme.sh` dispatcher, one
authoritative `README.md`, every script committed, zero hardcoded config outside `config.sh`.

**Scope was reorg-only**: move / rename / de-hardcode / document. No harness logic or menhir code
changed. The single allowed code touch was lifting hardcoded values into `config.sh`.

## What to read first
1. This doc.
2. The plan (the contract this executed against): `.agent/plans/longmemeval-framework-consolidation.md`
   — especially the **2026-07-02 UPDATE** section, which supersedes the original where they differ.
3. The new runbook: `scripts/longmemeval/README.md`.
4. Companion menhir-frontier plan (why the analysis harnesses exist / what they found):
   `menhir-frontier/.agent/plans/anecdotal-recall-oracle-ladder.md`.

## Commits (in order on the branch)
| commit | what |
|---|---|
| `a64d78d` | committed the previously-untracked one-off LME scripts **first**, so the later `git mv` preserves history |
| `6cacfa7` | `LME_RECALL_LIMIT` env knob in `run_memory_ab` (enables the MSC sweep; the only pre-reorg code change) |
| `66fcd9f` | updated the consolidation plan with the 2026-07-02 analysis layer |
| `3b67ca0` | the reorg: `git mv` moves (R100 renames) + new files (dispatcher, config, README, analysis harnesses) |
| `d474345` | de-hardcoding into `config.sh` + `.agent` doc updates |

## Final structure
```
scripts/longmemeval/
  README.md            authoritative runbook (stratification rules, config ref, interpretation, troubleshooting)
  lme.sh               dispatcher: build | recall-ab | buildout-ab | backup | status | retry | matrix | msc | ablation | presence | probe
  config.sh            ALL ports/containers/creds/paths/models as ${VAR:-default} (env-overridable)
  build_graph.sh       build/extend the persistent LME graph        (<- _lme_build_db.sh)
  recall_ab.sh         recall-only A/B on a built graph             (<- run_lme_recall_ab.sh)
  buildout_ab.sh       ingest-code A/B, fresh graphs                (<- session tmp slice_ab.sh)
  backup_graph.sh      neo4j dump/restore                          (new)
  status.sh            read-only graph/queue state                 (<- _lme_progress.sh)
  retry.sh             reset+drain FAILED episodes                 (<- _lme_retry_failed.sh)
  lib/
    ingest.py          resumable LME ingest, env-parameterized     (<- _ingest_lme.py)
    retry.py           FAILED-episode re-enrichment                (<- _retry_failed_episodes.py)
    expected.py        expected-turn counts                        (<- _lme_expected.py)
    recall_probe.sh    single-question recall ranking trace        (<- session tmp recall_probe.sh)
  analysis/            NEW measurement tier (this session's product)
    answer_matrix.sh   accuracy × config × question-type grid
    msc_sweep.sh       minimal-sufficient-context: accuracy vs recall top-k (uses LME_RECALL_LIMIT)
    ablation_sweep.sh  per-oracle add-one-in ablation → routing table
    lib/retrieval_quality.py   deterministic gold+support presence, menhir vs graphiti-native
  legacy/
    run_longmemeval_modeb.sh       old deepseek monolith, DEPRECATED (kept verbatim, still hardcoded — intentional)
    README-longmemeval-modeb.md    old README, DEPRECATED
```

## How to use it (quickstart)
```bash
bash scripts/longmemeval/lme.sh -h            # usage
bash scripts/longmemeval/lme.sh status        # read-only: reports the live graph (~500 lme-* namespaces)
bash scripts/longmemeval/lme.sh recall-ab <branch|path> [N]
bash scripts/longmemeval/lme.sh matrix [per_type]     # answer-accuracy grid across all 6 question types
```
All config is overridable via env (see `config.sh`); nothing is hardcoded in the scripts. OpenAI key
is read at runtime from `menhir/.env`, never committed.

## ⚠️ The one load-bearing gotcha the README documents (STRATIFICATION)
`--limit N` alone takes the first N oracle items, which are **100% `temporal-reasoning`** (the
dataset file is grouped by type). Every fair run MUST sweep all 6 `question_type`s via `--subset`
(temporal-reasoning, multi-session, knowledge-update, single-session-user, single-session-assistant,
single-session-preference). The analysis harnesses already loop `--subset`; bare `--limit` is a
sampling trap. This lesson cost a chunk of a session — it is the single most important thing a
newcomer must know.

## Verification performed (all FREE — no OpenAI spend), against the COMMITTED tree
1. `lme.sh -h` prints usage. ✓
2. `lme.sh status` → `episodes=21884 ready=10924 ... active_ns=500` (live graph reachable, config wired). ✓
3. `git grep 7689 / lmedata123 / /c/Users/thron` in `scripts/longmemeval/**/*.sh` → **only** `config.sh`
   (plus README docs and the intentionally-untouched `legacy/`). ✓
4. `bash -n` all shell scripts, `python -m py_compile` all Python → pass. ✓
Not run (costs money): any real `recall-ab` / `matrix` / `msc` / `ablation`.

## Reviewer note — a defect that was caught and fixed
The reorg was executed by a subagent. Its completion report claimed commit `3b67ca0` contained the
de-hardcoding, but that commit held **only** the `git mv` moves — the de-hardcode edits were left
**uncommitted** in the worktree. Its own verification passed because it ran against the live working
tree, not the commit. Reviewed the uncommitted diff (clean, de-hardcode-only, no logic change) and
committed it as `d474345`. **If reviewing commit-by-commit, `3b67ca0` alone still shows hardcodes;
the pair `3b67ca0`+`d474345` is the complete unit.**

## Out of scope / future work (noted in README)
- Cross-platform portability (scripts assume Git Bash on Windows + Docker Desktop).
- `preset` configurability from the launcher (a menhir/harness change, not this reorg).
- The one-off orchestration scripts (`rung_*.sh`, `edge_*probe.sh`, `oracle_packet_dump.py`, …) were
  **deliberately not promoted** — their durable ideas live in the promoted harnesses + README.

## Provenance / accuracy note
`status.sh` output shows `ready=10924` — that is the READY episodic-node count for the currently-built
slice, not the namespace count. The graph holds **500** `lme-*` namespaces (full oracle set). The
plan's original "READY≈10924" verification hint was updated to "500 namespaces".
