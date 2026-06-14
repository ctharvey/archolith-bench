"""Scenario loading and discovery for archolith-bench."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path


_env_scenarios = os.environ.get("ARCHOLITH_BENCH_SCENARIOS_DIR")
SCENARIOS_DIR = Path(_env_scenarios) if _env_scenarios else Path(__file__).resolve().parent.parent.parent / "scenarios"


@dataclass
class FactProbe:
    after_turn: int
    question: str
    expected_keywords: list[str]


@dataclass
class Scenario:
    name: str
    description: str
    system_prompt: str
    turns: list[str | dict]
    fact_probes: list[FactProbe] = field(default_factory=list)

    @classmethod
    def from_file(cls, path: Path) -> "Scenario":
        with open(path) as f:
            data = json.load(f)
        probes = [FactProbe(**p) for p in data.get("fact_probes", [])]
        return cls(
            name=data["name"],
            description=data["description"],
            system_prompt=data["system_prompt"],
            turns=data["turns"],
            fact_probes=probes,
        )


def is_tool_turn(turn: str | dict) -> bool:
    """Return True if turn is a tool-loop dict (has 'tool_calls' key)."""
    return isinstance(turn, dict) and "tool_calls" in turn


def build_turn_messages(turn: str | dict) -> list[dict]:
    """Assemble chat messages for one scenario turn.

    str turn → [user message]
    tool-loop dict → [user, assistant(tool_call), tool(result), ...]

    Tool-call IDs are stable and deterministic (sha1 of index + name + args).
    """
    if isinstance(turn, str):
        return [{"role": "user", "content": turn}]

    user_text = turn["user"]
    messages: list[dict] = [{"role": "user", "content": user_text}]
    for idx, tc in enumerate(turn.get("tool_calls", [])):
        raw = json.dumps({"i": idx, "n": tc["name"], "a": tc.get("arguments", {})}, sort_keys=True)
        call_id = "call_" + hashlib.sha1(raw.encode()).hexdigest()[:16]
        arguments_str = (
            json.dumps(tc["arguments"])
            if isinstance(tc.get("arguments"), dict)
            else tc.get("arguments", "{}")
        )
        messages.append({
            "role": "assistant",
            "content": None,
            "tool_calls": [{
                "id": call_id,
                "type": "function",
                "function": {"name": tc["name"], "arguments": arguments_str},
            }],
        })
        messages.append({
            "role": "tool",
            "tool_call_id": call_id,
            "content": tc["result"],
        })
    return messages


def list_scenarios() -> list[Path]:
    return sorted(SCENARIOS_DIR.glob("*.json"))
