"""R3 Warden consolidation bench — the decide layer composed (Oracle/Warden/Mutator).

Proves the Warden trio works TOGETHER: each single warden only guards its own axis, so it
misses candidates that trip a different one; the WardenChain (most-restrictive-wins) catches
all of them without over-blocking the genuinely-safe candidate. Consumes menhir.domain.warden
(the real wardens), not a reimplementation.

Conditions: currentness_only / exhaustion_only / scope_only / chain.
Metrics:
    refuse_recall    of the candidates that should NOT enter current-truth context, the
                     fraction the condition keeps out                       (HIGHER better)
    admit_retention  of the candidates that SHOULD be admitted, the fraction admitted
                     (guard against over-blocking)                          (must stay 1.0)

Win gate: the chain's refuse_recall beats every single warden, with admit_retention == 1.0.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from menhir.domain.belief import (
    BeliefCandidate,
    BeliefCandidateType,
    BeliefEvidence,
    BeliefHead,
    BeliefScore,
    EvidenceSignal,
    QueryIntent,
    RecallBucket,
)
from menhir.domain.exhaustion import RetrievalStats
from menhir.domain.scope import MemoryScope
from menhir.domain.warden import (
    CurrentnessWarden,
    ExhaustionWarden,
    ScopeWarden,
    WardenChain,
    WardenContext,
    WardenDecision,
)

CONDITIONS: tuple[str, ...] = ("currentness_only", "exhaustion_only", "scope_only", "chain")


@dataclass
class WardenItem:
    """A candidate carrying the signals every warden might read, plus the gold decision."""

    id: str
    bucket: str = "safe_to_assert"        # currentness base bucket
    superseded: bool = False              # -> IS_EXPIRED evidence (currentness)
    intent: str = "current"
    retrievals_since_progress: int = 0    # exhaustion
    exempt_reason: str | None = None
    query_repo: str | None = None         # scope
    candidate_repo: str | None = None
    gold_admit: bool = True               # should this enter current-truth context?

    @classmethod
    def from_dict(cls, d: dict) -> "WardenItem":
        return cls(**{k: d[k] for k in d if k in cls.__dataclass_fields__})


def _context(item: WardenItem) -> WardenContext:
    score = BeliefScore(
        candidate=BeliefCandidate(id=item.id, statement="", candidate_type=BeliefCandidateType.FIX),
        head=BeliefHead.CURRENT, probability=0.9, support=1.0, contradiction=0.0,
        evidence_count=1, bucket=RecallBucket(item.bucket),
    )
    evidence = (BeliefEvidence(EvidenceSignal.IS_EXPIRED),) if item.superseded else ()
    stats = RetrievalStats(retrievals_since_progress=item.retrievals_since_progress, exempt_reason=None) \
        if item.retrievals_since_progress else None
    q_scope = MemoryScope(repo=item.query_repo) if item.query_repo else None
    c_scope = MemoryScope(repo=item.candidate_repo) if item.candidate_repo else None
    return WardenContext(
        candidate_id=item.id, belief_score=score, evidence=evidence,
        intent=QueryIntent(item.intent), retrieval_stats=stats,
        query_scope=q_scope, candidate_scope=c_scope,
    )


@dataclass
class WardenFixture:
    name: str
    description: str
    items: list[WardenItem] = field(default_factory=list)

    @classmethod
    def from_file(cls, path: str | Path) -> "WardenFixture":
        with open(path) as h:
            d = json.load(h)
        return cls(name=d.get("name", "unnamed"), description=d.get("description", ""),
                   items=[WardenItem.from_dict(i) for i in d.get("items", [])])


def _chain_for(condition: str) -> WardenChain:
    if condition == "currentness_only":
        return WardenChain([CurrentnessWarden()])
    if condition == "exhaustion_only":
        return WardenChain([ExhaustionWarden()])
    if condition == "scope_only":
        return WardenChain([ScopeWarden()])
    return WardenChain([CurrentnessWarden(), ExhaustionWarden(), ScopeWarden()])


class WardenBenchRunner:
    def __init__(self, fixture: WardenFixture) -> None:
        self.fixture = fixture

    def run_condition(self, condition: str) -> dict[str, float]:
        chain = _chain_for(condition)
        should_refuse = [i for i in self.fixture.items if not i.gold_admit]
        should_admit = [i for i in self.fixture.items if i.gold_admit]
        kept_out = sum(1 for i in should_refuse if chain.evaluate(_context(i)).decision is not WardenDecision.ADMIT)
        admitted = sum(1 for i in should_admit if chain.evaluate(_context(i)).decision is WardenDecision.ADMIT)
        return {
            "refuse_recall": round(kept_out / len(should_refuse), 4) if should_refuse else 1.0,
            "admit_retention": round(admitted / len(should_admit), 4) if should_admit else 1.0,
        }

    def run(self) -> dict:
        results = {c: self.run_condition(c) for c in CONDITIONS}
        gate = evaluate_win_gate(results)
        return {
            "fixture": self.fixture.name, "description": self.fixture.description,
            "config": {"n_items": len(self.fixture.items), "conditions": list(CONDITIONS)},
            "conditions": {c: {"metrics": m} for c, m in results.items()},
            "win_gate": gate,
        }


def evaluate_win_gate(results: dict[str, dict[str, float]]) -> dict:
    """The chain graduates if its refuse_recall beats every single warden, admit_retention 1.0."""
    if "chain" not in results:
        return {"graduates": False, "reason": "missing chain condition"}
    chain = results["chain"]
    singles = {c: m for c, m in results.items() if c != "chain"}
    best_single = max((m["refuse_recall"] for m in singles.values()), default=0.0)
    graduates = chain["refuse_recall"] > best_single and chain["admit_retention"] >= 1.0
    return {
        "graduates": graduates,
        "chain_refuse_recall": chain["refuse_recall"],
        "best_single_refuse_recall": best_single,
        "chain_admit_retention": chain["admit_retention"],
        "singles": {c: m["refuse_recall"] for c, m in singles.items()},
    }
