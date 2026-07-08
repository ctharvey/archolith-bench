"""Offline tests for the expanded Phase 3 scenario suite.

A stateful per-namespace fake models the HAPPY menhir consumer (F1 semantic-family voting +
F2 unique-target corrections) so every scenario — including the characterization ones — passes
in the ideal model. Failure injection then proves the gate/characterization split behaves.
"""

from __future__ import annotations

import json

from archolith_bench.harness import (
    default_scenarios,
    run_scenario,
    run_scenario_suite,
    scenario_result_to_dict,
    suite_verdict,
)


class ScenarioFakeClient:
    """Per-namespace fake modeling menhir Phase 3 consolidation for the scenario fixtures.

    Deterministically batch-re-folds all posted prompts into counter Views, then applies bare
    numeric corrections to the UNIQUE value-matching View (abstaining when >1 match) — the F1/F2
    behavior the scenarios assert. `merge_count_and_spend=False` models menhir NOT extracting a
    separate count from "2 bikes for $125" (drives the characterization scenario to DIVERGE).
    """

    def __init__(self, *, merge_count_and_spend: bool = False,
                 negative_correction_binds: bool = True) -> None:
        self.merge_count_and_spend = merge_count_and_spend
        self.negative_correction_binds = negative_correction_binds
        self._posts: dict[str, list[str]] = {}
        self.reset_calls = 0

    def reset_phase3(self, namespace: str) -> dict:
        self.reset_calls += 1
        self._posts.pop(namespace, None)
        return {"namespace": namespace, "nodes_deleted": 0, "turn_evidence_deleted": 0}

    def post_turn_evidence(self, namespace: str, text: str, *, triage_reason=None,
                           turn_key=None, **_) -> dict:
        self._posts.setdefault(namespace, []).append(text)
        return {"turn_id": "t", "created": True, "recorded_at": "now"}

    def run_phase3(self, namespace: str, *, k: int = 3, source: str = "perception") -> dict:
        return {"views_written": 0, "abstained": 0, "corrections_applied": 0, "llm_calls": 0}

    def phase3_status(self, namespace: str) -> dict:
        return {"namespace": namespace, "dirty": bool(self._posts.get(namespace)), "turn_evidence": 0}

    def _measures(self, prompt: str) -> list[tuple[str, str, float]]:
        """(subject, counter, value) measures a prompt yields — matches the fixture strings."""
        p = prompt.lower()
        if "movies" in p and "watch list" in p:
            return [("movies", "movies_watchlist", 25.0)]
        if "books" in p and "this year" in p:
            return [("books", "books_read", 25.0)]
        if "50 dollars and 75 dollars" in p:
            return [("bike", "bike_spend", 125.0)]
        if "one bike for $50" in p:
            return [("bike", "bike_spend", 125.0)]
        if "2 bikes for $125" in p:
            spend = [("bike", "bike_spend", 125.0)]
            return spend if self.merge_count_and_spend else [("bike", "bikes_count", 2.0), *spend]
        return []

    def _correction(self, prompt: str) -> tuple[float, float] | None:
        p = prompt.lower()
        if "20, not 25" in p:
            return (25.0, 20.0)
        if "not 25 anymore, it is 20" in p and self.negative_correction_binds:
            return (25.0, 20.0)
        # consumer-quality-pack v1 additions: arrow ("25 -> 20") and reverse ("to 20 from 25").
        if "25 -> 20" in p or "to 20 from 25" in p:
            return (25.0, 20.0)
        return None

    def fetch_views(self, namespace: str, *, limit: int = 100) -> dict:
        views: dict[str, dict] = {}
        corrections: list[tuple[float, float]] = []
        for prompt in self._posts.get(namespace, []):
            for subject, counter, value in self._measures(prompt):
                views[counter] = {
                    "subject": subject, "counter": counter, "value": value,
                    "current": True, "history": [], "superseded": [],
                }
            corr = self._correction(prompt)
            if corr:
                corrections.append(corr)
        for old, new in corrections:
            matches = [v for v in views.values() if v["value"] == old]
            if len(matches) == 1:  # unique target -> supersede; else abstain (touch nothing)
                v = matches[0]
                v["superseded"] = [{"value": old, "current": False,
                                    "valid_at": "t1", "expired_at": "t2"}]
                v["value"] = new
        current = list(views.values())
        return {"namespace": namespace, "count": len(current), "views": current, "receipts": []}

    def recall(self, namespace: str, query: str, limit: int = 10) -> list[str]:
        return []

    def close(self) -> None:
        pass


def test_default_scenarios_shape():
    scenarios = default_scenarios()
    ids = {s.scenario_id for s in scenarios}
    assert ids == {
        "ambiguous-correction", "currency-worded-sum", "count-vs-spend",
        "negative-correction", "arrow-correction", "multi-namespace",
    }
    # count-vs-spend is the only remaining characterization (non-gate) scenario; negative-correction
    # and arrow-correction were promoted to gates once menhir's correction resolver handled the
    # "not OLD anymore" and arrow / reverse from-to forms.
    non_gate = {s.scenario_id for s in scenarios if not s.gate}
    assert non_gate == {"count-vs-spend"}


def test_happy_model_passes_every_scenario():
    client = ScenarioFakeClient(merge_count_and_spend=False, negative_correction_binds=True)
    results = run_scenario_suite(client, base_namespace="scn-test")
    for r in results:
        assert r.passed, f"{r.scenario_id} failed: {[a.__dict__ for a in r.assertions if not a.passed]}"
    assert suite_verdict(results) is True


