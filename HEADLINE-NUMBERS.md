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

6. **Industry benchmark candidates are not headline numbers.** The industry matrix
   records trusted benchmark families and launch gates. A `candidate-before-launch`
   entry is not evidence until a tracked result artifact exists under `benchmarks/`.

---

## Current Verified Numbers

### Proxy — upstream input reduction
| Stat | Value | Source | Commit | Run date | Notes |
|------|-------|--------|--------|----------|-------|
| Proxy upstream input reduction (proxy_only, 15K budget) | **25.8%** | `archolith-bench proxy` — code_review scenario; `benchmarks/proxy-code-review-2026-05-30.md` | `5112334` | 2026-05-30 | Direct input 108,516 → arm input 80,520; public launch copy should use actual upstream input delta |
| Proxy upstream input reduction (proxy_only, 4K budget) | **15.5%** | Same run; `benchmarks/proxy-code-review-2026-05-30.md` | `5112334` | 2026-05-30 | Direct input 108,516 → arm input 91,701 |
| Proxy + filter upstream input reduction (15K budget) | **-2.4%** | Same run; `benchmarks/proxy-code-review-2026-05-30.md` | `5112334` | 2026-05-30 | Direct input 108,376 → arm input 111,021; not a positive launch claim |

### Proxy — internal context curation
| Stat | Value | Source | Commit | Run date | Notes |
|------|-------|--------|--------|----------|-------|
| Internal context-curation savings (proxy_only, 15K budget) | **58.6%** | `archolith-bench proxy` — code_review scenario | `5112334` | 2026-05-30 | Historical benchmark summary value; do not label as upstream token savings |
| Internal context-curation savings (proxy_only, 4K budget) | **58.6%** | Same run | `5112334` | 2026-05-30 | Historical benchmark summary value; needs refreshed methodology before launch |

### Proxy — launch TODO

- Refresh proxy benchmarks before launch against the current proxy configuration.
- Cover at least `proxy_only` and `proxy_plus_filter`, 4K and 15K budgets, and the current launch model.
- Publish actual upstream input deltas separately from any internal context-curation metric.

### Filter — compression
| Stat | Value | Source | Commit | Run date | Notes |
|------|-------|--------|--------|----------|-------|
| Filter aggregate compression | **49.5%** | `archolith-bench filter` — 12 real tool-output samples; `benchmarks/filter-2026-05-30.md` | `5112334` | 2026-05-30 | Total row in Filter Suite table |

### Audit — waste reduction
| Stat | Value | Source | Commit | Run date | Notes |
|------|-------|--------|--------|----------|-------|
| MCP waste reduction | **71.5%** | `archolith-bench audit` — fixture data; `benchmarks/audit-fixture-2026-06-06.md` | `18057ca` | 2026-05-30 | `[FIXTURE — not for copy until live audit run confirms]` Waste tokens reduced 83,500 of 116,700 waste tokens identified |

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

# Industry coverage matrix — claim gates, not numeric results
archolith-bench industry --launch-only --out benchmarks/industry-trusted-benchmark-coverage.md
```

After each run, paste the updated result rows into the tables above and note the commit.
