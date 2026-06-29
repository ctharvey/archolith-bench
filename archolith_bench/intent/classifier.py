"""Deterministic task-intent classifier (menhir IntentOracle, Phase 4 bench prototype).

No LLM. An ordered keyword cascade that returns the *set* of task intents whose
signature cue matched (multi-hit, design 4A), each with the literal cue for
explainability. Precedence orders only the primary label; affinity maxes over the
whole set downstream, so precedence is not load-bearing for ranking.

This is the bench-first prototype of menhir's `domain/query_intent.py`; the menhir
port (Phase 1) reproduces this contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class TaskIntent(str, Enum):
    """What the caller is trying to accomplish (the task axis, orthogonal to temporal)."""

    DEBUG_FAILURE = "debug_failure"
    AVOID_REPEAT = "avoid_repeat"
    EXPLAIN_DECISION = "explain_decision"
    VERIFY_CURRENTNESS = "verify_currentness"
    EVIDENCE_LOOKUP = "evidence_lookup"
    CHANGE_ANALYSIS = "change_analysis"
    PLAN_NEXT_ACTION = "plan_next_action"
    UNDERSTAND_SYSTEM = "understand_system"  # default / orientation


class IntentConfidence(str, Enum):
    HIGH = "high"   # a signature cue matched
    LOW = "low"     # bare default; do not distort ranking


# Precedence is for the PRIMARY label only (most specific first). Affinity maxes over
# the whole matched set, so this ordering does not change rankings.
_PRECEDENCE: tuple[TaskIntent, ...] = (
    TaskIntent.AVOID_REPEAT,
    TaskIntent.DEBUG_FAILURE,
    TaskIntent.EXPLAIN_DECISION,
    TaskIntent.VERIFY_CURRENTNESS,
    TaskIntent.EVIDENCE_LOOKUP,
    TaskIntent.CHANGE_ANALYSIS,
    TaskIntent.PLAN_NEXT_ACTION,
    TaskIntent.UNDERSTAND_SYSTEM,
)

# Signature cues per intent (lowercase substring match). Authored contract; cues are
# chosen to be specific to the task, not to the topic vocabulary.
_CUES: dict[TaskIntent, tuple[str, ...]] = {
    TaskIntent.AVOID_REPEAT: (
        "already tried", "have we tried", "did we try", "have we already",
        "tried before", "previously attempted", "already done", "tried again",
    ),
    TaskIntent.DEBUG_FAILURE: (
        "failing", "failed", "fails", "error", "errors", "crash", "broken",
        "not working", "stack trace", "traceback", "exception", "why is", "throwing",
    ),
    TaskIntent.EXPLAIN_DECISION: (
        "why did we", "why do we", "why was", "rationale", "reason for",
        "reason we", "chose", "choose", "decided", "decision to",
    ),
    TaskIntent.VERIFY_CURRENTNESS: (
        "still", "up to date", "out of date", "outdated", "stale",
        "still accurate", "still valid", "still the case",
    ),
    TaskIntent.EVIDENCE_LOOKUP: (
        "which benchmark", "which test", "what verifies", "what proves",
        "proof of", "evidence for", "what covers", "backed by",
    ),
    TaskIntent.CHANGE_ANALYSIS: (
        "what changed", "blast radius", "what depends", "depends on",
        "impact of", "since commit", "what broke after", "diff",
    ),
    TaskIntent.PLAN_NEXT_ACTION: (
        "what next", "next step", "what should i", "what do i do",
        "how do i", "do next", "what now",
    ),
    TaskIntent.UNDERSTAND_SYSTEM: (
        "how does", "what is", "explain how", "how do", "what are", "overview of",
    ),
}


@dataclass(frozen=True)
class IntentHit:
    intent: TaskIntent
    cue: str


def classify_intent(text: str) -> tuple[list[IntentHit], IntentConfidence]:
    """Return every task intent whose cue matched, plus a confidence.

    Multi-hit: a query can carry several intents (design 4A). The list is ordered by
    precedence for a stable primary label. If nothing matches, the default is
    UNDERSTAND_SYSTEM at LOW confidence (so the oracle stays neutral)."""
    lowered = text.lower()
    hits: list[IntentHit] = []
    for intent in _PRECEDENCE:
        for cue in _CUES[intent]:
            if cue in lowered:
                hits.append(IntentHit(intent, cue))
                break  # one cue per intent is enough to flag it
    if not hits:
        return [IntentHit(TaskIntent.UNDERSTAND_SYSTEM, "")], IntentConfidence.LOW
    # HIGH if any non-default intent fired; a lone UNDERSTAND match is still HIGH
    # (an explicit "how does X work" is a real classification), the bare default is LOW.
    return hits, IntentConfidence.HIGH


def primary_intent(hits: list[IntentHit]) -> TaskIntent:
    """The highest-precedence matched intent (the display/log label)."""
    return hits[0].intent if hits else TaskIntent.UNDERSTAND_SYSTEM
