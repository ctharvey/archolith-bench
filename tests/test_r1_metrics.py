"""Tests for R1 retrieval metrics."""

from __future__ import annotations

from archolith_bench.r1 import metrics as M
from archolith_bench.r1.models import R1Memory, R1Query


def _mem(mid: str, **kw) -> R1Memory:
    return R1Memory(
        id=mid,
        text=kw.get("text", mid),
        repo=kw.get("repo"),
        project=kw.get("project"),
        symbols=set(kw.get("symbols", [])),
        exact_strings=set(kw.get("exact_strings", [])),
        stale=kw.get("stale", False),
    )


def _q(qid: str, **kw) -> R1Query:
    return R1Query(
        id=qid,
        text=kw.get("text", qid),
        family=kw.get("family", "exact_error_string"),
        support_ids=kw.get("support_ids", []),
        intent=kw.get("intent", "current"),
        repo=kw.get("repo"),
        project=kw.get("project"),
        target_symbol=kw.get("target_symbol"),
        target_exact_string=kw.get("target_exact_string"),
    )


def test_recall_at_k() -> None:
    assert M.recall_at_k(["a", "x", "b"], ["a", "b"], 5) == 1.0
    assert M.recall_at_k(["x", "y", "a"], ["a", "b"], 5) == 0.5
    assert M.recall_at_k(["a"], [], 5) == 0.0


def test_exact_string_hit_via_label_and_text_and_none() -> None:
    by_id = {
        "m1": _mem("m1", exact_strings=["E1234"]),
        "m2": _mem("m2", text="boom: E5678 happened"),
        "m3": _mem("m3"),
    }
    # in gold exact_strings set
    assert M.exact_string_hit(["m1"], by_id, _q("q", target_exact_string="E1234"), 5) == 1.0
    # verbatim in text
    assert M.exact_string_hit(["m2"], by_id, _q("q", target_exact_string="E5678"), 5) == 1.0
    # present but outside top-k
    assert M.exact_string_hit(["m3", "m1"], by_id, _q("q", target_exact_string="E1234"), 1) == 0.0
    # no target -> excluded from the average
    assert M.exact_string_hit(["m1"], by_id, _q("q"), 5) is None


def test_symbol_hit_and_none() -> None:
    by_id = {"m1": _mem("m1", symbols=["Foo.bar"]), "m2": _mem("m2")}
    assert M.symbol_hit(["m2", "m1"], by_id, _q("q", target_symbol="Foo.bar"), 5) == 1.0
    assert M.symbol_hit(["m2"], by_id, _q("q", target_symbol="Foo.bar"), 5) == 0.0
    assert M.symbol_hit(["m1"], by_id, _q("q"), 5) is None


def test_stale_hit_rate_respects_intent() -> None:
    by_id = {"s": _mem("s", stale=True), "f": _mem("f", stale=False)}
    cur = _q("q", intent="current")
    assert M.stale_hit_rate(["s", "f"], by_id, cur, 5) == 0.5
    # historical-intent queries never count stale as a hit
    hist = _q("q", intent="historical")
    assert M.stale_hit_rate(["s", "f"], by_id, hist, 5) == 0.0


def test_wrong_scope_injection_rate() -> None:
    by_id = {
        "same": _mem("same", repo="menhir"),
        "other": _mem("other", repo="yawn.market"),
        "unscoped": _mem("unscoped"),
    }
    q = _q("q", repo="menhir")
    # other-repo conflicts; same-repo and unscoped do not
    assert M.wrong_scope_injection_rate(["same", "other", "unscoped"], by_id, q, 5) == round(1 / 3, 4) or \
        abs(M.wrong_scope_injection_rate(["same", "other", "unscoped"], by_id, q, 5) - 1 / 3) < 1e-9


