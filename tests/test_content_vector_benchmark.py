from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest

from archolith_bench.r1.runner import ConditionResult


pytest.importorskip("neo4j")
pytest.importorskip("openai")


_SCRIPT = Path(__file__).parents[1] / "scripts" / "run_content_vector_benchmark.py"
_SPEC = spec_from_file_location("run_content_vector_benchmark", _SCRIPT)
assert _SPEC and _SPEC.loader
benchmark = module_from_spec(_SPEC)
_SPEC.loader.exec_module(benchmark)


def _result(name: str, recall5: float, mrr: float) -> ConditionResult:
    return ConditionResult(
        name,
        {
            "recall_at_5": recall5,
            "recall_at_10": recall5,
            "mrr": mrr,
            "stale_hit_rate": 0.0,
            "wrong_scope_injection_rate": 0.0,
            "negative_query_false_positive_rate": 0.0,
            "exact_string_recall": 1.0,
            "symbol_recall": 1.0,
        },
    )


def test_c_gate_measures_rank_regression_against_b_not_a() -> None:
    results = {
        "A": _result("A", 0.4, 0.2),
        "B": _result("B", 0.5, 0.3),
        "C": _result("C", 0.6, 0.4),
    }
    ranks = {
        "A": {"case": 1},
        "B": {"case": 3},
        "C": {"case": 2},
    }

    gate = benchmark._gate(results, ranks, "B", "C", rank_tolerance=0)

    assert gate["graduates"] is True
    assert gate["baseline"]["rank_regression_rate"] == 0.0
    assert gate["evaluated"][0]["rank_regression_rate"] == 0.0


def test_metrics_latency_is_scoped_to_the_requested_cases() -> None:
    cases = [{"id": "auto", "gold_ids": ["gold"], "namespace": "default"}]
    metrics, _ = benchmark._metrics(
        cases,
        {"auto": ["gold"], "anchor": ["other"]},
        {"auto": 12.0, "anchor": 900.0},
        {"gold": {"freshness": "ACTIVE", "namespace": "default"}},
        limit=50,
    )

    assert metrics["latency_ms"] == 12.0
