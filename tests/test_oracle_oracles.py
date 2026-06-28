"""Tests for the cheap retrieval oracles."""

from __future__ import annotations

from archolith_bench.oracle.models import OracleMemory, OraclePolarity, OracleTarget, QueryContext
from archolith_bench.oracle.oracles import (
    EvidenceOracle,
    ScopeOracle,
    SemanticOracle,
    StructureOracle,
    TemporalOracle,
    default_oracles,
)


def _cand(**kw) -> "object":
    return OracleMemory("m", **kw).to_candidate()


def test_semantic_overlap_higher_for_closer_text() -> None:
    q = QueryContext(text="source aware similarity floor")
    near = _cand(text="the similarity floor is source aware now")
    far = _cand(text="completely unrelated combat config tweak")
    assert SemanticOracle().evaluate(q, near).probability > SemanticOracle().evaluate(q, far).probability


def test_semantic_neutral_on_zero_overlap() -> None:
    q = QueryContext(text="alpha beta")
    r = SemanticOracle().evaluate(q, _cand(text="gamma delta"))
    assert r.probability == 0.0
    assert r.polarity == OraclePolarity.NEUTRAL


def test_structure_overlap_recovers_shared_symbol() -> None:
    q = QueryContext(text="x", symbols=("TreeWillow",), tests=("test_bounds",))
    hit = _cand(symbols={"TreeWillow"}, tests={"test_bounds"})
    miss = _cand(symbols={"Other"})
    r_hit = StructureOracle().evaluate(q, hit)
    r_miss = StructureOracle().evaluate(q, miss)
    assert r_hit.probability == 1.0
    assert r_hit.target == OracleTarget.RELEVANCE
    assert r_miss.polarity == OraclePolarity.MISSING


def test_scope_conflict_is_contradiction() -> None:
    q = QueryContext(text="x", repo="menhir")
    r = ScopeOracle().evaluate(q, _cand(repo="archolith-bench"))
    assert r.polarity == OraclePolarity.CONTRADICT
    assert r.target == OracleTarget.SCOPE
    assert r.scope_match == 1.0  # the fix: scope oracle does not zero its own verdict


def test_scope_match_is_support() -> None:
    q = QueryContext(text="x", repo="menhir")
    r = ScopeOracle().evaluate(q, _cand(repo="menhir"))
    assert r.polarity == OraclePolarity.SUPPORT


def test_scope_missing_when_no_shared_keys() -> None:
    q = QueryContext(text="x")  # no scope set
    r = ScopeOracle().evaluate(q, _cand(repo="menhir"))
    assert r.polarity == OraclePolarity.MISSING


def test_temporal_contradicts_stale_under_current() -> None:
    q = QueryContext(text="x", intent="current", as_of_time="2026-06-01")
    r = TemporalOracle().evaluate(q, _cand(superseded=True))
    assert r.polarity == OraclePolarity.CONTRADICT
    assert r.target == OracleTarget.CURRENTNESS


def test_temporal_supports_stale_under_historical() -> None:
    q = QueryContext(text="x", intent="historical")
    r = TemporalOracle().evaluate(q, _cand(belief_bucket="historical"))
    assert r.polarity == OraclePolarity.SUPPORT
    assert r.target == OracleTarget.HISTORICALITY


def test_temporal_invalid_at_before_as_of_is_stale() -> None:
    q = QueryContext(text="x", intent="current", as_of_time="2026-06-01")
    r = TemporalOracle().evaluate(q, _cand(invalid_at="2026-03-01"))
    assert r.polarity == OraclePolarity.CONTRADICT


def test_temporal_live_supports_currentness() -> None:
    q = QueryContext(text="x", intent="current", as_of_time="2026-06-01")
    r = TemporalOracle().evaluate(q, _cand(belief_bucket="current"))
    assert r.polarity == OraclePolarity.SUPPORT
    assert r.target == OracleTarget.CURRENTNESS


def test_temporal_anachronism_learned_after_as_of() -> None:
    # A memory created AFTER the query's as-of point is temporal leakage -> contradict.
    q = QueryContext(text="x", intent="current", as_of_time="2026-06-01")
    r = TemporalOracle().evaluate(q, _cand(created_at="2026-09-01", belief_bucket="current"))
    assert r.polarity == OraclePolarity.CONTRADICT
    assert r.target == OracleTarget.CURRENTNESS
    assert "anachronism" in r.note
    assert r.directness == 1.0


def test_temporal_not_yet_valid() -> None:
    q = QueryContext(text="x", intent="current", as_of_time="2026-06-01")
    r = TemporalOracle().evaluate(q, _cand(valid_at="2026-09-01"))
    assert r.polarity == OraclePolarity.CONTRADICT
    assert "not_yet_valid" in r.note


def test_temporal_unknown_is_missing_not_fabricated() -> None:
    q = QueryContext(text="x", intent="current", as_of_time="2026-06-01")
    r = TemporalOracle().evaluate(q, _cand())  # no temporal anchors at all
    assert r.polarity == OraclePolarity.MISSING


def test_temporal_directness_graded_explicit_vs_bucket() -> None:
    q = QueryContext(text="x", intent="current", as_of_time="2026-06-01")
    explicit = TemporalOracle().evaluate(q, _cand(superseded=True))
    bucket_only = TemporalOracle().evaluate(q, _cand(belief_bucket="historical"))
    assert explicit.directness == 1.0
    assert bucket_only.directness < explicit.directness  # inferred-stale penalised less hard


def test_temporal_current_via_validity_window() -> None:
    q = QueryContext(text="x", intent="current", as_of_time="2026-06-01")
    r = TemporalOracle().evaluate(q, _cand(valid_at="2026-01-01", invalid_at="2027-01-01"))
    assert r.polarity == OraclePolarity.SUPPORT
    assert r.target == OracleTarget.CURRENTNESS
    assert r.directness == 1.0


def test_evidence_strong_beats_inferred_directness() -> None:
    q = QueryContext(text="x")
    strong = EvidenceOracle().evaluate(q, _cand(evidence_kinds={"git", "test"}))
    inferred = EvidenceOracle().evaluate(q, _cand(evidence_kinds={"agent_inference"}))
    assert strong.directness > inferred.directness
    assert strong.confidence > inferred.confidence


def test_evidence_missing_is_not_contradiction() -> None:
    q = QueryContext(text="x")
    r = EvidenceOracle().evaluate(q, _cand(evidence_kinds=set()))
    assert r.polarity == OraclePolarity.MISSING


def test_default_oracles_are_named_uniquely() -> None:
    names = [o.name for o in default_oracles()]
    assert names == ["semantic", "structure", "scope", "temporal", "evidence"]
    assert len(set(names)) == len(names)
