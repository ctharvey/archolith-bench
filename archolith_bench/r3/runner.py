"""R3 belief-currentness ladder + win gate.

Conditions (subset of belief-layer.md's A-F, the ones that isolate the policy):
    A_assert_all      baseline strawman: assert every relevant belief as current truth
                      (no belief policy) — the poisoning case.
    C_belief_buckets  Rung-0 BeliefScorer buckets, NO intent: assert only
                      SAFE_TO_ASSERT + MENTION_WITH_UNCERTAINTY.
    D_currentness     intent-aware policy (build_intent_aware_packet): superseded
                      beliefs are routed out of current assertion (ANERGIC/HISTORICAL),
                      noise is BLOCKED.

Each condition yields two id sets per the fixture:
    asserted  — beliefs the agent would state as CURRENT TRUTH.
    surfaced  — beliefs available as context at all (anything not dropped/blocked).

Metrics (lower better unless noted):
    stale_current_assertion_rate    asserted beliefs that are NOT gold-current / asserted
    poisoned_context_injection_rate surfaced beliefs that are noise / surfaced
    historical_context_preservation gold-historical beliefs surfaced / gold-historical (HIGHER)

Win gate: D cuts stale_current_assertion_rate vs A_assert_all WITHOUT losing
historical_context_preservation (within tolerance).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from menhir.domain.belief import (
    BeliefCandidate,
    BeliefCandidateType,
    BeliefHead,
    BeliefScorer,
    QueryIntent,
    RecallBucket,
    build_intent_aware_packet,
)

from .models import BeliefFixture, BeliefItem, to_evidence

CONDITIONS: tuple[str, ...] = ("A_assert_all", "C_belief_buckets", "D_currentness")
BASELINE_CONDITION = "A_assert_all"


def _candidate(item: BeliefItem) -> BeliefCandidate:
    return BeliefCandidate(id=item.id, statement=item.statement, candidate_type=BeliefCandidateType.FIX)


@dataclass
class ConditionResult:
    condition: str
    metrics: dict[str, float]
    asserted: list[str] = field(default_factory=list)
    surfaced: list[str] = field(default_factory=list)


class R3BenchmarkRunner:
    """Run the belief-currentness ladder over a fixture."""

    def __init__(self, fixture: BeliefFixture) -> None:
        self.fixture = fixture
        self.intent = QueryIntent(fixture.intent)
        self.scorer = BeliefScorer()

    def _asserted_surfaced(self, condition: str) -> tuple[set[str], set[str]]:
        items = self.fixture.items
        if condition == "A_assert_all":
            ids = {i.id for i in items}
            return ids, ids  # baseline asserts and surfaces everything relevant

        # score each item under the CURRENT head (asking "is this current truth?")
        scored = [(i, self.scorer.score(_candidate(i), to_evidence(i.evidence), head=BeliefHead.CURRENT)) for i in items]

        if condition == "C_belief_buckets":
            asserted = {i.id for i, s in scored if s.bucket in (RecallBucket.SAFE_TO_ASSERT, RecallBucket.MENTION_WITH_UNCERTAINTY)}
            # Rung-0 surfaces everything except DO_NOT_ASSERT (the only "drop" it has)
            surfaced = {i.id for i, s in scored if s.bucket is not RecallBucket.DO_NOT_ASSERT}
            return asserted, surfaced

        if condition == "D_currentness":
            packet = build_intent_aware_packet(
                [(s, to_evidence(i.evidence)) for i, s in scored], intent=self.intent
            )
            asserted = {s.candidate.id for s in (*packet.safe_to_assert, *packet.mention_with_uncertainty)}
            # surfaced = everything available as labeled context; BLOCKED is dropped
            surfaced = {
                s.candidate.id
                for s in (
                    *packet.safe_to_assert, *packet.mention_with_uncertainty, *packet.conflict_set,
                    *packet.historical_only, *packet.anergic_current,
                )
            }
            return asserted, surfaced

        raise ValueError(f"unknown condition: {condition}")

    def run_condition(self, condition: str) -> ConditionResult:
        asserted, surfaced = self._asserted_surfaced(condition)
        by_id = self.fixture.items_by_id

        stale = sum(1 for cid in asserted if not by_id[cid].gold_current)
        poisoned = sum(1 for cid in surfaced if by_id[cid].is_noise)
        gold_hist = {i.id for i in self.fixture.items if i.gold_historical}
        preserved = len(gold_hist & surfaced)

        metrics = {
            "stale_current_assertion_rate": round(stale / len(asserted), 4) if asserted else 0.0,
            "poisoned_context_injection_rate": round(poisoned / len(surfaced), 4) if surfaced else 0.0,
            "historical_context_preservation": round(preserved / len(gold_hist), 4) if gold_hist else 1.0,
            "asserted_count": len(asserted),
            "surfaced_count": len(surfaced),
        }
        return ConditionResult(condition=condition, metrics=metrics, asserted=sorted(asserted), surfaced=sorted(surfaced))

    def run(self) -> dict:
        results = {c: self.run_condition(c) for c in CONDITIONS}
        gate = evaluate_win_gate(results)
        return {
            "fixture": self.fixture.name,
            "description": self.fixture.description,
            "intent": self.fixture.intent,
            "config": {"n_items": len(self.fixture.items), "conditions": list(CONDITIONS)},
            "conditions": {c: {"metrics": r.metrics, "asserted": r.asserted, "surfaced": r.surfaced} for c, r in results.items()},
            "win_gate": gate,
        }


def evaluate_win_gate(results: dict[str, ConditionResult], hist_tolerance: float = 0.0) -> dict:
    """D graduates if it cuts stale_current_assertion_rate vs A_assert_all without
    losing historical_context_preservation (within tolerance)."""
    if BASELINE_CONDITION not in results or "D_currentness" not in results:
        return {"graduates": False, "reason": "missing baseline or D condition"}
    base = results[BASELINE_CONDITION].metrics
    d = results["D_currentness"].metrics

    stale_cut = round(base["stale_current_assertion_rate"] - d["stale_current_assertion_rate"], 4)
    hist_loss = round(base["historical_context_preservation"] - d["historical_context_preservation"], 4)
    poison_cut = round(base["poisoned_context_injection_rate"] - d["poisoned_context_injection_rate"], 4)

    graduates = stale_cut > 0 and hist_loss <= hist_tolerance
    return {
        "graduates": graduates,
        "stale_current_assertion_cut": stale_cut,
        "historical_preservation_loss": hist_loss,
        "poisoned_injection_cut": poison_cut,
        "hist_tolerance": hist_tolerance,
        "baseline": {k: base[k] for k in ("stale_current_assertion_rate", "historical_context_preservation", "poisoned_context_injection_rate")},
        "d_currentness": {k: d[k] for k in ("stale_current_assertion_rate", "historical_context_preservation", "poisoned_context_injection_rate")},
    }
