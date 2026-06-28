"""Cheap retrieval oracles (menhir R6) + the RetrievalOracle protocol (R4).

Each oracle reads ONE class of evidence over a prefetched candidate snapshot and
returns an `OracleResult` (evidence, never final truth). All oracles are stateless
and pure, so the executor can reduce them deterministically.

The cheap set (per the ladder's R6 rung):
- SemanticOracle   — lexical-overlap stand-in for embedding similarity (RELEVANCE).
- StructureOracle  — file/symbol/test overlap (RELEVANCE; recovers buried memories).
- ScopeOracle      — repo/branch/project/namespace agreement (SCOPE; wrong-scope guard).
- TemporalOracle   — valid/invalid/as-of vs intent (CURRENTNESS / HISTORICALITY).
- EvidenceOracle   — provenance strength scales confidence/directness (RELEVANCE).

Heavier oracles (Git over commit ranges, Belief over scorer outputs, pairwise
Contradiction for amplification) are deliberately out of this first cut — they need
budgets/snapshots and, for pairwise, the R11 amplification loop.
"""

from __future__ import annotations

from typing import Protocol

from .models import (
    INFERRED_EVIDENCE,
    SCOPE_KEYS,
    STALE_BUCKETS,
    STRONG_EVIDENCE,
    CandidateMemory,
    OraclePolarity,
    OracleResult,
    OracleTarget,
    QueryContext,
)


class RetrievalOracle(Protocol):
    """Evaluate one evidence property of a candidate for a query. Read-only."""

    name: str
    source_family: str

    def evaluate(self, query: QueryContext, candidate: CandidateMemory) -> OracleResult: ...


def _tokens(text: str) -> set[str]:
    return {t for t in "".join(c.lower() if c.isalnum() else " " for c in text).split() if len(t) > 1}


def _overlap_coefficient(a: set[str], b: set[str]) -> float:
    """|a ∩ b| / min(|a|, |b|) — robust to length mismatch between query and memory."""
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


def _jaccard(a: set[object], b: set[object]) -> float:
    if not a and not b:
        return 0.0
    union = a | b
    return len(a & b) / len(union) if union else 0.0


class SemanticOracle:
    """Lexical-overlap stand-in for embedding similarity (deterministic).

    Swap a real embedding scorer in here before quoting semantic numbers — this is
    the same honest stand-in discipline the facet bench uses.
    """

    name = "semantic"
    source_family = "semantic"

    def evaluate(self, query: QueryContext, candidate: CandidateMemory) -> OracleResult:
        sim = _overlap_coefficient(_tokens(query.text), _tokens(candidate.content))
        return OracleResult(
            oracle=self.name,
            probability=sim,
            confidence=1.0,
            polarity=OraclePolarity.SUPPORT if sim > 0 else OraclePolarity.NEUTRAL,
            target=OracleTarget.RELEVANCE,
            source_family=self.source_family,
            note=f"lexical_overlap={sim:.2f}",
        )


class StructureOracle:
    """File/symbol/test overlap — structural relevance independent of wording.

    This is what recovers a memory that embedding similarity buries: if the query
    and candidate touch the same symbol/test, that is strong relevance evidence
    even when the prose does not match.
    """

    name = "structure"
    source_family = "structure"

    def evaluate(self, query: QueryContext, candidate: CandidateMemory) -> OracleResult:
        q = set(query.files) | set(query.symbols) | set(query.tests)
        c = (
            set(candidate.metadata.get("files", ()))
            | set(candidate.metadata.get("symbols", ()))
            | set(candidate.metadata.get("tests", ()))
        )
        score = _overlap_coefficient(q, c) if q and c else 0.0
        return OracleResult(
            oracle=self.name,
            probability=score,
            confidence=1.0,
            polarity=OraclePolarity.SUPPORT if score > 0 else OraclePolarity.MISSING,
            target=OracleTarget.RELEVANCE,
            source_family=self.source_family,
            note=f"structure_overlap={score:.2f}",
        )


