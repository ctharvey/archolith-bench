# WRAPUP: archolith-bench Phase 0-3

**Agent:** opencode
**Model:** nvidia/z-ai/glm-5.1
**Date:** 2026-05-30
**Status:** PARTIAL (all code complete; live-proxy runs NOT RUN; filter-only arm now uses rtk; filter suite verified offline)
**Plan:** `.agent/plans/archolith-bench-suite-plan.md` (Phase 0 through Phase 3)
**Worktree:** `C:\Users\thron\IdeaProjects\projects\archolith\archolith-bench`

## Summary

Built archolith-bench from scratch across Phases 0-3. Phase 0 scaffolded the repo. Phase 1 ported the seed benchmark.py into arm-aware architecture with six experiment arms, ContinuityTracker, and restart/bootstrap runner. Review round 1 fixed dead metrics, inverted orientation scoring, filter_only guard, and untracked logs. Phase 2 added filter compression-claim suite via archolith-rtk with 6 corpus samples and CLI subcommand. Phase 3 added four-way stack comparison suite with table renderer. The filter_only arm now uses archolith-rtk `filter_output` to pre-compress tool results.

## Commits

| Hash | Message |
|------|---------|
| `f3cc729` | chore(bench): scaffold archolith-bench repo + package skeleton |
| `4640c6a` | feat(bench): proxy suite core + arm-aware multi-turn runner |
| `bae5e97` | feat(bench): continuity tracker + restart/bootstrap runner |
| `f2c6d14` | fix(bench): correct pyproject build-backend reference |
| `506120a` | fix(bench): wire dead continuity metrics, correct orientation score, guard filter_only, untrack logs |
| `35cf047` | feat(bench): filter compression-claim suite via archolith-rtk |
| `2d253b4` | feat(bench): four-way stack comparison suite |

## Review Fixes Applied (Round 1)

1. **Dead continuity metrics wired**: `record_decision`/`record_verification` replaced with `record_probe_result` (derives decision_retention from fact-probe keyword recall) and `record_verification` (final-turn response references prior files/commands without re-read intent).
2. **orientation_score redesigned**: Rewards recovery of key facts (keyword overlap with last response). Penalizes only explicit re-read intent. Score = fact_recovery * 1.2 cap 1.0 without re-read, or 0.5 * fact_recovery with re-read.
3. **filter_only now real**: Was guarded with NotImplementedError; now uses `apply_filter_to_history()` from suites/filter.py which calls `archolith_rtk.filter_output` on tool-result-sized messages.
4. **logs/ untracked**: `git rm -r --cached logs`; added `logs/` to `.gitignore`.
5. **Wrapup model corrected**: `nvidia/z-ai/glm-5.1`.

## Files Created/Modified

| File | Purpose | Phase |
|------|---------|-------|
| `pyproject.toml` | Package metadata, deps (httpx, python-dotenv, archolith-rtk), console script | 0,2 |
| `.gitignore` | results/, __pycache__/, .env, .checkpoint_*, *.pyc, logs/ | 0,1 |
| `README.md` | What archolith-bench is, suites, quick start, arms table | 0 |
| `.agent/README.md` | Project context, follow-up | 0 |
| `archolith_bench/__init__.py` | Package init with version | 0 |
| `archolith_bench/core/__init__.py` | Core package init | 0 |
| `archolith_bench/core/scenario.py` | Scenario, FactProbe, from_file, list_scenarios | 1 |
| `archolith_bench/core/api.py` | send_chat, proxy helpers, token estimators, health check | 1 |
| `archolith_bench/core/metrics.py` | TokenMetrics, ContinuityMetrics, QualityPerfMetrics dataclasses | 1 |
| `archolith_bench/core/report.py` | print_summary, save_results, print_cross_scenario_summary, print_four_way_table | 1,3 |
| `archolith_bench/core/corpus.py` | CorpusSample, list_corpora, load_sample, load_all_corpora | 2 |
| `archolith_bench/arms.py` | Six-arm registry with config overrides | 1 |
| `archolith_bench/suites/__init__.py` | Suites package init | 0 |
| `archolith_bench/suites/proxy.py` | run_benchmark (arm-aware), ContinuityTracker, run_restart_bootstrap, checkpoint helpers | 1 |
| `archolith_bench/suites/filter.py` | Filter suite: run_filter_sample, run_filter_suite, apply_filter_to_history | 2 |
| `archolith_bench/suites/stack.py` | Stack suite: run_stack_suite with four arms | 3 |
| `archolith_bench/cli.py` | CLI entrypoint: proxy/filter/stack subcommands | 0,2,3 |
| `scenarios/*.json` | 5 seed scenarios | 0 |
| `corpora/*.txt` | 6 corpus samples (git_diff, search_ripgrep, bracketed_logs, test_output, read_file, nested_json) | 2 |

## Verification

| Check | Command | Result |
|-------|---------|--------|
| Import sanity | `python -c "import archolith_bench, archolith_bench.suites.proxy, archolith_bench.core.metrics, archolith_bench.arms"` | PASS |
| Import filter | `python -c "from archolith_rtk import filter_output, count_tokens"` | PASS |
| List scenarios | `archolith-bench proxy --list` | PASS |
| Six arms | `python -c "from archolith_bench.arms import ARMS; print(sorted(ARMS))"` | PASS |
| Filter suite | `archolith-bench filter --corpora corpora/` | PASS -- 33.2% aggregate savings |
| Stack imports | `python -c "from archolith_bench.suites.stack import STACK_ARMS; print(STACK_ARMS)"` | PASS |
| Four-way table (canned) | `print_four_way_table(canned_data)` | PASS -- prints table with headline |
| End-to-end proxy run | Requires live proxy | NOT RUN |
| End-to-end stack run | Requires live proxy | NOT RUN |

## Claim Cross-Check

| Claim | Verified |
|-------|----------|
| archolith-bench is its own git repo with 7 commits | yes |
| core + suites + arms + cli import cleanly | yes |
| `archolith-bench proxy --list` works without a live proxy | yes |
| `archolith-bench filter --corpora corpora/` works without a live proxy | yes |
| arms.py exposes all six arms | yes |
| filter_only uses archolith-rtk filter_output (not NotImplementedError) | yes |
| ContinuityTracker decision_retention wired to fact-probe results | yes |
| orientation_score rewards fact recovery, penalizes re-read intent only | yes |
| Four-way table renderer works on canned data | yes |
| 5 scenarios in scenarios/ | yes |
| 6 corpus samples in corpora/ | yes |
| No sibling repo modified | yes |
| logs/ untracked from git | yes |

## Assumptions

- The `direct` arm reuses the direct-upstream call path with zeroed trace fields.
- The `filter_only` arm pre-filteres tool-result-sized messages via `apply_filter_to_history` before direct API call; no proxy involved.
- pyproject.toml uses `setuptools.build_meta`; archolith-rtk is listed as a dependency installed via editable local path.
- ContinuityTracker heuristics use regex for file path/command detection and keyword overlap for orientation scoring.

## Risks / Gaps

- **No live-proxy test**: proxy and stack suites need a running proxy.
- **Corpus small**: Only 6 corpus samples; the plan's Phase 2 calls for real session-log corpora which would be larger and more diverse.
- **filter_only + stack runs need live proxy**: `archolith-bench stack --all` requires proxy connectivity for proxy_only and proxy_plus_filter arms.

## What Remains

- **Phase 4**: audit suite with `archolith-audit`
- **Phase 5**: BENCHMARKS.md report generation
- **Live-proxy integration test**
- **GitHub remote** (`archolith/archolith-bench`)