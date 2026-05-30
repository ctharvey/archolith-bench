"""Scenario loading and discovery for archolith-bench."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


SCENARIOS_DIR = Path(__file__).resolve().parent.parent.parent / "scenarios"


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
    turns: list[str]
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


def list_scenarios() -> list[Path]:
    return sorted(SCENARIOS_DIR.glob("*.json"))