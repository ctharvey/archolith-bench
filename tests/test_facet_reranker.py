"""Tests for the meet-point reranker and its explanation traces."""

from __future__ import annotations

from archolith_bench.facet.models import Memory, MemoryFacetSet, Query
from archolith_bench.facet.reranker import MeetPointReranker, MeetPointWeights


def _mem(mid: str, **facets) -> Memory:
    superseded = facets.pop("superseded", False)
    return Memory(mid, mid, MemoryFacetSet(**facets), superseded=superseded)


def test_required_facet_and_convergence_raise_score() -> None:
    rr = MeetPointReranker()
    query = Query("q", "q", MemoryFacetSet(repo="menhir", file={"a.py"}, symbol={"recall"}, operation={"fix"}))
    strong = _mem("strong", repo="menhir", file={"a.py"}, symbol={"recall"}, operation={"fix"})
    weak = _mem("weak", repo="menhir")
    s_strong = rr.score(query, strong).score
    s_weak = rr.score(query, weak).score
    assert s_strong > s_weak


def test_stale_penalty_under_current_intent() -> None:
    rr = MeetPointReranker()
    query = Query("q", "q", MemoryFacetSet(repo="menhir", symbol={"recall"}), intent="current")
    current = _mem("cur", repo="menhir", symbol={"recall"}, belief_bucket="current")
    stale = _mem("old", repo="menhir", symbol={"recall"}, belief_bucket="historical")
    exp_stale = rr.score(query, stale)
    assert rr.score(query, current).score > exp_stale.score
    assert any(p.startswith("stale:") for p in exp_stale.penalties)


def test_no_stale_penalty_under_historical_intent() -> None:
    rr = MeetPointReranker()
    query = Query("q", "q", MemoryFacetSet(repo="menhir", symbol={"recall"}), intent="historical")
    stale = _mem("old", repo="menhir", symbol={"recall"}, belief_bucket="historical")
    exp = rr.score(query, stale)
    assert not any(p.startswith("stale:") for p in exp.penalties)


def test_wrong_scope_penalty_demotes_other_repo() -> None:
    rr = MeetPointReranker()
    query = Query("q", "q", MemoryFacetSet(repo="menhir", object={"floor"}))
    same = _mem("same", repo="menhir", object={"floor"})
    other = _mem("other", repo="archolith-bench", object={"floor"})
    exp_other = rr.score(query, other)
    assert rr.score(query, same).score > exp_other.score
    assert any(p.startswith("wrong_scope:") for p in exp_other.penalties)


def test_time_compatibility_bonus() -> None:
    rr = MeetPointReranker()
    query = Query("q", "q", MemoryFacetSet(repo="menhir", symbol={"x"}, valid_time="2026-06-27"))
    in_window = _mem("ok", repo="menhir", symbol={"x"}, valid_time="2026-06-01")
    exp = rr.score(query, in_window)
    assert exp.time_compatible


def test_rerank_is_deterministic_and_ranked() -> None:
    rr = MeetPointReranker()
    query = Query("q", "q", MemoryFacetSet(repo="menhir", symbol={"recall"}))
    corpus = {
        "a": _mem("a", repo="menhir", symbol={"recall"}),
        "b": _mem("b", repo="menhir"),
        "c": _mem("c", repo="other", symbol={"recall"}),
    }
    order1 = rr.ranked_ids(query, ["c", "b", "a"], corpus)
    order2 = rr.ranked_ids(query, ["a", "b", "c"], corpus)
    assert order1 == order2
    assert order1[0] == "a"  # best convergence, no penalty
    explanations = rr.rerank(query, list(corpus), corpus)
    assert [e.rank for e in explanations] == [1, 2, 3]


def test_weights_are_tunable() -> None:
    query = Query("q", "q", MemoryFacetSet(repo="menhir", symbol={"recall"}), intent="current")
    stale = Memory("old", "old", MemoryFacetSet(repo="menhir", symbol={"recall"}, belief_bucket="historical"))
    soft = MeetPointReranker(MeetPointWeights(stale_penalty=0.0))
    hard = MeetPointReranker(MeetPointWeights(stale_penalty=10.0))
    assert soft.score(query, stale).score > hard.score(query, stale).score