def test_scope_conflict_only_when_both_set_and_differ() -> None:
    assert M._scope_conflict(_q("q", repo="a"), _mem("m", repo="b")) is True
    assert M._scope_conflict(_q("q", repo="a"), _mem("m", repo="a")) is False
    assert M._scope_conflict(_q("q"), _mem("m", repo="b")) is False
    assert M._scope_conflict(_q("q", project="p1"), _mem("m", project="p2")) is True


# --- known-item retrieval metrics (plan v6 auto-gen eval) -------------------


def test_known_item_rank_finds_first_cluster_member() -> None:
    ranked = ["a", "b", "gold", "c"]
    assert M.known_item_rank(ranked, ["gold"], limit=10) == 3


def test_known_item_rank_any_cluster_member_counts() -> None:
    # duplicate cluster: gold or gold_dup both count; the FIRST to appear sets the rank
    ranked = ["a", "gold_dup", "b", "gold"]
    assert M.known_item_rank(ranked, ["gold", "gold_dup"], limit=10) == 2


def test_known_item_rank_absent_gold_is_limit_plus_one() -> None:
    ranked = ["a", "b", "c"]
    assert M.known_item_rank(ranked, ["gold"], limit=10) == 11
    # total + monotone: an absent gold sorts strictly worse than any present rank
    present = M.known_item_rank(["gold"], ["gold"], limit=10)
    absent = M.known_item_rank(["x"], ["gold"], limit=10)
    assert present < absent


def test_known_item_recall_at_k_is_binary_and_nested() -> None:
    ranked = ["a", "b", "c", "d", "e", "f", "gold"]  # gold at rank 7
    assert M.known_item_recall_at_k(ranked, ["gold"], 5) == 0.0  # outside top-5
    assert M.known_item_recall_at_k(ranked, ["gold"], 10) == 1.0  # inside top-10
    # NESTED: a gold in the top-5 is necessarily in the top-10. This is exactly why
    # the win gate must use improvement_mode="any" (a 6->2 move lifts @5 but not @10).
    ranked2 = ["a", "gold", "c"]
    assert M.known_item_recall_at_k(ranked2, ["gold"], 5) == 1.0
    assert M.known_item_recall_at_k(ranked2, ["gold"], 10) == 1.0


def test_known_item_recall_credits_any_duplicate_member() -> None:
    ranked = ["a", "b", "gold_dup", "d", "e"]
    assert M.known_item_recall_at_k(ranked, ["gold", "gold_dup"], 5) == 1.0


def test_reciprocal_rank_and_mrr() -> None:
    assert M.reciprocal_rank(1) == 1.0
    assert M.reciprocal_rank(2) == 0.5
    assert abs(M.mrr([1, 2, 4]) - (1.0 + 0.5 + 0.25) / 3) < 1e-9
    assert M.mrr([]) == 0.0


def test_reciprocal_rank_rejects_nonpositive() -> None:
    for bad in (0, -1):
        try:
            M.reciprocal_rank(bad)
        except ValueError:
            pass
        else:  # pragma: no cover
            raise AssertionError(f"expected ValueError for rank={bad}")


def test_mrr_uses_limit_plus_one_for_absent_gold() -> None:
    # A run where gold is absent (rank limit+1) must contribute 1/(limit+1), not be dropped.
    r_present = M.known_item_rank(["gold"], ["gold"], limit=9)   # rank 1
    r_absent = M.known_item_rank(["x"], ["gold"], limit=9)       # rank 10
    assert abs(M.mrr([r_present, r_absent]) - (1.0 + 1.0 / 10) / 2) < 1e-9


def test_rank_regressed_uses_integer_tolerance() -> None:
    assert M.rank_regressed(3, 2) is True            # 3 > 2, worse
    assert M.rank_regressed(2, 2) is False           # equal, not a regression
    assert M.rank_regressed(1, 3) is False           # better
    assert M.rank_regressed(4, 2, rank_tolerance=2) is False  # within tolerance
    assert M.rank_regressed(5, 2, rank_tolerance=2) is True   # beyond tolerance
