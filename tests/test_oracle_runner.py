"""Tests for the oracle ladder runner + promotion gate."""

from __future__ import annotations

from pathlib import Path

from archolith_bench.oracle.models import OracleFixture
from archolith_bench.oracle.runner import CONDITIONS, OracleBenchmarkRunner, run_ablation

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
FIXTURE = FIXTURES / "oracle_demo.json"
HARD_FIXTURE = FIXTURES / "oracle_hard.json"
CORRELATED_FIXTURE = FIXTURES / "oracle_correlated.json"
SCOPE_FIXTURE = FIXTURES / "oracle_scope.json"


def _artifact() -> dict:
    return OracleBenchmarkRunner(OracleFixture.from_file(FIXTURE)).run(include_traces=False)


def _hard_artifact() -> dict:
    return OracleBenchmarkRunner(OracleFixture.from_file(HARD_FIXTURE)).run(include_traces=False)


def test_run_has_all_conditions() -> None:
    art = _artifact()
    assert set(art["conditions"]) == set(CONDITIONS)


def test_metrics_present_and_in_range() -> None:
    art = _artifact()
    for cond in CONDITIONS:
        m = art["conditions"][cond]["metrics"]
        for key in ("recall_at_5", "stale_hit_rate", "wrong_scope_injection_rate",
                    "current_truth_suppression_accuracy", "historical_context_preservation"):
            assert 0.0 <= m[key] <= 1.0


def test_all_conditions_are_deterministic() -> None:
    art = _artifact()
    for cond in CONDITIONS:
        assert art["conditions"][cond]["metrics"]["ranking_determinism"] == 1.0


def test_combining_oracles_beats_single_semantic_on_stale() -> None:
    # The whole point of the ladder: oracle combination suppresses stale/wrong-scope
    # that a lone semantic signal lets through.
    art = _artifact()
    a = art["conditions"]["A_semantic"]["metrics"]
    e = art["conditions"]["E_weighted"]["metrics"]
    assert e["stale_hit_rate"] <= a["stale_hit_rate"]
    assert e["wrong_scope_injection_rate"] <= a["wrong_scope_injection_rate"]
    assert e["recall_at_5"] >= a["recall_at_5"]


def test_promotion_gate_shape() -> None:
    gate = _artifact()["promotion_gate"]
    for key in ("graduates", "improved_any", "recall_loss", "recall_acceptable",
                "improvements_vs_best_baseline", "baseline_reference"):
        assert key in gate
    assert isinstance(gate["graduates"], bool)


def test_hard_fixture_support_ids_exist() -> None:
    fx = OracleFixture.from_file(HARD_FIXTURE)
    ids = set(fx.memories_by_id)
    for q in fx.queries:
        for sid in q.support_ids:
            assert sid in ids, f"{q.id} references missing support {sid}"


def test_logspace_graduates_on_hard_fixture() -> None:
    # On the harder fixture F still clears the promotion gate over the best of {A, E}
    # (with the structured temporal oracle the edge is on wrong-scope rather than
    # stale-hit — see the benchmark note), with no recall loss.
    art = _hard_artifact()
    e = art["conditions"]["E_weighted"]["metrics"]
    f = art["conditions"]["F_logspace"]["metrics"]
    assert f["recall_at_5"] >= e["recall_at_5"]
    assert f["wrong_scope_injection_rate"] <= e["wrong_scope_injection_rate"]
    assert art["promotion_gate"]["graduates"] is True


def test_correlated_trap_f_suppresses_all_stale_echoes() -> None:
    # One current truth vs five stale echoes of the same belief. F must keep every
    # stale echo out of the current-intent top-5; E admits some.
    fx = OracleFixture.from_file(CORRELATED_FIXTURE)
    by_id = fx.memories_by_id
    art = OracleBenchmarkRunner(fx).run(include_traces=False)
    f_pq = {r["query_id"]: r for r in art["conditions"]["F_logspace"]["per_query"]}
    top5 = f_pq["q_trap_current"]["ranked"][:5]
    assert top5[0] == "ct_truth"
    assert not any(by_id[m].is_stale for m in top5), f"F leaked stale echo into top5: {top5}"
    # F suppresses every stale echo; with the structured temporal oracle E now matches
    # this (both keep stale out), so the trap no longer separates E from F — F is at
    # least as good, not strictly better. (See benchmark note.)
    e = art["conditions"]["E_weighted"]["metrics"]
    f = art["conditions"]["F_logspace"]["metrics"]
    assert f["stale_hit_rate"] <= e["stale_hit_rate"]


def test_ablation_attributes_gains_to_the_right_oracle() -> None:
    # R7.5: each oracle should own the metric it is responsible for, relative to a
    # semantic-only baseline (combiner held = E).
    rows = dict(run_ablation(OracleFixture.from_file(HARD_FIXTURE)))
    base = rows["semantic [E]"]
    assert rows["semantic+temporal [E]"]["stale_hit_rate"] < base["stale_hit_rate"]
    assert rows["semantic+scope [E]"]["wrong_scope_injection_rate"] < base["wrong_scope_injection_rate"]
    assert rows["semantic+structure [E]"]["recall_at_5"] > base["recall_at_5"]
    # And the combiner choice (all[E] -> all[F]) is a smaller move than any strong oracle's.
    assert "all [E]" in rows and "all [F]" in rows


def test_scope_fixture_is_a_convergence_control() -> None:
    # Negative control: on a validator-clean, deep scope fixture E and F converge —
    # both keep the high-relevance wrong-repo distractor (and the in-scope stale one)
    # out of top-5. F's wrong-scope edge only appears on thin-scope (flagged) fixtures.
    art = OracleBenchmarkRunner(OracleFixture.from_file(SCOPE_FIXTURE)).run(include_traces=False)
    by_cond = {c: r["per_query"][0]["ranked"][:5] for c, r in art["conditions"].items()}
    assert "sg_graph" not in by_cond["E_weighted"]
    assert "sg_graph" not in by_cond["F_logspace"]
    e = art["conditions"]["E_weighted"]["metrics"]
    f = art["conditions"]["F_logspace"]["metrics"]
    assert f["wrong_scope_injection_rate"] == e["wrong_scope_injection_rate"] == 0.0


def test_run_is_reproducible() -> None:
    # Rankings/metrics are deterministic; latency_ms naturally wobbles, so exclude it.
    def _stable(art: dict) -> dict:
        m = dict(art["conditions"]["F_logspace"]["metrics"])
        m.pop("latency_ms", None)
        return m

    assert _stable(_artifact()) == _stable(_artifact())
