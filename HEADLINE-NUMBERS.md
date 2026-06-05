# Headline Numbers — archolith

This file is the canonical source of truth for any statistic used in marketing copy,
README headlines, or the archolith.dev site.

## Rules (enforced for all agents and contributors)

1. **Every number here must have a source.** Suite, script, commit hash, run date,
   and a one-line methodology note. No number without all four.

2. **Fixture/sample data is not a headline number.** Numbers from bundled `fixtures/`
   inputs may demonstrate report format but MUST NOT appear on archolith.dev or in
   README headline tables. Mark fixture-derived numbers `[FIXTURE — not for copy]`.

3. **Update this file when a benchmark run produces a new result.** Run the relevant
   suite, note the commit, paste the output row here. Do not leave this file stale.

4. **Before writing any number into marketing copy**, check this file. If the number
   isn't here, it isn't verified. Do not invent or estimate — run the benchmark.

5. **If a number changes**, update archolith.dev and all README headline tables in the
   same commit. Stale copy is worse than no copy.

---

## Current Verified Numbers

### Proxy — token savings
| Stat | Value | Source | Commit | Run date | Notes |
|------|-------|--------|--------|----------|-------|
| Proxy token savings (proxy_only, 15K budget) | **58.6%** | `archolith-bench proxy` — code_review scenario | `5112334` | 2026-05-30 | Savings column in Proxy Suite table; Direct In 108,516 → curated context |
| Proxy token savings (proxy_only, 4K budget) | **58.6%** | Same run | `5112334` | 2026-05-30 | Same scenario, smaller budget |

### Filter — compression
| Stat | Value | Source | Commit | Run date | Notes |
|------|-------|--------|--------|----------|-------|
| Filter aggregate compression | **49.5%** | `archolith-bench filter` — 12 real tool-output samples | `5112334` | 2026-05-30 | Total row in Filter Suite table; site rounds to 50% |

### Audit — waste reduction
| Stat | Value | Source | Commit | Run date | Notes |
|------|-------|--------|--------|----------|-------|
| MCP waste reduction | **71.5%** | `archolith-bench audit` — fixture data | `18057ca` | 2026-05-30 | `[FIXTURE — not for copy until live audit run confirms]` Waste tokens reduced 83,500 of 116,900 waste tokens identified |

---

## Numbers Removed from Copy

| Stat | Removed | Reason |
|------|---------|--------|
| 75% best single-turn savings | 2026-06-03 | No source found in any bench doc or result file |

---

## What to Run to Refresh Headlines

```bash
# Filter suite (archolith-filter compression)
archolith-bench filter --all

# Proxy suite (token savings + recall)
archolith-bench proxy --all --arms direct,proxy_only

# Audit suite — requires real before/after session logs, NOT fixtures
archolith-bench audit --before session_before.json --after session_after.json
```

After each run, paste the updated result rows into the tables above and note the commit.
