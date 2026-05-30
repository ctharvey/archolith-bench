# archolith-bench — Benchmark Results
Generated: 2026-05-30 05:43 UTC
## Filter Suite (archolith-rtk)
Token-savings compression ratio measured on real tool-output corpora.
| Category | Samples | Raw Tokens | Filtered | Savings |
|----------|---------|------------|----------|--------|
| generic | 2 | 937 | 953 | -1.7% |
| git_diff | 1 | 1,413 | 500 | 64.6% |
| read_file | 1 | 606 | 307 | 49.3% |
| search | 1 | 227 | 227 | 0.0% |
| test | 1 | 421 | 421 | 0.0% |
| **Total** | 6 | 3,604 | 2,408 | **33.2%** |

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
