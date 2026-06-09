"""Metric dataclasses for the archolith-bench proxy suite."""

from __future__ import annotations

from dataclasses import dataclass


def estimate_tokens(text: str | None) -> int:
    """Estimate token count from text using a simple heuristic."""
    if not text:
        return 1
    return max(1, len(text) // 4)


def estimate_messages_tokens(messages: list[dict]) -> int:
    """Estimate total token count from a list of message dicts."""
    total = 0
    for m in messages:
        c = m.get("content", "")
        if isinstance(c, str):
            total += estimate_tokens(c)
        elif isinstance(c, list):
            for part in c:
                total += estimate_tokens(part.get("text", ""))
    return max(1, total)


@dataclass
class ContinuityMetrics:
    repeat_file_reads: int = 0
    repeat_diagnostics: int = 0
    decision_retention: float = 0.0
    verification_continuity: float = 0.0
    turn_one_orientation_score: float = 0.0
    snippet_hit_rate: float = 0.0