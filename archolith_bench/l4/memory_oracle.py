"""MemoryOracle — read-only retrieval of L4 artifacts for a task (bench-first).

Given a task (text + optional structural anchors) it returns the artifacts relevant
to it as `ArtifactMatch`es. It is READ-ONLY by construction (invariant 1): it holds a
copy of the artifact list and exposes no create/promote/supersede — only the
ArtifactMutator writes (invariant 2).

Matching is deliberately simple and explainable for v0:
- structural ANCHOR overlap (deterministic) — strong signal;
- topic token overlap (a lexical stand-in for embedding similarity) — weak signal.

It returns historical/candidate artifacts too (with their status intact); deciding how
to *present* them — fact vs hypothesis, flagged-stale — is the ColdStartBrief's job, not
the oracle's.
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import Artifact


def _tokens(text: str) -> set[str]:
    return {t for t in "".join(c.lower() if c.isalnum() else " " for c in text).split() if len(t) > 1}


def _overlap_coefficient(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


@dataclass(frozen=True)
class ArtifactMatch:
    artifact: Artifact
    score: float
    matched_on: tuple[str, ...]  # subset of {"anchor", "topic"}


class MemoryOracle:
    """Read-only artifact retrieval. Never writes (invariants 1 & 2)."""

    def __init__(self, artifacts: list[Artifact]) -> None:
        self._artifacts = list(artifacts)

    def find(self, *, text: str, anchors: list[str] | None = None, limit: int = 10) -> list[ArtifactMatch]:
        q_tokens = _tokens(text)
        q_anchors = set(anchors or [])
        matches: list[ArtifactMatch] = []
        for art in self._artifacts:
            matched: list[str] = []
            score = 0.0
            if q_anchors & set(art.anchors):
                matched.append("anchor")   # deterministic, strong
                score += 1.0
            topic = _overlap_coefficient(q_tokens, _tokens(f"{art.summary} {art.body}"))
            if topic > 0:
                matched.append("topic")
                score += topic
            if matched:
                matches.append(ArtifactMatch(artifact=art, score=round(score, 4), matched_on=tuple(matched)))
        matches.sort(key=lambda m: (-m.score, m.artifact.id))
        return matches[:limit]
