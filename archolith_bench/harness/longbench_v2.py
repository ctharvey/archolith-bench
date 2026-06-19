"""LongBench v2 adapter — official multiple-choice long-context benchmark.

Dataset: `THUDM/LongBench-v2` (HuggingFace). Each item is a 4-way multiple-choice
question over a long context; the official metric is accuracy. Run as a direct-vs-
proxy A/B via `harness.base.run_ab`.

Online use requires the optional `datasets` dependency (`pip install ".[longbench]"`).
Offline/testing reads a bundled JSON fixture instead.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .base import Task

_CHOICE_KEYS = ("choice_A", "choice_B", "choice_C", "choice_D")
_LETTERS = ("A", "B", "C", "D")

_SYSTEM_PROMPT = (
    "You are answering a multiple-choice reading comprehension question about a long "
    "document. Read the context carefully and choose the single best answer. Respond "
    "with only the letter of the correct choice (A, B, C, or D)."
)

# Prefer an explicit "answer: X" / "answer is X" statement; fall back to a lone letter.
_ANSWER_RE = re.compile(r"answer\s*(?:is|:)?\s*\(?([ABCD])\)?", re.IGNORECASE)
_LONE_LETTER_RE = re.compile(r"\b([ABCD])\b")


def _build_prompt(item: dict) -> list[dict]:
    context = item.get("context", "")
    question = item.get("question", "")
    choices = "\n".join(
        f"{letter}. {item.get(key, '')}" for letter, key in zip(_LETTERS, _CHOICE_KEYS)
    )
    user = (
        f"{context}\n\n"
        f"Question: {question}\n\n"
        f"{choices}\n\n"
        "Answer with the single letter A, B, C, or D."
    )
    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]


def _extract_choice(text: str) -> str:
    """Return the predicted letter (A-D) from a model response, or '' if none."""
    if not text:
        return ""
    m = _ANSWER_RE.search(text)
    if m:
        return m.group(1).upper()
    m = _LONE_LETTER_RE.search(text.strip())
    if m:
        return m.group(1).upper()
    return ""


class LongBenchV2Adapter:
    """Official LongBench v2 multiple-choice accuracy, run as direct-vs-proxy A/B."""

    benchmark_id = "longbench-v2"
    name = "LongBench v2"

    def load_tasks(
        self,
        subset: str | None = None,
        limit: int | None = None,
        fixture_path: str | Path | None = None,
    ) -> list[Task]:
        items = self._load_items(subset=subset, fixture_path=fixture_path)
        if limit is not None:
            items = items[:limit]
        tasks: list[Task] = []
        for i, item in enumerate(items):
            task_id = str(item.get("_id") or item.get("id") or f"lbv2-{i}")
            answer = str(item.get("answer", "")).strip().upper()
            tasks.append(
                Task(
                    task_id=task_id,
                    prompt_messages=_build_prompt(item),
                    answer=answer,
                    meta={
                        "domain": item.get("domain"),
                        "difficulty": item.get("difficulty"),
                        "length": item.get("length"),
                    },
                )
            )
        return tasks

    def _load_items(
        self, subset: str | None, fixture_path: str | Path | None
    ) -> list[dict]:
        if fixture_path is not None:
            with open(fixture_path, encoding="utf-8") as f:
                items = json.load(f)
            if subset:
                items = [it for it in items if it.get("domain") == subset]
            return items

        try:
            from datasets import load_dataset
        except ImportError as e:  # pragma: no cover - exercised only online
            raise RuntimeError(
                "LongBench v2 requires the 'datasets' package. "
                "Install with: pip install '.[longbench]', or pass fixture_path for offline use."
            ) from e

        ds = load_dataset("THUDM/LongBench-v2", split="train")  # pragma: no cover - network
        items = [dict(row) for row in ds]
        if subset:
            items = [it for it in items if it.get("domain") == subset]
        return items

    def score(self, task: Task, response_text: str) -> bool:
        predicted = _extract_choice(response_text)
        return bool(predicted) and predicted == task.answer.upper()
