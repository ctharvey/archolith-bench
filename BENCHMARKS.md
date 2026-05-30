# archolith-bench — Benchmark Results
Generated: 2026-05-30 01:52 UTC
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
*Pending live-proxy run. Run `archolith-bench proxy --all --arms direct,proxy_plus_filter` to generate.*

## Audit Suite (archolith-audit)
MCP token-waste reduction before vs after.
| Server | Before | After | Change | Pct | Status |
|--------|--------|-------|--------|-----|--------|
| gradle | 18,500 | 8,200 | -10,300 | -55.7% | improved |
| home | 4,800 | 4,200 | -600 | -12.5% | no_change |
| memory | 32,000 | 14,000 | -18,000 | -56.2% | improved |
| vps | 9,200 | 6,100 | -3,100 | -33.7% | improved |
| **Total** | 64,500 | 32,500 | +32,000 | +49.6% | - |

**Token reduction:** 32,000 (49.6%). **Waste reduction:** 21,500 (83.0%).

## Stack Suite (Four-Way Comparison)
*Pending live-proxy run. Run `archolith-bench stack --all` to generate.*
