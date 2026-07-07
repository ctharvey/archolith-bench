"""Intent-aware retrieval benchmark (menhir IntentOracle, Phase 4).

Bench-first prototype of menhir's intent-aware retrieval: a deterministic (no-LLM)
classifier + content-role deriver + intent x role affinity matrix, surfaced as an
IntentOracle that plugs into the existing oracle combiner as one capped RELEVANCE
family. The runner falsifies the claim "intent changes the top artifact for the right
reason" with four arms (baseline / intent_on / shuffle / no_harm).

This package becomes the spec for menhir Phase 1 (`domain/query_intent.py`,
`domain/artifact_role.py`, `domain/intent_affinity.py`). Nothing here touches menhir
production.
"""

from .classifier import IntentConfidence, IntentHit, TaskIntent, classify_intent, primary_intent
from .matrix import (
    INTENT_ROLE_MATRIX,
    Affinity,
    affinity,
    affinity_to_weight,
    resolve_affinity,
    task_intents_to_query_intent,
)
from .models import IntentFixture, IntentMemory, IntentQuery
from .oracle import IntentOracle
from .roles import ContentRole, derive_content_role
from .runner import IntentBenchmarkRunner
from .validate import Finding, has_errors, validate_intent_fixture

__all__ = [
    "TaskIntent", "IntentConfidence", "IntentHit", "classify_intent", "primary_intent",
    "ContentRole", "derive_content_role",
    "Affinity", "INTENT_ROLE_MATRIX", "affinity", "affinity_to_weight",
    "resolve_affinity", "task_intents_to_query_intent",
    "IntentMemory", "IntentQuery", "IntentFixture",
    "IntentOracle", "IntentBenchmarkRunner",
    "Finding", "validate_intent_fixture", "has_errors",
]
