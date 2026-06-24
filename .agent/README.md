# archolith-bench — Project Context

## Purpose
Unified benchmark suite for the archolith product family. Measures token savings, continuity, compression, and cross-product metrics across proxy, filter, audit, and stack scenarios.

## Suites
- **proxy** (Phase 1, critical path for June 30 launch): Multi-turn token savings + continuity across experiment arms
- **filter** (Phase 2): Compression-ratio product claim on real corpora via archolith-filter
- **stack** (Phase 3): Experimental four-way comparison (direct/filter/proxy/proxy+filter); pending refreshed live run before launch copy
- **audit** (Phase 4): MCP token-waste reduction before/after via archolith-audit
- **industry** (Launch gate): Product-to-benchmark coverage matrix tying Archolith claims to trusted external benchmark families

## How to Run
```bash
pip install -e .
python -m pip install -e ../archolith-filter
python -m pip install -e ../archolith-mcp-audit
pip install -e ".[all]"                 # optional filter/audit suite deps after sibling editable installs
archolith-bench proxy --list          # list scenarios (no proxy needed)
archolith-bench proxy --all --arms direct,proxy_only  # run against live proxy
archolith-bench industry --launch-only                # generate launch benchmark coverage matrix
```

## Headline Numbers Policy

**`HEADLINE-NUMBERS.md` is the canonical source for any stat used in marketing copy or README headlines.**
Before writing any percentage or token count into archolith.dev or a product README:
1. Check `HEADLINE-NUMBERS.md` — if it isn't there, it isn't verified.
2. Run the benchmark, paste the result row into the table, note the commit.
3. Fixture data (from bundled `fixtures/`) is NOT a headline number — it demonstrates report format only.

## Launch Readiness

Use `.agent/launch-readiness-tracker.md` as the active pre-launch checklist.
The current posture is imminent pre-launch: fix Critical and High items first,
and defer polish unless it blocks installability, reproducibility, or trust.

## FOLLOW-UP
- GitHub remote `archolith/archolith-bench` still needs creating. Add with: `git remote add origin git@github.com:archolith/archolith-bench.git`
- `archolith-filter` and `archolith-audit` are optional extras (`filter`, `audit`, `all`) so base install remains usable before those sibling packages are published. For source checkouts, install sibling repos editable from `../archolith-filter` and `../archolith-mcp-audit` before `pip install -e ".[all]"`.
- The industry benchmark registry is launch-facing. Candidate benchmarks are gates, not completed evidence, until a tracked artifact exists under `benchmarks/`.
