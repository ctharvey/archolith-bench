"""R3 rung F bench — bounded structural expansion ladder.

Tests whether expanding semantic seed hits to bounded structural neighbors surfaces the
bug-relevant memory that the semantic ranking misses, WITHOUT unbounded pool blow-up.
Consumes menhir.domain.structural_expansion (the real algorithm + guards).

Conditions:
    A_semantic_only        candidate pool = the semantic seed hits.
    F_structural_expansion seeds + bounded structural expansion.

Metrics:
    structural_neighbor_recall  gold bug-relevant neighbors in the pool / gold neighbors (HIGHER)
    hub_kept_out                1.0 if no hub/utility node entered the pool (must stay 1.0)
    pool_size                   total candidates (bounded check)

Win gate: F raises structural_neighbor_recall over A, keeps every hub out, and the pool
stays within the configured cap (seeds + max_total_clones).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from menhir.domain.structural_expansion import (
    ExpansionConfig,
    StructuralNeighbor,
    expand_structural,
)

CONDITIONS: tuple[str, ...] = ("A_semantic_only", "F_structural_expansion")
BASELINE_CONDITION = "A_semantic_only"


@dataclass
class StructuralFixture:
    name: str
    description: str
    seed_hits: list[str] = field(default_factory=list)
    gold_neighbors: list[str] = field(default_factory=list)
    hub_nodes: list[str] = field(default_factory=list)
    graph: dict[str, list[dict[str, str]]] = field(default_factory=dict)
    degrees: dict[str, int] = field(default_factory=dict)
    max_clones_per_hit: int = 5
    max_total_clones: int = 20
    max_depth: int = 2
    utility_degree_threshold: int = 25

    def neighbor_fn(self):
        def fn(node: str) -> list[StructuralNeighbor]:
            return [StructuralNeighbor(id=e["id"], relation=e.get("relation", "neighbor")) for e in self.graph.get(node, [])]
        return fn

    def degree_fn(self):
        degrees = self.degrees
        def fn(node: str) -> int:
            return int(degrees.get(node, 0))
        return fn

    @property
    def config(self) -> ExpansionConfig:
        return ExpansionConfig(
            max_clones_per_hit=self.max_clones_per_hit,
            max_total_clones=self.max_total_clones,
            max_depth=self.max_depth,
            utility_degree_threshold=self.utility_degree_threshold,
        )

    @classmethod
    def from_dict(cls, d: dict) -> "StructuralFixture":
        return cls(
            name=d.get("name", "unnamed"),
            description=d.get("description", ""),
            seed_hits=[str(x) for x in d.get("seed_hits", [])],
            gold_neighbors=[str(x) for x in d.get("gold_neighbors", [])],
            hub_nodes=[str(x) for x in d.get("hub_nodes", [])],
            graph={k: list(v) for k, v in d.get("graph", {}).items()},
            degrees={k: int(v) for k, v in d.get("degrees", {}).items()},
            max_clones_per_hit=int(d.get("max_clones_per_hit", 5)),
            max_total_clones=int(d.get("max_total_clones", 20)),
            max_depth=int(d.get("max_depth", 2)),
            utility_degree_threshold=int(d.get("utility_degree_threshold", 25)),
        )

    @classmethod
    def from_file(cls, path: str | Path) -> "StructuralFixture":
        with open(path) as h:
            return cls.from_dict(json.load(h))


@dataclass
class ConditionResult:
    condition: str
    metrics: dict[str, float]
    pool: list[str] = field(default_factory=list)


class StructuralBenchRunner:
    def __init__(self, fixture: StructuralFixture) -> None:
        self.fixture = fixture

    def _pool(self, condition: str) -> list[str]:
        seeds = list(dict.fromkeys(self.fixture.seed_hits))
        if condition == "A_semantic_only":
            return seeds
        res = expand_structural(
            seeds, self.fixture.neighbor_fn(), config=self.fixture.config, degree_fn=self.fixture.degree_fn()
        )
        return list(dict.fromkeys(seeds + res.candidate_ids))

    def run_condition(self, condition: str) -> ConditionResult:
        pool = self._pool(condition)
        pool_set = set(pool)
        gold = set(self.fixture.gold_neighbors)
        hubs = set(self.fixture.hub_nodes)
        recall = len(gold & pool_set) / len(gold) if gold else 1.0
        hub_kept_out = 1.0 if not (hubs & pool_set) else round(1.0 - len(hubs & pool_set) / len(hubs), 4)
        return ConditionResult(
            condition=condition,
            metrics={
                "structural_neighbor_recall": round(recall, 4),
                "hub_kept_out": hub_kept_out,
                "pool_size": float(len(pool)),
            },
            pool=pool,
        )

    def run(self) -> dict:
        results = {c: self.run_condition(c) for c in CONDITIONS}
        gate = evaluate_win_gate(results, self.fixture)
        return {
            "fixture": self.fixture.name,
            "description": self.fixture.description,
            "config": {"max_total_clones": self.fixture.max_total_clones, "max_depth": self.fixture.max_depth, "conditions": list(CONDITIONS)},
            "conditions": {c: {"metrics": r.metrics, "pool": r.pool} for c, r in results.items()},
            "win_gate": gate,
        }


def evaluate_win_gate(results: dict[str, ConditionResult], fixture: StructuralFixture) -> dict:
    """F graduates if it raises structural_neighbor_recall vs A, keeps every hub out
    (hub_kept_out == 1.0), and the pool stays within seeds + max_total_clones."""
    if BASELINE_CONDITION not in results or "F_structural_expansion" not in results:
        return {"graduates": False, "reason": "missing baseline or F condition"}
    a = results[BASELINE_CONDITION].metrics
    f = results["F_structural_expansion"].metrics
    recall_gain = round(f["structural_neighbor_recall"] - a["structural_neighbor_recall"], 4)
    pool_bound = len(set(fixture.seed_hits)) + fixture.max_total_clones
    bounded = f["pool_size"] <= pool_bound
    graduates = recall_gain > 0 and f["hub_kept_out"] >= 1.0 and bounded
    return {
        "graduates": graduates,
        "recall_gain": recall_gain,
        "hub_kept_out": f["hub_kept_out"],
        "pool_size": f["pool_size"],
        "pool_bound": pool_bound,
        "bounded": bounded,
        "baseline_recall": a["structural_neighbor_recall"],
        "f_recall": f["structural_neighbor_recall"],
    }
