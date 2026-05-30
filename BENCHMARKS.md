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
MCP token-waste reduction before vs after archolith-rtk filtering.
Fixtures derived from live session telemetry (2,322 MCP results, 2.49M chars)
with projected filter savings applied per-server category.

Source: `fixtures/audit_before.json` → `fixtures/audit_after.json`

| Server | Before | After | Change | Pct | Status |
|--------|--------|-------|--------|-----|--------|
| gradle | 32,500 | 19,500 | -13,000 | -40.0% | improved |
| harness | 20,300 | 5,100 | -15,200 | -74.9% | improved |
| memory | 28,400 | 7,100 | -21,300 | -75.0% | improved |
| vps | 50,200 | 12,600 | -37,600 | -74.9% | improved |
| workspace-artifacts | 211,400 | 148,000 | -63,400 | -30.0% | improved |
| **Total** | **342,800** | **192,300** | **-150,500** | **-43.9%** | - |

**Token reduction:** 150,500 (43.9%). **Waste reduction:** 83,500 (71.5%).

## Stack Suite (Four-Way Comparison)
*Pending live-proxy run. Run `archolith-bench stack --all` to generate.*
