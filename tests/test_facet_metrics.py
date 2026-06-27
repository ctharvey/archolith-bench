"""Tests for facet retrieval metrics."""

from __future__ import annotations

from archolith_bench.facet import metrics as M
from archolith_bench.facet.models import Memory, MemoryFacetSet, Query


def _mem(mid: str, **facets) -> Memory:
    superseded = facets.pop("superseded", False)
    return Memory(mid, mid, MemoryFacetSet(**facets), superseded=superseded)


def test_recall_precision_mrr_ndcg() -> None:
    ranked = ["a", "x", "b"]
    support = ["a", "b"]
    assert M.recall_at_k(ranked, support, 5) == 1.0
    assert M.precision_at_k(ranked, support, 3) == 2 / 3
    assert M.mrr(ranked, support) == 1.0
    assert M.mrr(["x", "a"], support) == 0.5
    assert M.ndcg_at_k(["a", "b"], support, 5) == 1.0
    assert M.ndcg_at_k(["x", "a", "b"], support, 5) < 1.0


def test_stale_hit_rate_respects_intent() -> None:
    by_id = {"a": _mem("a", belief_bucket="current"), "b": _mem("b", belief_bucket="historical")}
    current_q = Query("q", "q", intent="current")
    historical_q = Query("q", "q", intent="historical")
    assert M.stale_hit_rate(["a", "b"], by_id, current_q, 5) == 0.5
    assert M.stale_hit_rate(["a", "b"], by_id, historical_q, 5) == 0.0


def test_wrong_scope_injection_rate() -> None:
    by_id = {"a": _mem("a", repo="menhir"), "b": _mem("b", repo="other")}
    query = Query("q", "q", MemoryFacetSet(repo="menhir"))
    assert M.wrong_scope_injection_rate(["a", "b"], by_id, query, 5) == 0.5


def test_support_sufficiency_is_binary_all_covered() -> None:
    assert M.support_sufficiency(["a", "b"], ["a", "b"], 5) == 1.0
    assert M.support_sufficiency(["a"], ["a", "b"], 5) == 0.0


def test_false_neighbor_rate_counts_convincing_wrong_hits() -> None:
    by_id = {
        "good": _mem("good", symbol={"recall"}),
        "neighbor": _mem("neighbor", symbol={"recall"}),  # shares topic, not support
        "unrelated": _mem("unrelated", symbol={"ingest"}),
    }
    query = Query("q", "q", MemoryFacetSet(symbol={"recall"}), support_ids=["good"])
    rate = M.false_neighbor_rate(["good", "neighbor", "unrelated"], by_id, query, 5)
    assert rate == 1 / 3  # only "neighbor" counts


def test_paraphrase_stability_groups() -> None:
    queries = [
        Query("q1", "q1", paraphrase_group="g"),
        Query("q2", "q2", paraphrase_group="g"),
        Query("q3", "q3", paraphrase_group=None),
    ]
    top = {"q1": ["a", "b"], "q2": ["a", "b"], "q3": ["z"]}
    assert M.paraphrase_stability(top, queries, 5) == 1.0
    top_div = {"q1": ["a", "b"], "q2": ["c", "d"]}
    assert M.paraphrase_stability(top_div, queries, 5) == 0.0


def test_paraphrase_stability_no_groups_returns_zero() -> None:
    queries = [Query("q1", "q1"), Query("q2", "q2")]
    assert M.paraphrase_stability({"q1": ["a"], "q2": ["a"]}, queries, 5) == 0.0
