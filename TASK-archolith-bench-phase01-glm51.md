You are building a NEW standalone Python project: archolith-bench, a unified benchmark suite for the archolith product family. This session covers Phase 0 (scaffold) and Phase 1 (proxy suite) only.

WORKTREE FENCE: Your working directory is C:\Users\thron\IdeaProjects\projects\archolith\archolith-bench. You MAY WRITE only inside this directory. You MAY READ (read-only, never edit) these three external paths for the plan and seed material:
  - C:\Users\thron\IdeaProjects\projects\archolith\.agent\plans\archolith-bench-suite-plan.md   (THE PLAN — read this first, in full)
  - C:\Users\thron\IdeaProjects\projects\archolith\archolith-context\scripts\benchmark.py        (seed source to port)
  - C:\Users\thron\IdeaProjects\projects\archolith\archolith-context\scripts\scenarios\*.json     (5 scenario files to copy)
Do NOT edit, delete, or move anything outside your working directory. If a task seems to require changing a sibling repo, STOP and report it.

STEP 0 — Read the plan file listed above completely before writing any code. It defines the architecture, the experiment-arm matrix, the metrics schema, and the per-phase anchors. Follow it. This task text is a summary; the plan is authoritative.

=== PHASE 0: Scaffold ===
Create this structure under your working directory:
  pyproject.toml          # package name archolith-bench, package dir archolith_bench; deps: httpx, python-dotenv. Console script: archolith-bench = archolith_bench.cli:main. (Do NOT add archolith-rtk/archolith-audit deps yet — those are Phase 2+; leave a commented TODO.)
  .gitignore              # results/, __pycache__/, .env, .checkpoint_*, *.pyc
  README.md               # what archolith-bench is, the suites, quick start
  .agent/README.md        # project context: purpose, the four suites (proxy/filter/audit/stack), how to run, and a FOLLOW-UP note that the GitHub remote archolith/archolith-bench still needs creating
  archolith_bench/__init__.py
  archolith_bench/core/__init__.py
  archolith_bench/suites/__init__.py
  scenarios/              # copy the 5 .json scenarios from the seed path above
Then run: git init  (this is its own repo) and make an initial commit:  chore(bench): scaffold archolith-bench repo + package skeleton

=== PHASE 1: Proxy suite (port + refactor + new continuity work) ===
Port the seed benchmark.py (it is HTTP-only, zero import coupling) into clean modules. Map the seed line ranges (the plan lists them) into:

  archolith_bench/core/scenario.py   <- Scenario, FactProbe, from_file, list_scenarios (seed ~lines 51-80). Point SCENARIOS_DIR at the repo-root scenarios/ dir.
  archolith_bench/core/api.py        <- send_chat (keep the 429 exponential backoff exactly), _proxy_base, get_proxy_trace, set_proxy_budget, snapshot_proxy_config, estimate_tokens, estimate_messages_tokens (seed ~lines 87-216)
  archolith_bench/core/report.py     <- print_summary, save_results, cross-scenario summary (seed ~lines 646-727, 864-883)
  archolith_bench/core/metrics.py    <- dataclasses for the metric schema in the plan: token metrics, continuity metrics, quality/perf metrics
  archolith_bench/suites/proxy.py    <- run_benchmark, run_experiment, checkpoint helpers (seed ~lines 281-639), made ARM-AWARE (see below)
  archolith_bench/arms.py            <- the six-arm registry from the plan (direct, filter_only, proxy_only, proxy_plus_filter, proxy_typed_state, proxy_state_snippets). Each arm maps to a dict of proxy /admin/config overrides. This session only needs the proxy-family arms wired; filter_only can be a registered-but-noop placeholder with a TODO.
  archolith_bench/cli.py             <- argparse entrypoint: `archolith-bench proxy --scenario/--all --arms <csv> --budgets <csv> --list`. Preserve the seed's --list, --proxy, --direct, --model, --output-dir, --resume, --experiment, --config behavior.

NEW work (this is the part NOT in the seed script — the original plan's missing Step 3):
  1. ContinuityTracker (in suites/proxy.py): across a scenario run, count repeat_file_reads and repeat_diagnostics by scanning an arm's response history for re-mentions of file paths / commands first seen in earlier turns; record decision_retention and verification_continuity via checks at the final turns. Populate the metrics.py continuity dataclass.
  2. Restart/bootstrap runner: replay a scenario, then start a fresh conversation in the same proxy session and score turn_one_orientation_score (did the model recover the last blocker/next step without re-reading?).
  3. Make run_benchmark arm-aware: accept an `arm` argument; before the run, POST the arm's config overrides to the proxy /admin/config endpoint (reuse the seed's snapshot_proxy_config / config-override code path). Output PAIRED PER-ARM results, not just the seed's hardcoded proxy-vs-direct.

CONSTRAINTS:
  - Do NOT require a live proxy to import or to run `archolith-bench proxy --list`. The health check should fail FAST with a clear message only when an actual run is requested. A live end-to-end benchmark run is OUT OF SCOPE for this session (no proxy is guaranteed running).
  - Do NOT modify the seed benchmark.py or any sibling repo. You are copying/porting, not moving.
  - All files UTF-8 without BOM, ASCII-only.

VERIFY before finishing:
  - `python -c "import archolith_bench, archolith_bench.suites.proxy, archolith_bench.core.metrics, archolith_bench.arms"` imports clean
  - `archolith-bench proxy --list` (or `python -m archolith_bench.cli proxy --list`) lists the 5 scenarios WITHOUT needing a live proxy
  - `python -c "from archolith_bench.arms import ARMS; print(sorted(ARMS))"` shows all six arms

COMMITS (atomic, conventional):
  chore(bench): scaffold archolith-bench repo + package skeleton
  feat(bench): proxy suite core + arm-aware multi-turn runner
  feat(bench): continuity tracker + restart/bootstrap runner

DEFINITION OF DONE:
  [ ] archolith-bench is its own git repo with commits above
  [ ] core (scenario, api, metrics, report) + suites/proxy + arms + cli import cleanly
  [ ] `archolith-bench proxy --list` works without a live proxy
  [ ] arms.py exposes all six arms; proxy-family arms carry config overrides
  [ ] ContinuityTracker + restart/bootstrap runner implemented and wired into metrics
  [ ] 5 scenarios copied into scenarios/
  [ ] No sibling repo or seed file modified
  [ ] .agent/README.md notes the GitHub-remote follow-up

STOP CONDITIONS: If imports fail in a way you cannot resolve, if the seed file structure differs materially from the line ranges above, or if any task requires writing outside the fence — STOP and report rather than guessing or reaching outside the working directory.

When done, write a wrapup to .agent/for-review/WRAPUP-2026-05-29-archolith-bench-phase01.md summarizing what you built, the commit hashes, the verification commands you ran with their results (honest PASS/FAIL/NOT RUN), files created, and anything deferred.