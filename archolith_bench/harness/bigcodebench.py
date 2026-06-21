"""BigCodeBench-Hard adapter — official function-level code-generation benchmark.

Dataset: `bigcode/bigcodebench-hard` (HuggingFace). Each item gives an instruction
prompt plus a unittest `test`; the official metric is pass@1 — generate code, run
the provided tests, pass if they all succeed. Run as a direct-vs-proxy A/B via
`harness.base.run_ab`.

Generated code is executed in a subprocess with a timeout (never in-process) so a
bad/hostile generation cannot affect the benchmark runner. Online use needs the
`bigcodebench` extra (`datasets`); offline reads a bundled JSON fixture.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

from .base import Task
from .tempfiles import secure_temporary_directory

_SYSTEM_PROMPT = (
    "You are an expert Python programmer. Complete the requested function. "
    "Return only a single self-contained Python code block with all imports."
)

_CODE_FENCE_RE = re.compile(r"```(?:python)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)

_EXEC_TIMEOUT_S = 30


def _build_prompt(item: dict) -> list[dict]:
    instruction = item.get("instruct_prompt") or item.get("complete_prompt") or item.get("prompt", "")
    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": instruction},
    ]


def _extract_code(text: str) -> str:
    """Pull the Python code out of a model response (fenced block if present)."""
    if not text:
        return ""
    m = _CODE_FENCE_RE.search(text)
    if m:
        return m.group(1).strip()
    return text.strip()


def _execute_tests(solution: str, test: str, timeout: int = _EXEC_TIMEOUT_S) -> bool:
    """Run solution + unittest `test` in a subprocess; True iff tests pass."""
    script = f"{solution}\n\n{test}\n\nimport unittest\nunittest.main(argv=['x'], exit=False)\n"
    with secure_temporary_directory() as workdir:
        path = workdir / "candidate.py"
        path.write_text(script, encoding="utf-8")
        try:
            proc = subprocess.run(
                [sys.executable, str(path)],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=workdir,
            )
        except subprocess.TimeoutExpired:
            return False
    # unittest writes the summary to stderr; "OK" with no failures means pass.
    out = proc.stderr + proc.stdout
    if proc.returncode != 0:
        return False
    return "OK" in out and "FAILED" not in out


class BigCodeBenchHardAdapter:
    """Official BigCodeBench-Hard pass@1, run as a direct-vs-proxy A/B."""

    benchmark_id = "bigcodebench-hard"
    name = "BigCodeBench-Hard"

    def load_tasks(
        self,
        subset: str | None = None,
        limit: int | None = None,
        fixture_path: str | Path | None = None,
    ) -> list[Task]:
        items = self._load_items(fixture_path=fixture_path)
        if limit is not None:
            items = items[:limit]
        tasks: list[Task] = []
        for i, item in enumerate(items):
            task_id = str(item.get("task_id") or f"bcb-{i}")
            tasks.append(
                Task(
                    task_id=task_id,
                    prompt_messages=_build_prompt(item),
                    answer="",
                    meta={
                        "test": item.get("test", ""),
                        "entry_point": item.get("entry_point", ""),
                    },
                )
            )
        return tasks

    def _load_items(self, fixture_path: str | Path | None) -> list[dict]:
        if fixture_path is not None:
            with open(fixture_path, encoding="utf-8") as f:
                return json.load(f)
        try:
            from datasets import load_dataset
        except ImportError as e:  # pragma: no cover - online only
            raise RuntimeError(
                "BigCodeBench requires the 'datasets' package. "
                "Install with: pip install '.[bigcodebench]', or pass fixture_path for offline use."
            ) from e
        ds = load_dataset("bigcode/bigcodebench-hard", split="v0.1.0_hf")  # pragma: no cover - network
        return [dict(row) for row in ds]

    def score(self, task: Task, response_text: str) -> bool:
        solution = _extract_code(response_text)
        test = task.meta.get("test", "")
        if not solution or not test:
            return False
        return _execute_tests(solution, test)
