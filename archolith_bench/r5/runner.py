"""R5 StructureTemporalOracle bench — time-aware blast radius ladder.

Conditions:
    A_structure_only   rank the anchor's structural dependencies with NO time awareness
                       (every dependency is an equal suspect — can't tell what changed when).
    B_structure_temporal  the StructureTemporalOracle: rank by in-window change
                       (proximity + recency + density).

Each fixture = a failing anchor + a dependency graph + a git change log (some changes IN the
window, some OUT) + the GOLD culprit (the dependency whose in-window change caused the break).

Metrics:
    culprit_at_1        culprit ranked #1            (HIGHER better)
    culprit_recall_at_k culprit in top-k             (HIGHER better)
    noise_at_1          a non-culprit ranked #1      (LOWER better)

Win gate: B ranks the culprit #1 where A cannot (A has no signal to prefer the changed
dependency over its unchanged/out-of-window siblings).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from menhir.domain.git_staleness import GitChange
from menhir.domain.structural_expansion import ExpansionConfig, StructuralNeighbor
from menhir.domain.structure_temporal import (
    StructureTemporalOracle,
    StructureTemporalQuery,
)

CONDITIONS: tuple[str, ...] = ("A_structure_only", "B_structure_temporal")
BASELINE_CONDITION = "A_structure_only"
DEFAULT_K = 3


@dataclass
class R5Fixture:
    name: str
    description: str
    anchor: str = ""
    window_start: str | None = None
    window_end: str | None = None
    culprit: str = ""
    graph: dict[str, list[dict[str, str]]] = field(default_factory=dict)
    changes: list[dict] = field(default_factory=list)
    max_depth: int = 2

    def neighbor_fn(self):
        def fn(node: str) -> list[StructuralNeighbor]:
            return [StructuralNeighbor(id=e["id"], relation=e.get("relation", "callee")) for e in self.graph.get(node, [])]
        return fn

    def git_changes(self) -> list[GitChange]:
        return [
            GitChange(c["target"], c["changed_at"], kind=c.get("kind", "file"),
                      commit=c.get("commit"), renamed_from=c.get("renamed_from"))
            for c in self.changes
        ]

    @property
    def config(self) -> ExpansionConfig:
        return ExpansionConfig(max_depth=self.max_depth, max_clones_per_hit=9)

    @classmethod
    def from_file(cls, path: str | Path) -> "R5Fixture":
        with open(path) as h:
            d = json.load(h)
        return cls(
            name=d.get("name", "unnamed"), description=d.get("description", ""),
            anchor=d["anchor"], window_start=d.get("window_start"), window_end=d.get("window_end"),
            culprit=d["culprit"], graph={k: list(v) for k, v in d.get("graph", {}).items()},
            changes=list(d.get("changes", [])), max_depth=int(d.get("max_depth", 2)),
        )


class R5BenchRunner:
    def __init__(self, fixture: R5Fixture, k: int = DEFAULT_K) -> None:
        self.fixture = fixture
        self.k = k

    def _ranked_ids(self, condition: str) -> list[str]:
        fx = self.fixture
        if condition == "A_structure_only":
            # structure-only: the blast radius in structural order, no time signal -> all the
            # anchor's dependencies, deterministically ordered, with no preference for changed.
            # structure-only ranks the raw radius (time-blind), not a change-filtered window:
            from menhir.domain.structural_expansion import expand_structural
            radius = expand_structural([fx.anchor], fx.neighbor_fn(), config=fx.config)
            return [c.id for c in radius.candidates]  # depth/discovery order, time-blind
        oracle = StructureTemporalOracle(neighbor_fn=fx.neighbor_fn(), config=fx.config)
        ranked = oracle.evaluate(
            StructureTemporalQuery(fx.anchor, fx.window_start, fx.window_end), fx.git_changes()
        )
        return [r.dependency.id for r in ranked]

    def run_condition(self, condition: str) -> dict[str, float]:
        ranked = self._ranked_ids(condition)
        culprit = self.fixture.culprit
        at1 = 1.0 if ranked[:1] == [culprit] else 0.0
        recall_k = 1.0 if culprit in ranked[: self.k] else 0.0
        noise1 = 1.0 if ranked and ranked[0] != culprit else 0.0
        return {"culprit_at_1": at1, "culprit_recall_at_k": recall_k, "noise_at_1": noise1}

    def run(self) -> dict:
        results = {c: self.run_condition(c) for c in CONDITIONS}
        gate = evaluate_win_gate(results)
        return {
            "fixture": self.fixture.name, "description": self.fixture.description,
            "config": {"k": self.k, "anchor": self.fixture.anchor, "culprit": self.fixture.culprit,
                       "conditions": list(CONDITIONS)},
            "conditions": {c: {"metrics": m} for c, m in results.items()},
            "win_gate": gate,
        }


def evaluate_win_gate(results: dict[str, dict[str, float]]) -> dict:
    """B graduates if it ranks the culprit #1 where A does not (time signal beats blind structure)."""
    if BASELINE_CONDITION not in results or "B_structure_temporal" not in results:
        return {"graduates": False, "reason": "missing baseline or B condition"}
    a = results[BASELINE_CONDITION]
    b = results["B_structure_temporal"]
    graduates = b["culprit_at_1"] > a["culprit_at_1"]
    return {
        "graduates": graduates,
        "culprit_at_1": {"A": a["culprit_at_1"], "B": b["culprit_at_1"]},
        "noise_at_1": {"A": a["noise_at_1"], "B": b["noise_at_1"]},
    }
