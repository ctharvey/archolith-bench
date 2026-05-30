# archolith-bench — Project Context

## Purpose
Unified benchmark suite for the archolith product family. Measures token savings, continuity, compression, and cross-product metrics across proxy, filter, audit, and stack scenarios.

## Suites
- **proxy** (Phase 1, critical path for June 30 launch): Multi-turn token savings + continuity across experiment arms
- **filter** (Phase 2): Compression-ratio product claim on real corpora via archolith-rtk
- **stack** (Phase 3): Four-way headline comparison (direct/filter/proxy/proxy+filter)
- **audit** (Phase 4): MCP token-waste reduction before/after via archolith-audit

## How to Run
```bash
pip install -e .
archolith-bench proxy --list          # list scenarios (no proxy needed)
archolith-bench proxy --all --arms direct,proxy_only  # run against live proxy
```

## FOLLOW-UP
- GitHub remote `archolith/archolith-bench` still needs creating. Add with: `git remote add origin git@github.com:archolith/archolith-bench.git`
- Phase 2+ deps (archolith-rtk, archolith-audit) not yet in pyproject.toml