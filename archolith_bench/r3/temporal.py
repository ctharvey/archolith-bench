"""R3 rung B bench — temporal-metadata ladder.

Tests whether applying the bitemporal clock model to recall returns the right facts for
each temporal lens (current belief / as-of world time / what-we-knew-then), where a
temporal-blind baseline cannot. Consumes menhir.domain.temporal (the real filters).

Conditions:
    A_no_temporal   temporal-blind: return every fact (no stamp handling) — the failure
                    where a stale/superseded fact is surfaced as current.
    B_temporal      apply matches_query() for the query's temporal lens.

Each query declares a lens + optional as_of and gold fact ids. Metrics:
    temporal_recall      gold facts returned / gold                      (HIGHER)
    temporal_precision   returned facts that are gold / returned         (HIGHER)
    leak_rate            non-gold facts returned / returned              (LOWER — stale/leak)

Win gate: B beats A on temporal_precision (cuts leakage) without losing recall.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from menhir.domain.temporal import FactTemporal, TemporalQuery, matches_query

CONDITIONS: tuple[str, ...] = ("A_no_temporal", "B_temporal")
BASELINE_CONDITION = "A_no_temporal"


@dataclass
class TemporalFact:
    id: str
    statement: str = ""
    temporal: FactTemporal = field(default_factory=FactTemporal)

    @classmethod
    def from_dict(cls, d: dict) -> "TemporalFact":
        return cls(
            id=str(d["id"]),
            statement=d.get("statement", ""),
            temporal=FactTemporal(
                valid_at=d.get("valid_at"), invalid_at=d.get("invalid_at"),
                created_at=d.get("created_at"), expired_at=d.get("expired_at"),
            ),
        )


@dataclass
class TemporalQuerySpec:
    id: str
    lens: str                       # current_belief | as_of_world | as_known_at
    as_of: str | None = None
    gold_ids: list[str] = field(default_factory=list)
    note: str = ""

    @classmethod
    def from_dict(cls, d: dict) -> "TemporalQuerySpec":
        return cls(
            id=str(d["id"]), lens=str(d.get("lens", "current_belief")),
            as_of=d.get("as_of"), gold_ids=[str(x) for x in d.get("gold_ids", [])], note=d.get("note", ""),
        )


@dataclass
class TemporalFixture:
    name: str
    description: str
    facts: list[TemporalFact] = field(default_factory=list)
    queries: list[TemporalQuerySpec] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> "TemporalFixture":
        return cls(
            name=d.get("name", "unnamed"), description=d.get("description", ""),
            facts=[TemporalFact.from_dict(f) for f in d.get("facts", [])],
            queries=[TemporalQuerySpec.from_dict(q) for q in d.get("queries", [])],
        )

    @classmethod
    def from_file(cls, path: str | Path) -> "TemporalFixture":
        with open(path) as h:
            return cls.from_dict(json.load(h))


@dataclass
class ConditionResult:
    condition: str
    metrics: dict[str, float]


class TemporalBenchRunner:
    def __init__(self, fixture: TemporalFixture) -> None:
        self.fixture = fixture

    def _returned(self, condition: str, q: TemporalQuerySpec) -> set[str]:
        if condition == "A_no_temporal":
            return {f.id for f in self.fixture.facts}  # temporal-blind: everything
        lens = TemporalQuery(q.lens)
        return {f.id for f in self.fixture.facts if matches_query(f.temporal, lens, as_of=q.as_of)}

    def run_condition(self, condition: str) -> ConditionResult:
        recall = precision = leak = 0.0
        n = len(self.fixture.queries) or 1
        for q in self.fixture.queries:
            returned = self._returned(condition, q)
            gold = set(q.gold_ids)
            hits = gold & returned
            recall += len(hits) / len(gold) if gold else 1.0
            precision += len(hits) / len(returned) if returned else 1.0
            leak += (len(returned) - len(hits)) / len(returned) if returned else 0.0
        return ConditionResult(condition, {
            "temporal_recall": round(recall / n, 4),
            "temporal_precision": round(precision / n, 4),
            "leak_rate": round(leak / n, 4),
        })

    def run(self) -> dict:
        results = {c: self.run_condition(c) for c in CONDITIONS}
        gate = evaluate_win_gate(results)
        return {
            "fixture": self.fixture.name, "description": self.fixture.description,
            "config": {"n_facts": len(self.fixture.facts), "n_queries": len(self.fixture.queries), "conditions": list(CONDITIONS)},
            "conditions": {c: {"metrics": r.metrics} for c, r in results.items()},
            "win_gate": gate,
        }


def evaluate_win_gate(results: dict[str, ConditionResult], recall_tolerance: float = 0.0) -> dict:
    """B graduates if it raises temporal_precision (cuts leakage) vs A without losing recall."""
    if BASELINE_CONDITION not in results or "B_temporal" not in results:
        return {"graduates": False, "reason": "missing baseline or B condition"}
    a = results[BASELINE_CONDITION].metrics
    b = results["B_temporal"].metrics
    precision_gain = round(b["temporal_precision"] - a["temporal_precision"], 4)
    recall_loss = round(a["temporal_recall"] - b["temporal_recall"], 4)
    graduates = precision_gain > 0 and recall_loss <= recall_tolerance
    return {
        "graduates": graduates, "precision_gain": precision_gain, "recall_loss": recall_loss,
        "leak_cut": round(a["leak_rate"] - b["leak_rate"], 4),
        "baseline": a, "b_temporal": b,
    }