class ScopeOracle:
    """Repo/branch/project/namespace agreement — the wrong-scope contamination guard.

    A disagreement on any set scope key (both sides specified, values differ) is a
    CONTRADICT on the SCOPE target; full agreement is mild SUPPORT.
    """

    name = "scope"
    source_family = "scope"

    def evaluate(self, query: QueryContext, candidate: CandidateMemory) -> OracleResult:
        compared = 0
        conflicts = 0
        for key in SCOPE_KEYS:
            q_val = getattr(query, key)
            c_val = candidate.metadata.get(key)
            if q_val and c_val:
                compared += 1
                if q_val != c_val:
                    conflicts += 1
        if compared == 0:
            return OracleResult(
                oracle=self.name, probability=0.0, confidence=0.5,
                polarity=OraclePolarity.MISSING, target=OracleTarget.SCOPE,
                source_family=self.source_family, note="no_shared_scope_keys",
            )
        if conflicts:
            # scope_match stays 1.0: it downweights OTHER oracles' evidence, not this
            # oracle's own verdict — the conflict strength is carried by `probability`.
            return OracleResult(
                oracle=self.name, probability=conflicts / compared, confidence=1.0,
                polarity=OraclePolarity.CONTRADICT, target=OracleTarget.SCOPE,
                source_family=self.source_family,
                note=f"scope_conflict={conflicts}/{compared}",
            )
        return OracleResult(
            oracle=self.name, probability=1.0, confidence=1.0,
            polarity=OraclePolarity.SUPPORT, target=OracleTarget.SCOPE,
            source_family=self.source_family, note="scope_match",
        )


class TemporalOracle:
    """Currentness vs historicality keyed on valid/invalid/as-of and query intent.

    - current intent + stale candidate  -> CONTRADICT on CURRENTNESS (suppress).
    - historical intent + stale candidate -> SUPPORT on HISTORICALITY (keep it).
    - otherwise (live candidate)         -> mild SUPPORT on CURRENTNESS.

    "stale" = explicitly superseded / non-current belief bucket, or invalid_at is
    set and on/before the query's as_of_time (lexical ISO compare).
    """

    name = "temporal"
    source_family = "temporal"

    def evaluate(self, query: QueryContext, candidate: CandidateMemory) -> OracleResult:
        stale = self._is_stale(query, candidate)
        if query.intent == "historical":
            if stale:
                return OracleResult(
                    oracle=self.name, probability=1.0, confidence=0.9,
                    polarity=OraclePolarity.SUPPORT, target=OracleTarget.HISTORICALITY,
                    source_family=self.source_family, note="historical_query_historical_memory",
                )
            return OracleResult(
                oracle=self.name, probability=0.3, confidence=0.6,
                polarity=OraclePolarity.NEUTRAL, target=OracleTarget.HISTORICALITY,
                source_family=self.source_family, note="historical_query_current_memory",
            )
        # current / any intent
        if stale:
            return OracleResult(
                oracle=self.name, probability=1.0, confidence=0.9,
                polarity=OraclePolarity.CONTRADICT, target=OracleTarget.CURRENTNESS,
                source_family=self.source_family, note="stale_under_current_intent",
            )
        return OracleResult(
            oracle=self.name, probability=0.6, confidence=0.7,
            polarity=OraclePolarity.SUPPORT, target=OracleTarget.CURRENTNESS,
            source_family=self.source_family, note="live_at_as_of",
        )

    @staticmethod
    def _is_stale(query: QueryContext, candidate: CandidateMemory) -> bool:
        if candidate.metadata.get("superseded"):
            return True
        if candidate.metadata.get("belief_bucket") in STALE_BUCKETS:
            return True
        invalid_at = candidate.metadata.get("invalid_at")
        if invalid_at and query.as_of_time and str(invalid_at) <= str(query.as_of_time):
            return True
        return False


class EvidenceOracle:
    """Provenance strength: strong evidence raises confidence/directness; inference lowers it.

    Missing evidence is NOT contradiction — it returns a MISSING polarity that raises
    uncertainty downstream rather than suppressing the candidate.
    """

    name = "evidence"
    source_family = "evidence"

    def evaluate(self, query: QueryContext, candidate: CandidateMemory) -> OracleResult:
        kinds = set(candidate.metadata.get("evidence_kinds", ()))
        if not kinds:
            return OracleResult(
                oracle=self.name, probability=0.0, confidence=0.3,
                polarity=OraclePolarity.MISSING, target=OracleTarget.RELEVANCE,
                directness=0.3, source_family=self.source_family, note="no_evidence",
            )
        strong = bool(kinds & STRONG_EVIDENCE)
        only_inferred = kinds <= INFERRED_EVIDENCE
        directness = 1.0 if strong else (0.4 if only_inferred else 0.7)
        confidence = 1.0 if strong else (0.5 if only_inferred else 0.7)
        return OracleResult(
            oracle=self.name,
            probability=1.0 if strong else 0.5,
            confidence=confidence,
            polarity=OraclePolarity.SUPPORT,
            target=OracleTarget.RELEVANCE,
            directness=directness,
            source_family=self.source_family,
            note=f"evidence={','.join(sorted(kinds))}",
        )


def default_oracles() -> list[RetrievalOracle]:
    """The cheap oracle set, in deterministic priority order."""
    return [SemanticOracle(), StructureOracle(), ScopeOracle(), TemporalOracle(), EvidenceOracle()]
