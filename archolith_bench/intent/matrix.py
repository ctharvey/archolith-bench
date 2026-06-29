"""Intent x ContentRole affinity matrix + the multi-hit reduction (menhir IntentOracle).

The matrix is the single data-driven extension point: adding a task = a row, adding an
artifact kind = a column, no consumer code changes (design 2 extensibility principle).

The SIGNS (PREFER / NEUTRAL / PENALIZE / IGNORE) are the human-authored contract
(design 4). The WEIGHT MAGNITUDES are the bench's first calibration — the design left
them open precisely so this Phase 4 bench sets them; they are not load-bearing for the
sign of the effect, only its strength.

Multi-hit (design 4A): for several matched intents and/or several candidate roles, the
affinity is the MAX over the cross-product ("most-helpful-wins" — the ranking dual of
the WardenChain's most-restrictive-wins).

Bench prototype of menhir's `domain/intent_affinity.py`.
"""

from __future__ import annotations

from enum import Enum

from .classifier import TaskIntent
from .roles import ContentRole


class Affinity(str, Enum):
    PREFER = "prefer"
    NEUTRAL = "neutral"
    PENALIZE = "penalize"
    IGNORE = "ignore"


# Ranking order for the max reduction (PREFER beats NEUTRAL beats PENALIZE beats IGNORE).
_RANK: dict[Affinity, int] = {
    Affinity.IGNORE: 0,
    Affinity.PENALIZE: 1,
    Affinity.NEUTRAL: 2,
    Affinity.PREFER: 3,
}

# Bench-calibrated magnitudes (the design's open item). Map an affinity to a relevance
# weight in [0, 1] that the IntentOracle emits as its probability.
_WEIGHT: dict[Affinity, float] = {
    Affinity.PREFER: 1.0,
    Affinity.NEUTRAL: 0.25,
    Affinity.PENALIZE: 0.05,
    Affinity.IGNORE: 0.0,
}

# Shorthand for authoring the table (G = iGnore; avoids the ambiguous bare `I`).
P, N, X, G = Affinity.PREFER, Affinity.NEUTRAL, Affinity.PENALIZE, Affinity.IGNORE

# Column order for readability (must match the dict keys below).
_ROLES: tuple[ContentRole, ...] = (
    ContentRole.FAILURE, ContentRole.INCIDENT, ContentRole.DECISION, ContentRole.EXPERIMENT,
    ContentRole.BENCHMARK, ContentRole.TEST, ContentRole.PLAN, ContentRole.RUNBOOK,
    ContentRole.EVIDENCE, ContentRole.REFERENCE,
)

# The 8 x 10 affinity matrix (design 4). Rows = task intent, columns = _ROLES order.
_ROWS: dict[TaskIntent, tuple[Affinity, ...]] = {
    #                         FAIL INC  DEC  EXP  BEN  TST  PLN  RUN  EVD  REF
    TaskIntent.DEBUG_FAILURE:     (P,  P,   N,   N,   X,   P,   X,   P,   P,   X),
    TaskIntent.AVOID_REPEAT:      (P,  N,   P,   P,   P,   N,   X,   X,   N,   X),
    TaskIntent.EXPLAIN_DECISION:  (N,  N,   P,   P,   P,   X,   X,   X,   P,   N),
    TaskIntent.VERIFY_CURRENTNESS:(N,  X,   N,   N,   P,   P,   X,   N,   P,   P),
    TaskIntent.EVIDENCE_LOOKUP:   (N,  X,   N,   N,   P,   P,   X,   X,   P,   X),
    TaskIntent.CHANGE_ANALYSIS:   (P,  P,   N,   N,   N,   P,   X,   X,   P,   X),
    TaskIntent.PLAN_NEXT_ACTION:  (P,  N,   P,   P,   N,   X,   P,   N,   X,   X),
    TaskIntent.UNDERSTAND_SYSTEM: (N,  X,   N,   N,   N,   X,   N,   N,   X,   P),
}

INTENT_ROLE_MATRIX: dict[TaskIntent, dict[ContentRole, Affinity]] = {
    intent: dict(zip(_ROLES, row)) for intent, row in _ROWS.items()
}

# Status routing: which temporal QueryIntent each task intent selects (design 4).
#   AVOID_REPEAT       -> historical : the past attempt IS the answer (boost superseded).
#   VERIFY_CURRENTNESS -> any        : surface current + superseded side by side for the
#                                      drift check, WITHOUT boosting the stale one (design's
#                                      CONFLICT lens; "any" is the bench combiner's neutral
#                                      lens — it neither suppresses nor lifts superseded).
#   everything else    -> current    : superseded suppressed as today.
_STATUS_LENS: dict[TaskIntent, str] = {
    TaskIntent.AVOID_REPEAT: "historical",
    TaskIntent.VERIFY_CURRENTNESS: "any",
}
# History-wanting lens wins when intents disagree (design 4A): historical > any > current.
_LENS_PRIORITY: tuple[str, ...] = ("historical", "any", "current")


def affinity(intent: TaskIntent, role: ContentRole) -> Affinity:
    return INTENT_ROLE_MATRIX[intent][role]


def affinity_to_weight(a: Affinity) -> float:
    return _WEIGHT[a]


def resolve_affinity(
    intents: list[TaskIntent], roles: set[ContentRole]
) -> tuple[Affinity, TaskIntent, ContentRole]:
    """Max affinity over (intents x roles) — most-helpful-wins (design 4A).

    Returns the winning affinity and the (intent, role) pair that produced it, for the
    explainable rationale."""
    best: tuple[Affinity, TaskIntent, ContentRole] | None = None
    for intent in intents:
        row = INTENT_ROLE_MATRIX[intent]
        for role in roles:
            a = row[role]
            if best is None or _RANK[a] > _RANK[best[0]]:
                best = (a, intent, role)
    if best is None:  # no intents/roles supplied
        return Affinity.NEUTRAL, TaskIntent.UNDERSTAND_SYSTEM, ContentRole.REFERENCE
    return best


def task_intents_to_query_intent(intents: list[TaskIntent]) -> str:
    """Select the temporal lens; the history-wanting lens wins on conflict (design 4A)."""
    selected = {_STATUS_LENS.get(i, "current") for i in intents}
    for lens in _LENS_PRIORITY:
        if lens in selected:
            return lens
    return "current"
