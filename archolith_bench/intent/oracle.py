"""IntentOracle — task-intent-aware relevance (menhir R6 addition, Phase 4 prototype).

A pure-relevance oracle (NOT a Warden — design 0 pairing rule): it reads the query's task
intent and the candidate's content role and emits a RELEVANCE OracleResult whose
probability is the intent->role affinity. It NEVER contradicts (a wrong-role-for-task hit
is less helpful, not unsafe) — so it lifts the relevance *band* of task-appropriate
artifacts and lets the other oracles order within the band.

It plugs into the existing combiner as one more capped source family ("intent"); no
combiner change. The classifier also selects the temporal lens (see runner), so
lifecycle status stays owned by the temporal producer — no second supersession logic.
"""

from __future__ import annotations

from archolith_bench.oracle.models import (
    CandidateMemory,
    OraclePolarity,
    OracleResult,
    OracleTarget,
    QueryContext,
)

from .classifier import IntentConfidence, TaskIntent, classify_intent
from .matrix import affinity_to_weight, resolve_affinity
from .roles import derive_content_role


class IntentOracle:
    """Emits intent->role affinity as a RELEVANCE signal. Read-only, deterministic."""

    name = "intent"
    source_family = "intent"

    def __init__(self, forced_intent: TaskIntent | None = None) -> None:
        # `forced_intent` overrides classification — used by the bench shuffle-ablation
        # arm to feed a deliberately wrong intent and prove the lift is the real signal.
        self.forced_intent = forced_intent

    def evaluate(self, query: QueryContext, candidate: CandidateMemory) -> OracleResult:
        if self.forced_intent is not None:
            intents = [self.forced_intent]
        else:
            hits, confidence = classify_intent(query.text)
            if confidence is IntentConfidence.LOW:
                # Unclassifiable -> stay neutral, never distort baseline (missing != falsity).
                return OracleResult(
                    oracle=self.name, probability=0.25, confidence=0.5,
                    polarity=OraclePolarity.NEUTRAL, target=OracleTarget.RELEVANCE,
                    source_family=self.source_family, note="low-confidence intent -> neutral",
                )
            intents = [h.intent for h in hits]

        roles = derive_content_role(candidate.metadata)
        aff, win_intent, win_role = resolve_affinity(intents, roles)
        weight = affinity_to_weight(aff)
        polarity = OraclePolarity.SUPPORT if weight > 0 else OraclePolarity.NEUTRAL
        return OracleResult(
            oracle=self.name, probability=weight, confidence=1.0,
            polarity=polarity, target=OracleTarget.RELEVANCE,
            source_family=self.source_family,
            note=f"{win_intent.value}:{win_role.value}={aff.value} w={weight:.2f}",
        )
