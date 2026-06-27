"""Tests for facet data models and fixture loading."""

from __future__ import annotations

from pathlib import Path

from archolith_bench.facet.models import FacetFixture, Memory, MemoryFacetSet, Query

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "facet_demo.json"


def test_facetset_from_dict_coerces_sets_and_scalars() -> None:
    fs = MemoryFacetSet.from_dict({"file": "a.py", "symbol": ["X", "y"], "repo": "menhir"})
    assert fs.file == {"a.py"}
    assert fs.symbol == {"X", "y"}
    assert fs.repo == "menhir"
    assert fs.namespace is None


def test_facetset_values_unifies_set_and_scalar() -> None:
    fs = MemoryFacetSet(symbol={"a", "b"}, repo="menhir")
    assert fs.values("symbol") == {"a", "b"}
    assert fs.values("repo") == {"menhir"}
    assert fs.values("project") == set()


def test_discrete_pairs_excludes_temporal() -> None:
    fs = MemoryFacetSet(file={"a.py"}, repo="menhir", valid_time="2026-01-01")
    pairs = fs.discrete_pairs()
    assert ("file", "a.py") in pairs
    assert ("repo", "menhir") in pairs
    assert all(name != "valid_time" for name, _ in pairs)


def test_to_dict_round_trips_and_sorts() -> None:
    fs = MemoryFacetSet.from_dict({"symbol": ["b", "a"], "repo": "menhir"})
    out = fs.to_dict()
    assert out["symbol"] == ["a", "b"]
    assert out["repo"] == "menhir"
    assert "namespace" not in out


def test_memory_is_stale_from_bucket_or_supersede() -> None:
    assert Memory("m", "t", MemoryFacetSet(belief_bucket="historical")).is_stale
    assert Memory("m", "t", MemoryFacetSet(), superseded=True).is_stale
    assert not Memory("m", "t", MemoryFacetSet(belief_bucket="current")).is_stale


def test_query_from_dict_defaults() -> None:
    q = Query.from_dict({"id": "q1", "text": "hi", "support_ids": ["m1"]})
    assert q.intent == "current"
    assert q.support_ids == ["m1"]
    assert q.required_facets == []


def test_demo_fixture_loads_and_supports_resolve() -> None:
    fx = FacetFixture.from_file(FIXTURE)
    assert fx.name == "facet_demo"
    assert len(fx.memories) == 10
    assert len(fx.queries) == 6
    by_id = fx.memories_by_id
    for query in fx.queries:
        for sid in query.support_ids:
            assert sid in by_id, f"{query.id} references missing support {sid}"
