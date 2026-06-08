# Code Conventions — archolith-bench

## Style

- Python 3.11+ only
- 4 spaces indent, no tabs
- 120 character max line length
- UTF-8 encoding for all source files
- Trailing commas in multi-line collections

## Imports

- `from __future__ import annotations` in every module
- Import order: stdlib → third-party → local
- No unused imports; let ruff catch them
- No wildcard imports (`from x import *`)

## Naming

| Element | Convention | Example |
|---------|------------|---------|
| Packages / modules | snake_case | `archolith_bench`, `core`, `scenario.py` |
| Classes | PascalCase | `ScenarioResult`, `ContinuityTracker` |
| Functions / methods | snake_case | `run_benchmark()`, `send_chat()` |
| Constants | UPPER_SNAKE_CASE | `COLLAPSE_CONSECUTIVE_LIMIT`, `SCENARIOS_DIR` |
| Private functions | `_` prefix | `_run_proxy()`, `_run_filter()` |
| Variables | snake_case | `arm_name`, `output_dir` |

## Types

- Builtin generics: `list[str]`, `dict[str, int]`, not `typing.List`/`typing.Dict`
- Union types: `str | None`, not `Optional[str]`
- Use `from __future__ import annotations` to defer annotation evaluation
- Dataclasses with `field(default_factory=list)` for mutable defaults, never `= []`

## Dataclasses

```python
from dataclasses import dataclass, field

@dataclass
class Example:
    name: str
    count: int = 0
    items: list[str] = field(default_factory=list)
```

## CLI Conventions

- Use `argparse` (not `click` or `typer`)
- Subcommands via `add_subparsers(dest="suite")`
- Module-level constants for defaults: `PROXY_URL`, `DIRECT_URL`, `API_KEY`, `MODEL`
- Validate user input early; fail with clear error messages to stderr
- Environment variables loaded via `python-dotenv` at module level

## HTTP Client

- Use `httpx.Client` (synchronous) for all HTTP calls
- Exponential backoff on 429 rate limits (function `send_chat` handles this)
- Check proxy health before starting proxy-dependent suites

## Error Handling

- Print user-facing errors to `sys.stderr`, not `sys.stdout`
- Use `sys.exit(1)` for fatal errors
- Catch `json.JSONDecodeError` when parsing user-provided JSON strings
- Log rate limit responses (429) silently during retry, report only on exhaustion

## Testing

- Tests go in `tests/` directory
- Use `pytest` as the test runner
- Test files named `test_<module>.py`
- No external API calls in tests — mock all HTTP
- Scenario loading tests should use minimal inline JSON
