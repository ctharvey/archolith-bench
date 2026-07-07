# Headline Numbers — archolith

This file is the canonical source of truth for any statistic used in marketing copy,
README headlines, or the archolith.dev site.

## Current Status

No headline numbers are active.

Historical, fixture, and candidate benchmark outputs may remain in `benchmarks/`, `results/`,
`BENCHMARKS.md`, and `.agent/benchmark-notes/` for methodology review. They are not launch claims and
must not be copied into public material until they are refreshed against the current launch
configuration and recorded here with full provenance.

## Rules

1. Every active number here must have a source: suite or script, exact command, commit hash, run date,
   and a one-line methodology note.
2. Fixture/sample data is not a headline number. Numbers from bundled `fixtures/` may demonstrate
   report format only.
3. Candidate industry benchmark entries are not evidence until a tracked result artifact exists under
   `benchmarks/`.
4. If a number is used in README, archolith.dev, launch copy, or external material, it must appear in
   the active table below in the same commit.
5. If a number changes or is retired, update public copy in the same commit.

## Active Headline Numbers

| Product | Claim | Value | Source | Commit | Run date | Notes |
|---------|-------|-------|--------|--------|----------|-------|
| _none_ | _No active headline claims_ | _pending_ | _pending refreshed evidence_ | _pending_ | _pending_ | Historical values intentionally removed pending a current evidence run. |

## Retired / Not For Copy

| Prior stat | Removed | Reason |
|------------|---------|--------|
| Proxy upstream input reduction from the 2026-05-30 code-review run | 2026-07-07 | Historical, single-scenario evidence; needs refreshed run against current launch setup before public use. |
| Internal context-curation savings from the 2026-05-30 proxy run | 2026-07-07 | Not billed-token reduction and not current launch evidence. |
| Filter aggregate compression from the 2026-05-30 corpus run | 2026-07-07 | Historical evidence; keep as methodology reference until refreshed and reconciled with generated reports. |
| MCP waste reduction from bundled audit fixtures | 2026-07-07 | Fixture data only; not live before/after evidence. |
| 75% best single-turn savings | 2026-06-03 | No source found in any bench doc or result file. |

## Evidence Refresh Commands

```bash
# Proxy suite: token savings + continuity, current launch config
archolith-bench proxy --all --arms direct,proxy_only,proxy_plus_filter --budgets 4000,15000

# Filter suite: archolith-filter compression on launch corpus
archolith-bench filter --corpora corpora/ --format markdown

# Audit suite: requires real before/after session logs, not fixtures
archolith-bench audit --before session_before.json --after session_after.json --format markdown

# Stack suite: experimental until tracked evidence exists
archolith-bench stack --all

# Industry coverage matrix: claim gates, not numeric results
archolith-bench industry --launch-only --out benchmarks/industry-trusted-benchmark-coverage.md
```
