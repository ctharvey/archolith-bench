# AGENTS.md

## Project Instructions For Coding Agents

1. Before making changes, read the guidance files in `.agent/`.
2. Start with `.agent/README.md` for project workflow and conventions.
3. Use `.agent/data_models.md` for entity and schema expectations.
4. Use `.agent/architecture.md` for system design and external API context.
5. Check `.agent/workflows/` for task-specific runbooks before executing operational actions.
6. If there is a conflict between code and `.agent` docs, call it out explicitly and ask for clarification.

## Scope

These instructions apply to the entire repository.

## Build / Lint / Test Commands

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Install optional benchmark-suite dependencies
pip install -e ".[all]"

# Run all tests
pytest

# Default pytest collection is limited to tests/; experiments/ are archival
# benchmark inputs and are excluded from launch-readiness test runs.

# Run single test file
pytest tests/test_metrics.py

# Lint
ruff check .

# Auto-fix lint issues
ruff check --fix .

# Run benchmark suites (requires UPSTREAM_API_KEY in .env for proxy/stack)
archolith-bench proxy --list
archolith-bench filter
archolith-bench audit --before fixtures/audit_before.json --after fixtures/audit_after.json
archolith-bench industry --launch-only

# Generate BENCHMARKS.md from results/
archolith-bench report
```

## Code Style

See `.agent/workflows/code_conventions.md` for full rules. Key points:

- Python 3.11+, 4 spaces indent, 120 char max line length
- Builtin generics (`list`, `dict`), `X | Y` unions, not `typing.List`/`Optional`
- `from __future__ import annotations` in all modules
- snake_case for modules/functions, PascalCase for classes
- Dataclasses with `field(default_factory=...)` for mutable defaults

## Project-Specific Notes

- This is a **benchmark suite**, not a production service. It runs offline CLI sessions against a live proxy and upstream API.
- Token counting uses tiktoken (cl100k_base) when available via archolith-mcp-audit; falls back to char ÷ 4 heuristic.
- Scenario files in `scenarios/` define multi-turn conversations with optional fact probes. Keep scenarios deterministic and reproducible.
- The ContinuityTracker in `suites/proxy.py` measures repeat file reads, diagnostics, decision retention, and verification continuity across turns.
- The industry suite in `suites/industry.py` maps each product to trusted external benchmark families and launch gates; update it when benchmark standards or product scope change.
- Experiment arms in `arms.py` map named configurations to proxy `/admin/config` overrides. Add new arms there, not inline.
- Checkpoint files (`.checkpoint_*.json`) enable resumable benchmark runs. They live in the working directory.
- Headline numbers must be sourced from `HEADLINE-NUMBERS.md` before appearing in any marketing copy or README.
- Fixture data in `fixtures/` is for demonstrating report format only — not a source of verified stats.
