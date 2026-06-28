"""Tests for the ArtifactMutator (R9-lite) — the L4 invariants, fail-closed."""

from __future__ import annotations

import pytest

from archolith_bench.l4.models import ArtifactType, Evidence, Source, Status
from archolith_bench.l4.mutator import ArtifactMutator, MutatorError

_EV = [Evidence(kind="git", ref="e8da67d")]


def _m() -> ArtifactMutator:
    return ArtifactMutator(clock=lambda: "2026-06-28T00:00:00Z")


def test_human_with_evidence_is_trusted_on_create() -> None:
    a = _m().create(id="f1", type=ArtifactType.FAILURE, summary="x", source=Source.HUMAN, evidence=_EV)
    assert a.status is Status.TRUSTED


def test_human_without_evidence_is_candidate() -> None:
    a = _m().create(id="f1", type=ArtifactType.FAILURE, summary="x", source=Source.HUMAN)
    assert a.status is Status.CANDIDATE


def test_llm_is_never_trusted_on_create_even_with_evidence() -> None:
    # invariant 4 — structural: create() has no status param, so this is unforgeable.
    a = _m().create(id="f1", type=ArtifactType.FAILURE, summary="x", source=Source.LLM, evidence=_EV)
    assert a.status is Status.CANDIDATE


def test_promote_refuses_without_evidence() -> None:
    m = _m()
    m.create(id="d1", type=ArtifactType.DECISION, summary="x", source=Source.HUMAN)
    with pytest.raises(MutatorError):
        m.promote("d1")  # invariant 3, fail-closed


def test_promote_with_evidence_trusts_llm_candidate_via_review() -> None:
    m = _m()
    m.create(id="f1", type=ArtifactType.FAILURE, summary="x", source=Source.LLM, evidence=_EV)
    promoted = m.promote("f1", reviewed_by="human")  # the promote call IS the review
    assert promoted.status is Status.TRUSTED


def test_supersede_marks_historical_and_links_never_deletes() -> None:
    m = _m()
    m.create(id="old", type=ArtifactType.DECISION, summary="old", source=Source.HUMAN, evidence=_EV)
    m.create(id="new", type=ArtifactType.DECISION, summary="new", source=Source.HUMAN, evidence=_EV)
    old, new = m.supersede("old", "new")
    assert old.status is Status.HISTORICAL
    assert old.superseded_by == "new"
    assert new.supersedes == "old"
    assert m.get("old") is not None  # not deleted (invariant 7)


def test_unknown_and_duplicate_and_self_supersede_raise() -> None:
    m = _m()
    m.create(id="a", type=ArtifactType.DECISION, summary="x", source=Source.HUMAN, evidence=_EV)
    with pytest.raises(MutatorError):
        m.create(id="a", type=ArtifactType.DECISION, summary="dup", source=Source.HUMAN)
    with pytest.raises(MutatorError):
        m.promote("nope")
    with pytest.raises(MutatorError):
        m.supersede("a", "a")


def test_cannot_promote_historical() -> None:
    m = _m()
    m.create(id="old", type=ArtifactType.DECISION, summary="old", source=Source.HUMAN, evidence=_EV)
    m.create(id="new", type=ArtifactType.DECISION, summary="new", source=Source.HUMAN, evidence=_EV)
    m.supersede("old", "new")
    with pytest.raises(MutatorError):
        m.promote("old")
