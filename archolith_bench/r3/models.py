"""Data models for the R3 belief-currentness benchmark.

A fixture is a set of belief items (each = a candidate statement + its evidence +
gold labels) and a query with an intent. Gold labels are the ground truth the
metrics judge against:

  gold_current     — is this belief SAFE to assert as current truth right now?
  gold_historical  — is this a valid former belief worth preserving (timeline value)?
  is_noise         — is this unsupported/poisoned content that must stay out of context?

Evidence is given as {signal, polarity?, strength?} dicts and converted to menhir
BeliefEvidence so the bench scores with the real domain.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from menhir.domain.belief import BeliefEvidence, EvidencePolarity, EvidenceSignal


def to_evidence(rows: list[dict[str, Any]] | None) -> list[BeliefEvidence]:
    """Convert fixture evidence dicts to menhir BeliefEvidence (skips unknown signals)."""
    out: list[BeliefEvidence] = []
    for row in rows or []:
        try:
            signal = EvidenceSignal(str(row["signal"]))
        except (KeyError, ValueError):
            continue
        polarity = EvidencePolarity(str(row.get("polarity", "supports")))
        out.append(BeliefEvidence(signal, polarity, float(row.get("strength", 1.0)), note=row.get("note")))
    return out


@dataclass
class BeliefItem:
    """One candidate belief: statement + evidence + gold labels."""

    id: str
    statement: str
    evidence: list[dict[str, Any]] = field(default_factory=list)
    gold_current: bool = False
    gold_historical: bool = False
    is_noise: bool = False

    @classmethod
    def from_dict(cls, data: dict) -> "BeliefItem":
        return cls(
            id=str(data["id"]),
            statement=data.get("statement", ""),
            evidence=list(data.get("evidence", [])),
            gold_current=bool(data.get("gold_current", False)),
            gold_historical=bool(data.get("gold_historical", False)),
            is_noise=bool(data.get("is_noise", False)),
        )


@dataclass
class BeliefFixture:
    """A loadable R3 fixture: belief items + the query intent under test."""

    name: str
    description: str
    intent: str = "current"
    items: list[BeliefItem] = field(default_factory=list)

    @property
    def items_by_id(self) -> dict[str, BeliefItem]:
        return {i.id: i for i in self.items}

    @classmethod
    def from_dict(cls, data: dict) -> "BeliefFixture":
        return cls(
            name=data.get("name", "unnamed"),
            description=data.get("description", ""),
            intent=data.get("intent", "current"),
            items=[BeliefItem.from_dict(i) for i in data.get("items", [])],
        )

    @classmethod
    def from_file(cls, path: str | Path) -> "BeliefFixture":
        with open(path) as handle:
            return cls.from_dict(json.load(handle))
