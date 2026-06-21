"""Tier 2 metric-quality regressions."""

from __future__ import annotations

import httpx

from archolith_bench.core.scenario import FactProbe, Scenario
from archolith_bench.suites import probes
from archolith_bench.suites.continuity import ContinuityTracker, _extract_file_paths


def test_keyword_hit_matches_simple_morphology() -> None:
    assert probes._keyword_hit("run", "The tests are running now.")
    assert probes._keyword_hit("migration order", "The migration ordering is the blocker.")
    assert not probes._keyword_hit("deploy", "The tests are running now.")


def test_run_fact_probes_uses_morphology_aware_hits(monkeypatch) -> None:
    scenario = Scenario(
        name="probe",
        description="probe",
        system_prompt="system",
        turns=[],
        fact_probes=[
            FactProbe(
                after_turn=1,
                question="What happened?",
                expected_keywords=["run", "migration order"],
            )
        ],
    )
    responses = iter([
        "We need to run the migration order check.",
        "The migration ordering check is running.",
    ])

    monkeypatch.setattr(probes, "send_chat", lambda *args, **kwargs: (next(responses), 1.0, {}))

    with httpx.Client() as client:
        result = probes.run_fact_probes(
            client,
            scenario,
            direct_history=[],
            arm_history=[],
            proxy_url="http://proxy.test/v1",
            direct_url="http://direct.test/v1",
            model="unit-model",
            current_turn=1,
            api_key="test-key",
        )

    assert result[0]["direct_hits"] == 2
    assert result[0]["arm_hits"] == 2


def test_extract_file_paths_handles_windows_relative_dotfiles_and_no_ext() -> None:
    text = (
        "Read C:\\Users\\thron\\repo\\src\\app.py, src/config, .env, "
        "README, and ./scripts/run_tests before rerunning."
    )

    paths = _extract_file_paths(text)

    assert "C:\\Users\\thron\\repo\\src\\app.py" in paths
    assert "src/config" in paths
    assert ".env" in paths
    assert "README" in paths
    assert "./scripts/run_tests" in paths


def test_continuity_tracker_counts_repeat_relative_paths() -> None:
    tracker = ContinuityTracker()

    first = tracker.observe_turn(1, "Updated src/config and .env.")
    second = tracker.observe_turn(2, "Checked src/config again.")

    assert first["new_files"] == 2
    assert second["repeat_files"] == 1
    assert tracker.compute().repeat_file_reads == 1
