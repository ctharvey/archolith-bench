# archolith-bench — Benchmark Results
Generated: 2026-05-30 06:15 UTC
## Filter Suite (archolith-rtk)
Token-savings compression ratio measured on real tool-output corpora extracted from
live Claude Code agent sessions (git diffs, grep results, file reads, MCP JSON, etc.).
| Category | Samples | Raw Tokens | Filtered | Savings |
|----------|---------|------------|----------|--------|
| git_diff | 2 | 4,566 | 1,826 | 60.0% |
| git_log | 1 | 580 | 580 | 0.0% |
| git_status | 1 | 774 | 774 | 0.0% |
| json | 1 | 2,078 | 59 | 97.2% |
| logs | 2 | 977 | 835 | 14.5% |
| read_file | 1 | 1,296 | 568 | 56.2% |
| search | 2 | 5,588 | 2,755 | 50.7% |
| test | 2 | 1,851 | 1,542 | 16.7% |
| **Total** | **12** | **17,710** | **8,939** | **49.5%** |

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

---

## Reproduction

### Prerequisites

- Python 3.11+
- Running archolith-context proxy (port 9801) with DeepSeek upstream
- `archolith-rtk` and `archolith-audit` packages installed

### Setup

```bash
git clone <repo-url> && cd archolith-bench
python -m venv .venv && .venv/Scripts/activate  # or source .venv/bin/activate
pip install -e .
cp .env.example .env   # set UPSTREAM_API_KEY, PROXY_BASE_URL
```

### Run suites

```bash
# Filter suite — measures RTK compression on tool-output corpora
archolith-bench filter

# Proxy suite — multi-turn benchmark against live proxy
#   Requires proxy running at PROXY_BASE_URL (default http://localhost:9801/v1)
archolith-bench proxy --scenario scenarios/code_review.json \
    --arms proxy_only proxy_plus_filter \
    --budgets 4000 15000

# Audit suite — MCP token-waste before/after comparison
archolith-bench audit --before fixtures/audit_before.json \
    --after fixtures/audit_after.json

# Report — regenerate BENCHMARKS.md from results/
archolith-bench report
```

### Notes

- Proxy suite runs are **not deterministic** — LLM responses vary between runs.
  Token savings (58-59%) are stable; recall metrics vary ±15%.
- Filter suite is deterministic given the same corpus files.
- Budget parameter controls `context_token_budget` via proxy admin API.
- Cold start defaults: `cold_start_token_threshold=5000`, `cold_start_turns=2`.