def test_ambiguous_correction_leaves_both_views_untouched():
    client = ScenarioFakeClient()
    scenario = next(s for s in default_scenarios() if s.scenario_id == "ambiguous-correction")
    r = run_scenario(client, scenario, base_namespace="scn-amb")
    assert r.passed
    # both movies and books remain 25 (the bare correction had two 25-valued targets -> abstain)
    labels = {a.label: a.passed for a in r.assertions}
    assert labels["movies still 25 after ambiguous correction"]
    assert labels["books still 25 after ambiguous correction"]


def test_count_vs_spend_characterization_diverges_when_menhir_merges():
    # If menhir does NOT emit a separate count, the characterization scenario "diverges" but the
    # SUITE VERDICT still holds (non-gate) -- documents behavior without failing the run.
    client = ScenarioFakeClient(merge_count_and_spend=True)
    results = run_scenario_suite(client, base_namespace="scn-cvs")
    cvs = next(r for r in results if r.scenario_id == "count-vs-spend")
    assert cvs.gate is False
    assert cvs.passed is False  # diverged: no distinct count View
    assert suite_verdict(results) is True  # non-gate divergence does not fail the suite


def test_negative_correction_is_a_gate_and_regression_fails_suite():
    # negative-correction is now a GATE: if menhir stops binding the "not OLD anymore, it is NEW"
    # form (regression), the scenario fails AND the suite verdict fails.
    client = ScenarioFakeClient(negative_correction_binds=False)
    results = run_scenario_suite(client, base_namespace="scn-neg")
    neg = next(r for r in results if r.scenario_id == "negative-correction")
    assert neg.gate is True
    assert neg.passed is False  # stayed 25, never superseded
    assert suite_verdict(results) is False  # a gate regression fails the suite


def test_negative_correction_passes_when_bound():
    client = ScenarioFakeClient(negative_correction_binds=True)
    results = run_scenario_suite(client, base_namespace="scn-neg-ok")
    neg = next(r for r in results if r.scenario_id == "negative-correction")
    assert neg.gate is True and neg.passed is True


def test_multi_namespace_independence():
    client = ScenarioFakeClient()
    scenario = next(s for s in default_scenarios() if s.scenario_id == "multi-namespace")
    r = run_scenario(client, scenario, base_namespace="scn-mns")
    assert r.passed
    assert len(r.namespaces_used) == 2
    assert len(set(r.namespaces_used)) == 2  # two distinct namespaces
    independence = next(a for a in r.assertions if a.kind == "independence")
    assert independence.passed


def test_gate_failure_fails_suite_verdict():
    # A gate scenario failing (e.g. currency SUM does not fold) must fail the suite verdict.
    class NoFoldClient(ScenarioFakeClient):
        def _measures(self, prompt: str):
            if "50 dollars and 75 dollars" in prompt.lower():
                return []  # currency SUM never commits -> gate scenario fails
            return super()._measures(prompt)

    results = run_scenario_suite(NoFoldClient(), base_namespace="scn-gate")
    currency = next(r for r in results if r.scenario_id == "currency-worded-sum")
    assert currency.gate is True
    assert currency.passed is False
    assert suite_verdict(results) is False


def test_phase3_client_post_carries_provenance():
    # The live Phase3MenhirClient must send additive source_client/hook_version provenance
    # (menhir stores them; older builds ignore unknown body fields).
    from archolith_bench.harness import Phase3MenhirClient

    class _Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"turn_id": "t", "created": True, "recorded_at": "now"}

    captured = {}

    class _Inner:
        def post(self, url, json=None, headers=None):  # noqa: A002
            captured["url"] = url
            captured["json"] = json
            return _Resp()

        def close(self):
            pass

    client = Phase3MenhirClient("http://localhost:9")
    client._client = _Inner()
    client.post_turn_evidence("ns", "I have 25 movies on my watch list.", triage_reason=["number"])
    assert captured["url"].endswith("/api/turn-evidence")
    assert captured["json"]["source_client"] == "archolith_bench"
    assert captured["json"]["hook_version"] == "menhir-phase3-bench-v1"
    assert captured["json"]["text"].startswith("I have 25")


def test_scenario_result_serializable():
    client = ScenarioFakeClient()
    results = run_scenario_suite(client, base_namespace="scn-json")
    json.dumps([scenario_result_to_dict(r) for r in results])  # must not raise


def test_stub_phase3_client_drives_core_flow_and_suite():
    # The shipped StubPhase3Client (used by the CLI --offline path) must satisfy BOTH the core
    # run_phase3 flow and the scenario suite with a passing verdict — the CI-safe smoke contract.
    from archolith_bench.harness import (
        StubPhase3Client,
        default_phase3_cases,
        run_phase3,
    )

    client = StubPhase3Client()
    result = run_phase3(client, cases=default_phase3_cases(), reset_confirmed=True,
                        menhir_url="offline-stub", model="offline-stub")
    assert result.verdict is True
    assert result.metrics["wrong_view_writes"] == 0
    assert result.metrics["silent_abstentions"] == 0
    assert result.metrics["duplicate_writes_on_rerun"] == 0
    assert result.metrics["watermark_debounce_hit"] is True

    suite = run_scenario_suite(client, base_namespace="stub-suite")
    assert suite_verdict(suite) is True


def test_cli_offline_menhir_phase3_smoke(tmp_path):
    # End-to-end CLI smoke of the --offline path: no menhir, no network, exit 0.
    from archolith_bench.cli import main

    out = tmp_path / "phase3_offline.json"
    try:
        main(["harness", "menhir-phase3", "--offline-fixture", "stub",
              "--format", "json", "--out", str(out)])
    except SystemExit as exc:  # main() sys.exits(1) only on a verdict failure
        assert exc.code in (None, 0), f"offline smoke should pass, exited {exc.code}"
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["verdict"] == "pass"
    assert data["scenario_suite"]["gate_passed"] is True
    assert len(data["scenario_suite"]["scenarios"]) == 6
