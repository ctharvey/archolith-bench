"""Tests for the facet overlap candidate index."""

from __future__ import annotations

from archolith_bench.facet.index import MemoryFacetIndex
from archolith_bench.facet.models import Memory, MemoryFacetSet


def _mem(mid: str, **facets) -> Memory:
    return Memory(mid, mid, MemoryFacetSet(**facets))


def test_candidates_by_overlap_count() -> None:
    corpus = [
        _mem("a", repo="menhir", symbol={"recall"}),
        _mem("b", repo="menhir"),
        _mem("c", repo="other"),
    ]
    index = MemoryFacetIndex().build(corpus)
    cands = index.candidates(MemoryFacetSet(repo="menhir", symbol={"recall"}))
    # a shares 2 pairs, b shares 1, c shares 0 (excluded).
    assert cands == [("a", 2), ("b", 1)]


def test_candidate_ids_stable_tiebreak() -> None:
    corpus = [_mem("b", repo="menhir"), _mem("a", repo="menhir")]
    index = MemoryFacetIndex().build(corpus)
    # equal overlap → id-sorted, deterministic
    assert index.candidate_ids(MemoryFacetSet(repo="menhir")) == ["a", "b"]


def test_no_overlap_returns_empty() -> None:
    index = MemoryFacetIndex().build([_mem("a", repo="menhir")])
    assert index.candidates(MemoryFacetSet(repo="nope")) == []


def test_len_counts_unique_memories() -> None:
    index = MemoryFacetIndex().build([_mem("a", repo="menhir"), _mem("b", repo="menhir")])
    assert len(index) == 2
