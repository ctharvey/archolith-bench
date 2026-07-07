"""Tests for ColdStartBrief v0 — bucketing carries epistemic status (invariant 8)."""

from __future__ import annotations

from archolith_bench.l4.brief import Epistemic, build_brief
from archolith_bench.l4.memory_oracle import MemoryOracle
from archolith_bench.l4.models import Artifact, ArtifactType, Evidence, Source, Status

_EV = [Evidence(kind="git", ref="e8da67d")]


def _corpus() -> list[Artifact]:
    return [
        Artifact(id="floor_fail", type=ArtifactType.FAILURE,
                 summary="fixed cosine similarity floor dropped facet candidates",
                 status=Status.TRUSTED, source=Source.HUMAN, evidence=_EV,
                 anchors=["scoring_service.py"]),
        Artifact(id="floor_fix", type=ArtifactType.DECISION,
                 summary="rank facet candidates instead of applying a fixed floor",
                 status=Status.TRUSTED, source=Source.HUMAN, evidence=_EV,
                 anchors=["scoring_service.py"]),
        Artifact(id="floor_guess", type=ArtifactType.FAILURE,
                 summary="maybe the floor interacts with recency on cosine scores",
                 status=Status.CANDIDATE, source=Source.LLM, evidence=_EV,
                 anchors=["scoring_service.py"]),
        Artifact(id="old_floor", type=ArtifactType.DECISION,
                 summary="use a fixed cosine floor on similarity",
                 status=Status.HISTORICAL, source=Source.HUMAN, evidence=_EV,
                 anchors=["scoring_service.py"], superseded_by="floor_fix"),
    ]


def _brief():
    oracle = MemoryOracle(_corpus())
    return build_brief(task="tighten the cosine similarity floor",
                       anchors=["scoring_service.py"], oracle=oracle)


def test_trusted_failure_is_a_fact_with_evidence() -> None:
    brief = _brief()
    ids = [i.artifact_id for i in brief.failed_approaches]
    assert "floor_fail" in ids
    item = next(i for i in brief.failed_approaches if i.artifact_id == "floor_fail")
    assert item.epistemic is Epistemic.FACT
    assert item.evidence_refs == ("git:e8da67d",)


def test_candidate_is_a_hypothesis_never_a_fact() -> None:
    # invariant 8: a CANDIDATE artifact can never appear in a fact bucket.
    brief = _brief()
    hyp_ids = [i.artifact_id for i in brief.hypotheses]
    assert "floor_guess" in hyp_ids
    assert all(i.epistemic is Epistemic.HYPOTHESIS for i in brief.hypotheses)
    fact_ids = [i.artifact_id for i in brief.facts()]
    assert "floor_guess" not in fact_ids
    assert all(i.epistemic is Epistemic.FACT for i in brief.facts())


def test_historical_is_flagged_stale_not_current() -> None:
    brief = _brief()
    stale_ids = [i.artifact_id for i in brief.stale_or_contradicted]
    assert "old_floor" in stale_ids
    assert "old_floor" not in [i.artifact_id for i in brief.facts()]
    assert "old_floor" not in [i.artifact_id for i in brief.decisions]


def test_recommended_first_action_avoids_failure_prefers_corrective() -> None:
    brief = _brief()
    rec = brief.recommended_first_action
    assert rec is not None
    assert "floor_fail" in rec
    assert "Avoid" in rec
    assert "floor_fix" in rec  # corrective decision shares the anchor


def test_no_candidate_id_in_any_fact_bucket() -> None:
    brief = _brief()
    candidate_id = "floor_guess"
    for bucket in (brief.failed_approaches, brief.decisions, brief.risks):
        assert candidate_id not in [i.artifact_id for i in bucket]


def test_render_is_token_countable() -> None:
    brief = _brief()
    assert brief.token_count() > 0
    assert "TASK:" in brief.render()
