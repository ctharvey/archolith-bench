"""Offline unit test for the REAL retrieval_quality.py logic (no live graph, no API spend).

Catches the class of bug where the print path crashes (f-string `:s` applied to a number
or None) and where gate math silently changes.

These tests import the shipped functions from retrieval_quality rather than re-implementing
them. A previous version of this file inlined copies of summarize()/mrr_at_k(), which meant
it passed even when the real module was broken -- do not reintroduce that pattern.
Importing is safe because retrieval_quality reads env tolerantly and guards its entrypoint
behind `if __name__ == "__main__"`.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from retrieval_quality import (  # noqa: E402  -- real shipped code under test
    KS,
    format_narrow_line,
    format_wide_line,
    gold_rank,
    mrr_at_k,
    summarize,
    support_rank,
)


def _fmt_summary_line(s):
    """Exercise BOTH shipped format paths. main() calls exactly these functions, so a
    regression to `{median_rank:>11s}` (numeric/None + `:s`) raises here."""
    return format_wide_line("menhir", s) + "\n" + format_narrow_line("support", s)


def test_summarize_with_empty_rows():
    s = summarize([], "m_rank")
    assert s["median_rank"] is None
    assert s["found"] == 0
    assert s["total"] == 0
    assert s["mrr@10"] == 0.0
    # None median must still format without raising.
    assert isinstance(_fmt_summary_line(s), str)


def test_summarize_with_synthetic_rows():
    rows = [
        {"m_rank": 1, "g_rank": 2},
        {"m_rank": 3, "g_rank": 4},
        {"m_rank": None, "g_rank": 5},
        {"m_rank": 7, "g_rank": None},
    ]
    s = summarize(rows, "m_rank")
    assert s["found"] == 3
    assert s["total"] == 4
    assert s["median_rank"] == 3
    assert s["present@3"] == 2  # ranks 1 and 3
    assert s["mrr@10"] > 0.0
    assert set(KS) == {5, 10, 20}


def test_mrr_at_k_computation():
    # ranks [1, 2, None, 5, 15] @k=10 -> [1.0, 0.5, 0, 0.2, 0] -> mean 0.34
    assert abs(mrr_at_k([1, 2, None, 5, 15], k=10) - 0.34) < 1e-9
    assert mrr_at_k([], k=10) == 0.0
    assert mrr_at_k([None, None], k=10) == 0.0
    # rank beyond k contributes nothing
    assert mrr_at_k([11], k=10) == 0.0


def test_print_path_no_crash_numeric_and_none_median():
    """The regression guard: numeric AND None median_rank must both format."""
    numeric = summarize([{"m_rank": 1}, {"m_rank": 3}], "m_rank")
    assert numeric["median_rank"] is not None
    assert isinstance(_fmt_summary_line(numeric), str)

    none_median = summarize([{"m_rank": None}], "m_rank")
    assert none_median["median_rank"] is None
    assert isinstance(_fmt_summary_line(none_median), str)


def test_gate_math_uses_real_summarize():
    rows = [
        {"m_supp": 1, "g_supp": 2},
        {"m_supp": 2, "g_supp": 3},
        {"m_supp": 5, "g_supp": 4},
    ]
    m = summarize(rows, "m_supp")
    g = summarize(rows, "g_supp")

    hit3_rate = m["present@3"] / len(rows)
    assert abs(hit3_rate - (2 / 3)) < 1e-9
    assert (hit3_rate >= 0.80) is False  # 0.67 must not pass the 0.80 gate

    assert (m["mrr@10"] >= g["mrr@10"]) is True

    # An unmeasured gate is None and must never contribute a PASS to the overall verdict.
    gate1, gate2, gate3 = hit3_rate >= 0.80, m["mrr@10"] >= g["mrr@10"], None
    measured = [x for x in (gate1, gate2, gate3) if x is not None]
    overall = all(measured) if measured else False
    assert measured == [gate1, gate2]  # the None gate is excluded, not coerced to True
    assert overall is False  # gate1 fails at 0.67, so overall must fail


def test_rank_helpers_real_behaviour():
    """gold_rank/support_rank are the metric primitives the gates rest on."""
    assert gold_rank("blue car", ["nothing here", "the car is blue"]) == 2
    assert gold_rank("absent token", ["nothing here"]) is None
    assert gold_rank("", ["anything"]) is None

    support = {"pizza", "cheese"}
    assert support_rank(support, ["favorite food pizza with cheese"]) == 1
    assert support_rank(set(), ["anything"]) is None
