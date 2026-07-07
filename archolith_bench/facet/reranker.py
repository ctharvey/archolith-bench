"""`MeetPointReranker` — convergence scoring over shared support structure.

From the R2 plan:

    meet_score =
        weighted required-facet overlap
      + file/symbol/test convergence
      + evidence/source convergence
      + time-window compatibility
      - stale/superseded penalty
      - wrong-scope penalty

Every candidate emits a `MeetPointExplanation`: which facets matched, which
penalties fired, and why it ranked where it did. Determinism + explainability
are invariants here, not extras — ranking is a stable sort on (−score, id).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .models import SCOPE_FACETS, STALE_BUCKETS, Memory, MemoryFacetSet, Query


@dataclass
class MeetPointWeights:
    """Tunable weights for the meet-point score.

    Penalties are large relative to bonuses on purpose: the whole point of R2 is
    to *suppress* stale and wrong-scope injection even when a candidate has high
    surface overlap. These are seams for the bench to sweep, not tuned values.
    """

    required_facet: float = 2.0
    file_symbol_test: float = 1.5
    evidence_source: float = 1.0
    time_compatible: float = 1.0
    stale_penalty: float = 4.0
    wrong_scope_penalty: float = 5.0


# Facets that count toward "required-facet overlap" when a query does not name an
# explicit `required_facets` list. Scope + what-was-done + what-it-was-about.
_DEFAULT_REQUIRED: tuple[str, ...] = ("repo", "project", "namespace", "operation", "object", "symbol")

# Facets whose value overlap counts as file/symbol/test convergence.
_CONVERGENCE_FACETS: tuple[str, ...] = ("file", "symbol", "test")


@dataclass
class MeetPointExplanation:
    """Per-candidate trace of how the meet-point score was assembled."""

    memory_id: str
    score: float = 0.0
    matched_required: list[str] = field(default_factory=list)
    convergence: dict[str, list[str]] = field(default_factory=dict)
    evidence_overlap: list[str] = field(default_factory=list)
    time_compatible: bool = False
    penalties: list[str] = field(default_factory=list)
    rank: int = 0

    def to_dict(self) -> dict:
        return {
            "memory_id": self.memory_id,
            "score": round(self.score, 4),
            "rank": self.rank,
            "matched_required": self.matched_required,
            "convergence": self.convergence,
            "evidence_overlap": self.evidence_overlap,
            "time_compatible": self.time_compatible,
            "penalties": self.penalties,
        }


class MeetPointReranker:
    """Score facet-overlap candidates by convergence; emit explanation traces."""

    def __init__(self, weights: MeetPointWeights | None = None) -> None:
        self.weights = weights or MeetPointWeights()

    def score(self, query: Query, memory: Memory) -> MeetPointExplanation:
        """Compute the meet-point score + trace for one candidate memory."""
        weights = self.weights
        qf = query.facets
        mf = memory.facets
        exp = MeetPointExplanation(memory_id=memory.id)
        score = 0.0

        required = query.required_facets or [f for f in _DEFAULT_REQUIRED if qf.values(f)]
        for facet in required:
            if _facet_overlaps(qf, mf, facet):
                score += weights.required_facet
                exp.matched_required.append(facet)

        for facet in _CONVERGENCE_FACETS:
            shared = sorted(qf.values(facet) & mf.values(facet))
            if shared:
                exp.convergence[facet] = shared
                score += weights.file_symbol_test * len(shared)

        evidence_shared = sorted(qf.values("evidence_type") & mf.values("evidence_type"))
        if evidence_shared:
            exp.evidence_overlap.extend(evidence_shared)
        if qf.source_id and qf.source_id == mf.source_id:
            exp.evidence_overlap.append(f"source_id={mf.source_id}")
        if exp.evidence_overlap:
            score += weights.evidence_source * len(exp.evidence_overlap)

        if _time_compatible(qf, mf):
            exp.time_compatible = True
            score += weights.time_compatible

        # --- penalties ---------------------------------------------------------
        if query.intent == "current" and memory.is_stale:
            score -= weights.stale_penalty
            bucket = mf.belief_bucket if mf.belief_bucket in STALE_BUCKETS else "superseded"
            exp.penalties.append(f"stale:{bucket}")

        for facet in SCOPE_FACETS:
            q_val = getattr(qf, facet)
            m_val = getattr(mf, facet)
            if q_val and m_val and q_val != m_val:
                score -= weights.wrong_scope_penalty
                exp.penalties.append(f"wrong_scope:{facet}({m_val}!={q_val})")

        exp.score = score
        return exp

    def rerank(
        self, query: Query, candidate_ids: list[str], memories_by_id: dict[str, Memory]
    ) -> list[MeetPointExplanation]:
        """Score candidates and return explanations sorted by (−score, id).

        Unknown candidate ids are skipped silently — the index and the corpus are
        expected to agree, but a stray id should never crash a benchmark run.
        """
        explanations = [
            self.score(query, memories_by_id[cid]) for cid in candidate_ids if cid in memories_by_id
        ]
        explanations.sort(key=lambda e: (-e.score, e.memory_id))
        for rank, exp in enumerate(explanations, start=1):
            exp.rank = rank
        return explanations

    def ranked_ids(
        self, query: Query, candidate_ids: list[str], memories_by_id: dict[str, Memory]
    ) -> list[str]:
        """Convenience: just the reranked memory ids, best first."""
        return [exp.memory_id for exp in self.rerank(query, candidate_ids, memories_by_id)]


def _facet_overlaps(qf: MemoryFacetSet, mf: MemoryFacetSet, facet: str) -> bool:
    """True if query and candidate share any value on `facet`."""
    return bool(qf.values(facet) & mf.values(facet))


def _time_compatible(qf: MemoryFacetSet, mf: MemoryFacetSet) -> bool:
    """A candidate's fact must hold at or before the query's as-of time.

    ISO-8601 strings in the same format sort chronologically, so a lexical
    comparison is sufficient. If either side lacks `valid_time`, the time signal
    is neutral (not compatible, not penalized).
    """
    if not qf.valid_time or not mf.valid_time:
        return False
    return mf.valid_time <= qf.valid_time
