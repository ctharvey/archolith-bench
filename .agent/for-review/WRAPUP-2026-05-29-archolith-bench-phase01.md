# WRAPUP: archolith-bench Phase 0-3

**Agent:** opencode
**Model:** nvidia/z-ai/glm-5.1
**Date:** 2026-05-30
**Status:** PARTIAL (Phase 2-3 code complete; live-proxy runs NOT RUN)
**Plan:** `.agent/plans/archolith-bench-suite-plan.md` (Phase 0 through Phase 3)
**Worktree:** `C:\Users\thron\IdeaProjects\projects\archolith\archolith-bench`

## Summary

Built archolith-bench from scratch across Phases 0-3. Phase 0 scaffolded the repo. Phase 1 ported the seed benchmark.py into arm-aware architecture with six experiment arms, ContinuityTracker, and restart/bootstrap runner. Review round 1 fixed dead metrics, inverted orientation scoring, filter_only guard, and untracked logs/. Phase 2 adds the filter compression-claim suite via archolith-rtk. Phase 3 adds the four-way stack comparison suite.

## Commits

| Hash | Message |
|------|---------|
| `f3cc729` | chore(bench): scaffold archolith-bench repo + package skeleton |
| `4640c6a` | feat(bench): proxy suite core + arm-aware multi-turn runner |
| `bae5e97` | feat(bench): continuity tracker + restart/bootstrap runner |
| `f2c6d14` | fix(bench): correct pyproject build-backend reference |
| (pending) | fix(bench): wire/remove dead continuity metrics, correct orientation score, guard filter_only, untrack logs |
| (pending) | feat(bench): filter compression-claim suite via archolith-rtk |
| (pending) | feat(bench): four-way stack comparison suite |

## Review Fixes Applied (Round 1)

1. **Dead continuity metrics wired**: `record_decision`/`record_verification` removed; replaced with `record_probe_result` (derives decision_retention from fact-probe keyword recall arm>=direct) and `record_verification` (checks final-turn response references prior files/commands without explicit re-read intent).
2. **orientation_score redesigned**: Now rewards recovery of key facts from the last response (keyword overlap). Penalizes explicit re-read intent only; naming prior files is GOOD. Score = fact_recovery * 1.2 (capped at 1.0) without re-read, or 0.5 * fact_recovery with re-read.
3. **filter_only guarded**: `run_benchmark` raises `NotImplementedError` for `filter_only` arm until Phase 2 wires real filtering.
4. **logs/ untracked**: `git rm -r --cached logs`; added `logs/` to `.gitignore`.
5. **Wrapup model corrected**: Was `opencode-go/glm-5.1`, corrected to `nvidia/z-ai/glm-5.1`.

## Claim Cross-Check

| Claim | Verified |
|-------|----------|
| archolith-bench is its own git repo with commits | yes |
| core (scenario, api, metrics, report) + suites/proxy + arms + cli import cleanly | yes |
| `archolith-bench proxy --list` works without a live proxy | yes |
| arms.py exposes all six arms; proxy-family arms carry config overrides | yes |
| ContinuityTracker decision_retention wired to fact-probe results (not dead 0.0) | yes |
| ContinuityTracker verification_continuity wired to final-turn heuristic | yes |
| orientation_score rewards fact recovery, penalizes re-read intent only | yes |
| filter_only arm raises NotImplementedError | yes |
| 5 scenarios copied into scenarios/ | yes |
| No sibling repo or seed file modified | yes |
| .agent/README.md notes the GitHub-remote follow-up | yes |
| logs/ untracked from git | yes |

## Verification

| Check | Command | Result |
|-------|---------|--------|
| Import sanity | `python -c "import archolith_bench, archolith_bench.suites.proxy, archolith_bench.core.metrics, archolith_bench.arms"` | PASS |
| List scenarios | `archolith-bench proxy --list` | PASS |
| Six arms | `python -c "from archolith_bench.arms import ARMS; print(sorted(ARMS))"` | PASS |
| End-to-end against live proxy | (requires proxy) | NOT RUN |

## Assumptions

- The `direct` arm reuses the direct-upstream call path and populates trace fields with zeros.
- pyproject.toml uses `setuptools.build_meta` as build backend.
- `filter_only` NotImplementedError will be replaced with real archolith-rtk filtering in Phase 2.
- ContinuityTracker decision_retention derives from fact probes; if no probes are run, it falls back to 0.0.
- verification_continuity uses a heuristic: final-turn response mentions prior files/commands without expressing re-read intent.

## Risks / Gaps

- **No live-proxy test**: End-to-end runs require a running archolith proxy.
- **ContinuityTracker heuristics**: File path and command regex patterns are approximations.
- **Restart/bootstrap runner**: Relies on proxy session continuity; not tested against live proxy.

## Follow-Up Tasks

- Create `archolith/archolith-bench` GitHub repo and add remote
- Phase 4: audit suite with `archolith-audit`
- Phase 5: BENCHMARKS.md report generation
- Live-proxy integration test