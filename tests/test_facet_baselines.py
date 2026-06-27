"""Tests for the facet-ladder baselines (BM25, embedding stub, fusion, file-context)."""

from __future__ import annotations

from archolith_bench.facet.baselines import (
    BM25,
    LexicalEmbeddingStub,
    file_context_rank,
    rank_from_scores,
    rrf_fuse,
    tokenize,
)
from archolith_bench.facet.models import Memory, MemoryFacetSet, Query


def _mem(mid: str, text: str, **facets) -> Memory:
    return Memory(mid, text, MemoryFacetSet(**facets))


def test_tokenize_lowercases_and_splits_identifiers() -> None:
    assert tokenize("Fix Recall_Service.py") == ["fix", "recall_service", "py"]


def test_bm25_ranks_term_match_first() -> None:
    corpus = [
        _mem("a", "cosine similarity floor in recall"),
        _mem("b", "ingest pipeline stamping episodes"),
    ]
    scores = BM25(corpus).score("cosine floor recall")
    assert scores["a"] > scores["b"]


def test_rank_from_scores_drops_zero_and_sorts() -> None:
    ranked = rank_from_scores({"a": 0.0, "b": 2.0, "c": 1.0})
    assert ranked == ["b", "c"]


def test_embedding_stub_is_symmetric_and_deterministic() -> None:
    stub = LexicalEmbeddingStub()
    corpus = [_mem("a", "floor recall menhir"), _mem("b", "unrelated ingest text")]
    s1 = stub.score("floor recall", corpus)
    s2 = stub.score("floor recall", corpus)
    assert s1 == s2
    assert s1["a"] > s1["b"]


def test_rrf_fuse_rewards_agreement() -> None:
    fused = rrf_fuse([["a", "b", "c"], ["a", "c", "b"]])
    assert fused[0] == "a"
    assert set(fused) == {"a", "b", "c"}


def test_file_context_rank_uses_structure_overlap() -> None:
    query = Query("q", "q", MemoryFacetSet(file={"a.py"}, symbol={"recall"}))
    corpus = [
        _mem("hit", "x", file={"a.py"}, symbol={"recall"}),
        _mem("partial", "y", file={"a.py"}),
        _mem("miss", "z", file={"b.py"}),
    ]
    ranked = file_context_rank(query, corpus)
    assert ranked[0] == "hit"
    assert "miss" not in ranked


def test_file_context_empty_when_query_has_no_structure() -> None:
    query = Query("q", "q", MemoryFacetSet(repo="menhir"))
    assert file_context_rank(query, [_mem("a", "x", file={"a.py"})]) == []
