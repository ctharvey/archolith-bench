"""Tests for the L4 benchmark runner — the without/with_l4 contrast and invariant guards."""

from __future__ import annotations

from pathlib import Path

from archolith_bench.l4.models import ArtifactFixture
from archolith_bench.l4.runner import L4Task, run_l4_benchmark, run_task

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "l4_failure_demo.json"


def _result() -> dict:
    fixture = ArtifactFixture.from_file(FIXTURE)
    return run_l4_benchmark(fixture)


def test_fixture_loads_and_runs() -> None:
    out = _result()
    assert out["fixture"] == "l4_failure_demo"
    assert len(out["tasks"]) == 1


def test_l4_flips_failed_approach_and_first_action() -> None:
    # the headline: the Failure artifact flips both metrics 0 -> 1.
    conds = _result()["tasks"][0]["conditions"]
    assert conds["without_l4"]["metrics"]["failed_approach_surfaced"] == 0.0
    assert conds["with_l4"]["metrics"]["failed_approach_surfaced"] == 1.0
    assert conds["without_l4"]["metrics"]["first_action_quality"] == 0.0
    assert conds["with_l4"]["metrics"]["first_action_quality"] == 1.0


def test_with_l4_keeps_invariants() -> None:
    m = _result()["tasks"][0]["conditions"]["with_l4"]["metrics"]
    assert m["evidence_present"] == 1.0           # every TRUSTED fact carries evidence
    assert m["stale_or_conflict_flagged"] == 1.0  # superseded reads historical, not fact
    assert m["decision_accuracy_per_token"] > 0.0


def test_candidate_never_surfaces_as_fact_in_run() -> None:
    brief = _result()["tasks"][0]["conditions"]["with_l4"]["brief"]
    fact_ids = {i["artifact_id"] for bucket in ("failed_approaches", "decisions", "risks")
                for i in brief[bucket]}
    # the LLM candidate and the evidence-less human note must be hypotheses, not facts.
    assert "floor_guess" not in fact_ids
    assert "floor_hunch" not in fact_ids
    hyp_ids = {i["artifact_id"] for i in brief["hypotheses"]}
    assert {"floor_guess", "floor_hunch"} <= hyp_ids


def test_run_is_deterministic() -> None:
    assert _result() == _result()


def test_baseline_ids_control_without_l4_corpus() -> None:
    fixture = ArtifactFixture.from_file(FIXTURE)
    task = L4Task.from_dict({"id": "t", "text": "tighten the similarity floor",
                             "anchors": ["scoring_service.py"], "gold_failure": "floor_fail",
                             "baseline_ids": ["floor_fail"]})
    conds = run_task(fixture.artifacts, task)["conditions"]
    # with floor_fail in the baseline, even without_l4 surfaces it.
    assert conds["without_l4"]["metrics"]["failed_approach_surfaced"] == 1.0
