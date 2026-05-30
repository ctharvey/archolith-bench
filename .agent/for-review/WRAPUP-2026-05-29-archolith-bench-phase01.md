# WRAPUP: archolith-bench Phase 0-5

**Agent:** opencode
**Model:** nvidia/z-ai/glm-5.1
**Date:** 2026-05-30
**Status:** PARTIAL (all code complete; live-proxy runs NOT RUN; filter suite verified offline; audit suite verified on fixtures)
**Plan:** `.agent/plans/archolith-bench-suite-plan.md` (Phase 0 through Phase 5)
**Worktree:** `C:\Users\thron\IdeaProjects\projects\archolith\archolith-bench`

## Summary

Built archolith-bench from scratch across Phases 0-5. Phase 0 scaffolded the repo. Phase 1 ported the seed benchmark.py into arm-aware architecture with six experiment arms, ContinuityTracker, and restart/bootstrap runner. Phase 2 added filter compression-claim suite via archolith-rtk (33.2% aggregate savings on 6 corpus samples). Phase 3 added four-way stack comparison suite. Phase 4 added audit waste-reduction suite via archolith-audit. Phase 5 added BENCHMARKS.md report generation from results/.

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
| `87b329e` | feat(bench): audit waste-reduction suite via archolith-audit |
| `1d0881b` | feat(bench): BENCHMARKS.md report generation |
| `e27ca06` | docs(bench): update wrapup for Phase 0-5 complete |

## Review Fixes Applied (Round 1)

1. **Dead continuity metrics wired**: record_probe_result derives decision_retention from fact-probe recall; record_verification checks final-turn reference to prior files/commands without re-read intent.
2. **orientation_score redesigned**: Rewards key-fact recovery (keyword overlap), penalizes only explicit re-read intent.
3. **filter_only no longer a no-op**: Now uses `apply_filter_to_history()` calling `archolith_rtk.filter_output`.
4. **logs/ untracked from git**.
5. **Wrapup model corrected**.

## Files

| File | Purpose | Phase |
|------|---------|-------|
| `pyproject.toml` | Package metadata, deps (httpx, python-dotenv, archolith-rtk, archolith-audit) | 0,2,4 |
| `.gitignore` | results/, __pycache__/, .env, .checkpoint_*, *.pyc, logs/ | 0,1 |
| `README.md` | Suites, quick start, arms table | 0 |
| `.agent/README.md` | Project context, GitHub remote follow-up | 0 |
| `archolith_bench/__init__.py` | Package init with version | 0 |
| `archolith_bench/core/scenario.py` | Scenario, FactProbe, from_file, list_scenarios | 1 |
| `archolith_bench/core/api.py` | send_chat, proxy helpers, token estimators, health check | 1 |
| `archolith_bench/core/metrics.py` | TokenMetrics, ContinuityMetrics, QualityPerfMetrics dataclasses | 1 |
| `archolith_bench/core/report.py` | print_summary, save_results, print_four_way_table, write_benchmarks_md | 1,3,5 |
| `archolith_bench/core/corpus.py` | CorpusSample, list_corpora, load_sample | 2 |
| `archolith_bench/arms.py` | Six-arm registry with config overrides | 1 |
| `archolith_bench/suites/proxy.py` | run_benchmark (arm-aware), ContinuityTracker, run_restart_bootstrap | 1 |
| `archolith_bench/suites/filter.py` | Filter suite: run_filter_sample, run_filter_suite, apply_filter_to_history | 2 |
| `archolith_bench/suites/stack.py` | Stack suite: run_stack_suite with four arms | 3 |
| `archolith_bench/suites/audit.py` | Audit suite: run_audit_comparison via archolith-audit comparator | 4 |
| `archolith_bench/cli.py` | CLI subcommands: proxy, filter, stack, audit, report | 0,2,3,4,5 |
| `scenarios/*.json` | 5 seed scenarios | 0 |
| `corpora/*.txt` | 6 corpus samples (git_diff, search_ripgrep, bracketed_logs, test_output, read_file, nested_json) | 2 |
| `fixtures/audit_before.json` | Sample before-audit report | 4 |
| `fixtures/audit_after.json` | Sample after-audit report | 4 |
| `BENCHMARKS.md` | Generated report from results/ | 5 |

## Verification

| Check | Command | Result |
|-------|---------|--------|
| Import all modules | `python -c "import archolith_bench, ...suites.filter, ...suites.audit, ...suites.stack, ...core.corpus, ...arms"` | PASS |
| List scenarios | `archolith-bench proxy --list` | PASS |
| Six arms | `python -c "from archolith_bench.arms import ARMS; print(sorted(ARMS))"` | PASS |
| Filter suite | `archolith-bench filter --corpora corpora/` | PASS -- 33.2% aggregate |
| Audit on fixtures | `archolith-bench audit --before fixtures/audit_before.json --after fixtures/audit_after.json` | PASS -- 49.6% token reduction, 83.0% waste reduction |
| Report generation | `archolith-bench report --out BENCHMARKS.md` | PASS -- writes BENCHMARKS.md with filter/audit/proxy/stack sections |
| Stack smoke (canned) | `print_four_way_table(canned_data)` | PASS -- four-way table + headline |
| 5 CLI subcommands | `archolith-bench --help` | PASS -- proxy, filter, stack, audit, report |
| Proxy live run | Requires live proxy | NOT RUN |
| Stack live run | Requires live proxy | NOT RUN |

## Claim Cross-Check

| Claim | Verified |
|-------|----------|
| archolith-bench is its own repo with 10 commits | yes |
| All modules import cleanly | yes |
| proxy --list works without proxy | yes |
| filter --corpora works without proxy | yes |
| audit --before/--after works on fixture JSON | yes |
| report --out writes BENCHMARKS.md | yes |
| 5 CLI subcommands parse | yes |
| filter_only arm uses archolith-rtk (not NotImplementedError) | yes |
| ContinuityTracker decision_retention wired to probes | yes |
| orientation_score rewards fact recovery | yes |
| Four-way table renders | yes |
| 5 scenarios in scenarios/ | yes |
| 6 corpus samples in corpora/ | yes |
| No sibling repo modified | yes |
| logs/ untracked | yes |

## What Remains

- **Live-proxy runs**: proxy and stack suites need a running archolith proxy to produce real numbers. BENCHMARKS.md proxy/stack sections are labeled "pending live-proxy run."
- **Representative corpus expansion**: Current 6-corpus filter result (33.2%) is below the product claim range (36-57%). More representative corpora would bring the number into range.
- **GitHub remote creation**: `archolith/archolith-bench` repo needs creating on GitHub.
- **Phase 6 (DEFERRED)**: Supervised LLM-judge quality eval (`judge.py` stub).