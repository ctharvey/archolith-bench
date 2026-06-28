"""End-to-end tests for the facet ladder runner and promotion gate."""

from __future__ import annotations

from pathlib import Path

from archolith_bench.facet.models import FacetFixture
from archolith_bench.facet.runner import (
    BASELINE_CONDITIONS,
    CONDITIONS,
    FACET_MODES,
    FacetBenchmarkRunner,
    evaluate_promotion_gate,
)

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "facet_demo.json"


def _runner() -> FacetBenchmarkRunner:
    return FacetBenchmarkRunner(FacetFixture.from_file(FIXTURE))


def test_run_emits_all_conditions_and_modes() -> None:
    artifact = _runner().run()
    for mode in FACET_MODES:
        assert set(artifact["modes"][mode].keys()) == set(CONDITIONS)
        for cond in CONDITIONS:
            metrics = artifact["modes"][mode][cond]["metrics"]
            assert "recall_at_5" in metrics
            assert "stale_hit_rate" in metrics


def _strip_latency(artifact: dict) -> dict:
    """Drop wall-clock latency so determinism can be asserted on rankings/metrics."""
    for mode in artifact["modes"].values():
        for cond in mode.values():
            cond["metrics"].pop("latency_ms", None)
            for pq in cond["per_query"]:
                pq.pop("latency_ms", None)
    return artifact


def test_run_is_deterministic() -> None:
    a1 = _strip_latency(_runner().run(include_traces=False))
    a2 = _strip_latency(_runner().run(include_traces=False))
    assert a1 == a2


def test_meet_point_emits_explanation_traces() -> None:
    artifact = _runner().run()
    f_q1 = next(
        pq for pq in artifact["modes"]["gold"]["F_facet_meet"]["per_query"] if pq["query_id"] == "q1"
    )
    assert f_q1["trace"], "condition F must emit per-candidate explanation traces"
    top = f_q1["trace"][0]
    assert {"memory_id", "score", "matched_required", "penalties"} <= top.keys()


def test_gold_mode_meet_point_graduates_on_demo() -> None:
    artifact = _runner().run()
    gate = artifact["promotion_gate"]["gold"]
    # On the demo, meet-point should cut stale/wrong-scope without losing recall.
    assert gate["graduates"] is True
    assert gate["improved_any"] is True
    assert gate["recall_acceptable"] is True


def test_gold_meet_point_beats_baselines_on_targeted_metrics() -> None:
    artifact = _runner().run()
    gold = artifact["modes"]["gold"]
    f = gold["F_facet_meet"]["metrics"]
    best_stale = min(gold[c]["metrics"]["stale_hit_rate"] for c in BASELINE_CONDITIONS)
    best_wrong = min(gold[c]["metrics"]["wrong_scope_injection_rate"] for c in BASELINE_CONDITIONS)
    assert f["stale_hit_rate"] <= best_stale
    assert f["wrong_scope_injection_rate"] <= best_wrong
    assert f["paraphrase_stability"] >= gold["A_bm25"]["metrics"]["paraphrase_stability"]


def test_gold_and_extracted_modes_are_reported_separately() -> None:
    artifact = _runner().run()
    gold_f = artifact["modes"]["gold"]["F_facet_meet"]["metrics"]
    extracted_f = artifact["modes"]["extracted"]["F_facet_meet"]["metrics"]
    # The two modes answer different questions and must not be merged.
    assert "gold" in artifact["promotion_gate"]
    assert "extracted" in artifact["promotion_gate"]
    assert gold_f["recall_at_5"] >= extracted_f["recall_at_5"]


def test_gate_helper_handles_synthetic_metrics() -> None:
    def metrics(recall, stale, wrong, support):
        return {
            "recall_at_5": recall,
            "stale_hit_rate": stale,
            "wrong_scope_injection_rate": wrong,
            "support_sufficiency": support,
        }

    from archolith_bench.facet.runner import ConditionResult

    def cr(name, m):
        return ConditionResult(condition=name, facet_mode="gold", metrics=m)

    cond_results = {
        "A_bm25": cr("A_bm25", metrics(1.0, 0.5, 0.5, 1.0)),
        "B_embedding": cr("B_embedding", metrics(1.0, 0.4, 0.4, 1.0)),
        "C_hybrid": cr("C_hybrid", metrics(1.0, 0.4, 0.4, 1.0)),
        "F_facet_meet": cr("F_facet_meet", metrics(0.95, 0.1, 0.1, 1.0)),
    }
    gate = evaluate_promotion_gate(cond_results)
    assert gate["graduates"] is True
    assert gate["recall_loss"] == 0.05

    # Recall collapse blocks graduation even with big stale/scope wins.
    cond_results["F_facet_meet"] = cr("F", metrics(0.5, 0.0, 0.0, 1.0))
    blocked = evaluate_promotion_gate(cond_results)
    assert blocked["graduates"] is False
    assert blocked["recall_acceptable"] is False


def test_hybrid_mode_closes_the_extracted_gap() -> None:
    # Priority 6: reading deterministic facets from structure/Git (hybrid) instead of
    # regexing them from prose (extracted) should recover most of gold's performance.
    draft = Path(__file__).resolve().parent.parent / "fixtures" / "facet_r2_draft.json"
    artifact = FacetBenchmarkRunner(FacetFixture.from_file(draft)).run(include_traces=False)
    f_extracted = artifact["modes"]["extracted"]["F_facet_meet"]["metrics"]["recall_at_5"]
    f_hybrid = artifact["modes"]["hybrid"]["F_facet_meet"]["metrics"]["recall_at_5"]
    f_gold = artifact["modes"]["gold"]["F_facet_meet"]["metrics"]["recall_at_5"]
    # hybrid recovers far above pure extraction, near gold
    assert f_hybrid > f_extracted
    assert f_hybrid >= 0.75 * f_gold
    # and the hybrid promotion gate graduates while extracted does not
    assert artifact["promotion_gate"]["hybrid"]["graduates"] is True
    assert artifact["promotion_gate"]["extracted"]["graduates"] is False
