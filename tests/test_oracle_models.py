"""Tests for the oracle bench data models."""

from __future__ import annotations

from pathlib import Path

from archolith_bench.oracle.models import (
    CandidateMemory,
    OracleFixture,
    OracleMemory,
    OracleQuery,
    QueryContext,
)

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "oracle_demo.json"


def test_memory_from_dict_roundtrip_fields() -> None:
    m = OracleMemory.from_dict(
        {"id": "m1", "text": "t", "repo": "menhir", "files": ["a.py"], "symbols": ["s"],
         "superseded": True, "belief_bucket": "historical", "evidence_kinds": ["git"]}
    )
    assert m.id == "m1"
    assert m.files == {"a.py"}
    assert m.symbols == {"s"}
    assert m.is_stale is True


def test_is_stale_via_bucket_and_flag() -> None:
    assert OracleMemory("a", belief_bucket="anergic").is_stale
    assert OracleMemory("b", superseded=True).is_stale
    assert not OracleMemory("c", belief_bucket="current").is_stale
    assert not OracleMemory("d").is_stale


def test_to_candidate_projects_metadata() -> None:
    m = OracleMemory("m", "txt", repo="menhir", symbols={"x"}, evidence_kinds={"git"})
    cand = m.to_candidate()
    assert isinstance(cand, CandidateMemory)
    assert cand.id == "m"
    assert cand.content == "txt"
    assert cand.metadata["repo"] == "menhir"
    assert cand.metadata["symbols"] == ("x",)
    assert cand.metadata["evidence_kinds"] == ("git",)


def test_query_to_context_sorts_sets_to_tuples() -> None:
    q = OracleQuery("q", "text", repo="menhir", symbols={"b", "a"}, intent="historical")
    ctx = q.to_context()
    assert isinstance(ctx, QueryContext)
    assert ctx.symbols == ("a", "b")
    assert ctx.intent == "historical"
    assert ctx.repo == "menhir"


def test_fixture_loads_from_file() -> None:
    fx = OracleFixture.from_file(FIXTURE)
    assert fx.name == "oracle_demo"
    assert len(fx.memories) == 10
    assert len(fx.queries) == 6
    assert "m01" in fx.memories_by_id


def test_fixture_support_ids_exist_in_corpus() -> None:
    fx = OracleFixture.from_file(FIXTURE)
    ids = set(fx.memories_by_id)
    for q in fx.queries:
        for sid in q.support_ids:
            assert sid in ids, f"{q.id} references missing support {sid}"
