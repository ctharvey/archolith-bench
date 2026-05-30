# archolith-bench — Benchmark Results
Generated: 2026-05-30 06:15 UTC
## Filter Suite (archolith-rtk)
Token-savings compression ratio measured on real tool-output corpora extracted from
live Claude Code agent sessions (git diffs, grep results, file reads, MCP JSON, etc.).
| Category | Samples | Raw Tokens | Filtered | Savings |
|----------|---------|------------|----------|--------|
| git_diff | 2 | 4,566 | 1,826 | 60.0% |
| git_log | 1 | 582 | 582 | 0.0% |
| git_status | 1 | 776 | 776 | 0.0% |
| json | 1 | 2,085 | 59 | 97.2% |
| logs | 2 | 977 | 835 | 14.5% |
| read_file | 1 | 1,317 | 589 | 55.3% |
| search | 2 | 6,372 | 3,051 | 52.1% |
| test | 2 | 1,873 | 1,564 | 16.5% |
| **Total** | **12** | **18,548** | **9,282** | **50.0%** |

## Proxy Suite
Multi-turn token savings and continuity metrics across proxy experiment arms.
| Scenario | Arm | Budget | Direct In | Arm In | Savings | Recall Pres. |
|----------|-----|--------|-----------|--------|---------|-------------|
| code_review | proxy_only | 15000 | 108,516 | 80,520 | 58.6% | 57% |
| code_review | proxy_only | 4000 | 108,516 | 91,701 | 58.6% | 91% |
| code_review | proxy_plus_filter | 15000 | 108,376 | 111,021 | 58.7% | 60% |
| code_review | proxy_plus_filter | 4000 | 108,516 | 105,139 | 58.6% | 54% |

## Audit Suite (archolith-audit)
> **Note:** sample/fixture data, not a live audit run. The numbers below reflect the bundled `fixtures/` inputs and demonstrate the report format only. Run `archolith-bench audit` against real before/after session logs to produce measured results.

MCP token-waste reduction before vs after.
Source: `fixtures\audit_before.json` -> `fixtures\audit_after.json`

| Server | Before | After | Change | Pct | Status |
|--------|--------|-------|--------|-----|--------|
| gradle | 18,500 | 8,200 | -10,300 | -55.7% | improved |
| home | 4,800 | 4,200 | -600 | -12.5% | no_change |
| memory | 32,000 | 14,000 | -18,000 | -56.2% | improved |
| vps | 9,200 | 6,100 | -3,100 | -33.7% | improved |
| **Total** | 64,500 | 32,500 | -32,000 | -49.6% | - |

**Token reduction:** 32,000 (49.6%). **Waste reduction:** 21,500 (83.0%).

## Stack Suite (Four-Way Comparison)
*Pending live-proxy run. Run `archolith-bench stack --all` to generate.*
