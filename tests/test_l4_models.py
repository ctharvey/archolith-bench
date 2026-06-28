"""Tests for the L4 artifact/evidence models."""

from __future__ import annotations

from archolith_bench.l4.models import Artifact, ArtifactType, Evidence, Source, Status


def test_evidence_roundtrip_and_structural() -> None:
    e = Evidence.from_dict({"kind": "git", "ref": "e8da67d", "directness": 1.0})
    assert e.is_structural
    assert Evidence(kind="agent_inference", ref="x").is_structural is False
    assert Evidence.from_dict(e.to_dict()) == e


def test_artifact_roundtrip() -> None:
    a = Artifact.from_dict(
        {
            "id": "f1",
            "type": "failure",
            "summary": "fixed cosine floor dropped facet candidates",
            "status": "trusted",
            "source": "human",
            "evidence": [{"kind": "git", "ref": "e8da67d"}, {"kind": "test", "ref": "test_scoring"}],
            "anchors": ["scoring_service.py"],
        }
    )
    assert a.type is ArtifactType.FAILURE
    assert a.status is Status.TRUSTED
    assert a.source is Source.HUMAN
    assert a.has_evidence
    assert a.is_trusted
    # round-trips
    assert Artifact.from_dict(a.to_dict()).to_dict() == a.to_dict()


def test_has_evidence_and_historical() -> None:
    bare = Artifact(id="d1", type=ArtifactType.DECISION, summary="x")
    assert not bare.has_evidence
    assert not bare.is_historical
    superseded = Artifact(id="d0", type=ArtifactType.DECISION, summary="old", superseded_by="d1")
    assert superseded.is_historical
    hist = Artifact(id="d2", type=ArtifactType.DECISION, summary="x", status=Status.HISTORICAL)
    assert hist.is_historical


def test_default_status_is_candidate() -> None:
    a = Artifact(id="i1", type=ArtifactType.INCIDENT, summary="lease overlap")
    assert a.status is Status.CANDIDATE
    assert a.source is Source.HUMAN
