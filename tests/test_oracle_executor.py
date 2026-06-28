"""Tests for the deterministic oracle executor."""

from __future__ import annotations

import pytest

from archolith_bench.oracle.executor import OracleExecutor
from archolith_bench.oracle.models import OracleMemory, QueryContext
from archolith_bench.oracle.oracles import default_oracles


def _cands():
    return [
        OracleMemory("m2", text="b", repo="menhir").to_candidate(),
        OracleMemory("m1", text="a", repo="menhir").to_candidate(),
    ]


def test_executor_requires_oracles() -> None:
    with pytest.raises(ValueError):
        OracleExecutor([])


def test_executor_groups_by_candidate() -> None:
    ex = OracleExecutor(default_oracles())
    grouped = ex.evaluate(QueryContext(text="a"), _cands())
    assert set(grouped) == {"m1", "m2"}
    assert all(len(v) == len(default_oracles()) for v in grouped.values())


def test_executor_results_in_oracle_priority_order() -> None:
    oracles = default_oracles()
    ex = OracleExecutor(oracles)
    grouped = ex.evaluate(QueryContext(text="a"), _cands())
    expected = [o.name for o in oracles]
    for results in grouped.values():
        assert [r.oracle for r in results] == expected


def test_executor_is_deterministic() -> None:
    ex = OracleExecutor(default_oracles())
    q = QueryContext(text="similarity floor", repo="menhir")
    first = ex.evaluate(q, _cands())
    second = ex.evaluate(q, _cands())
    assert {k: [r.probability for r in v] for k, v in first.items()} == {
        k: [r.probability for r in v] for k, v in second.items()
    }
