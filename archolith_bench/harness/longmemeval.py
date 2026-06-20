"""LongMemEval adapter — official long-term memory QA benchmark.

Dataset: LongMemEval (Wu et al., ICLR 2025) — chat assistants answering questions
that require recalling facts across long, multi-session histories. Measures the
five memory abilities: information extraction, multi-session reasoning, temporal
reasoning, knowledge updates, and abstention.

This is the capability benchmark for a memory system (menhir is built on Graphiti,
the same temporal-KG engine Zep reports on LongMemEval/DMR). Run as a direct-vs-
proxy A/B: the proxy assembles relevant memory from the history, so the claim is
memory-QA accuracy preserved/improved while tokens drop.

Online use needs the `longmemeval` extra (`datasets`); offline reads a fixture.

Scoring note: the official benchmark uses a GPT-4 judge. This adapter ships a
deterministic normalized-containment scorer (good for factual answers, offline,
no judge spend); an LLM-judge scorer can be added behind a flag later.
"""

from __future__ import annotations

import json
import re
import string
from pathlib import Path

from .base import Task

_SYSTEM_PROMPT = (
    "You are a helpful assistant with long-term memory of the user's prior conversations. "
    "Use the conversation history to answer the final question accurately and concisely. "
    "If the history does not contain the answer, say you don't know."
)

_PUNCT = str.maketrans("", "", string.punctuation)


def _flatten_history(item: dict) -> list[dict]:
    """Flatten LongMemEval haystack sessions into chat turns."""
    msgs: list[dict] = [{"role": "system", "content": _SYSTEM_PROMPT}]
    sessions = item.get("haystack_sessions") or item.get("sessions") or []
    for session in sessions:
        for turn in session:
            role = turn.get("role", "user")
            content = turn.get("content", "")
            if content:
                msgs.append({"role": "user" if role == "user" else "assistant", "content": content})
    msgs.append({"role": "user", "content": item.get("question", "")})
    return msgs


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().translate(_PUNCT)).strip()


class LongMemEvalAdapter:
    """Official LongMemEval memory-QA accuracy, run as a direct-vs-proxy A/B."""

    benchmark_id = "longmemeval"
    name = "LongMemEval"

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
            task_id = str(item.get("question_id") or item.get("id") or f"lme-{i}")
            tasks.append(
                Task(
                    task_id=task_id,
                    prompt_messages=_flatten_history(item),
                    answer=str(item.get("answer", "")),
                    meta={"question_type": item.get("question_type")},
                )
            )
        return tasks

    def _load_items(self, subset: str | None, fixture_path: str | Path | None) -> list[dict]:
        if fixture_path is not None:
            with open(fixture_path, encoding="utf-8") as f:
                items = json.load(f)
            if subset:
                items = [it for it in items if it.get("question_type") == subset]
            return items
        try:
            from datasets import load_dataset
        except ImportError as e:  # pragma: no cover - online only
            raise RuntimeError(
                "LongMemEval requires the 'datasets' package. "
                "Install with: pip install '.[longmemeval]', or pass fixture_path for offline use."
            ) from e
        ds = load_dataset("xiaowu0162/longmemeval", split="train")  # pragma: no cover - network
        items = [dict(row) for row in ds]
        if subset:
            items = [it for it in items if it.get("question_type") == subset]
        return items

    def score(self, task: Task, response_text: str) -> bool:
        """Normalized-containment scorer.

        Abstention questions (gold answer signals 'no answer') pass if the model
        declines; otherwise the gold answer must appear in the response.
        """
        gold = _normalize(task.answer)
        resp = _normalize(response_text)
        if not resp:
            return False
        if task.meta.get("question_type") == "abstention" or gold in {"", "no answer", "unknown"}:
            return any(p in resp for p in ("dont know", "not sure", "no information", "cannot", "unable"))
        return bool(gold) and gold in resp
