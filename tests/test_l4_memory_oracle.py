"""Tests for the read-only MemoryOracle."""

from __future__ import annotations

from archolith_bench.l4.memory_oracle import ArtifactMatch, MemoryOracle
from archolith_bench.l4.models import Artifact, ArtifactType, Evidence, Source, Status

_EV = [Evidence(kind="git", ref="e8da67d")]


def _corpus() -> list[Artifact]:
    return [
        Artifact(id="floor_fail", type=ArtifactType.FAILURE,
                 summary="fixed cosine similarity floor dropped facet candidates",
                 status=Status.TRUSTED, source=Source.HUMAN, evidence=_EV, anchors=["scoring_service.py"]),
        Artifact(id="lease_inc", type=ArtifactType.INCIDENT,
                 summary="force_acquire overwrote an active scheduler lease",
                 status=Status.TRUSTED, source=Source.HUMAN, evidence=_EV, anchors=["scheduler_lease.py"]),
        Artifact(id="old_floor", type=ArtifactType.DECISION,
                 summary="use a fixed cosine floor", status=Status.HISTORICAL, source=Source.HUMAN,
                 evidence=_EV, anchors=["scoring_service.py"], superseded_by="floor_fail"),
    ]


def test_anchor_match_is_strong_and_deterministic() -> None:
    oracle = MemoryOracle(_corpus())
    hits = oracle.find(text="tighten the similarity floor", anchors=["scoring_service.py"])
    ids = [h.artifact.id for h in hits]
    assert "floor_fail" in ids
    assert "lease_inc" not in ids  # different anchor, no topic overlap
    assert all(isinstance(h, ArtifactMatch) for h in hits)
    # anchor+topic outscores topic-only
    top = hits[0]
    assert "anchor" in top.matched_on


def test_returns_historical_with_status_intact() -> None:
    oracle = MemoryOracle(_corpus())
    hits = oracle.find(text="cosine floor", anchors=["scoring_service.py"])
    by_id = {h.artifact.id: h for h in hits}
    assert "old_floor" in by_id
    assert by_id["old_floor"].artifact.is_historical  # surfaced, status intact — brief decides presentation


def test_no_match_returns_empty() -> None:
    oracle = MemoryOracle(_corpus())
    assert oracle.find(text="completely unrelated topic about penguins") == []


def test_oracle_has_no_write_surface() -> None:
    # invariants 1 & 2: the oracle never writes.
    oracle = MemoryOracle(_corpus())
    for forbidden in ("create", "promote", "supersede"):
        assert not hasattr(oracle, forbidden)
