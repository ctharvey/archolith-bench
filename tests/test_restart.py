"""Offline tests for restart/bootstrap orientation scoring."""

from __future__ import annotations

import httpx
import pytest

from archolith_bench.core.scenario import Scenario
from archolith_bench.suites import restart


def _scenario() -> Scenario:
    return Scenario(
        name="restart",
        description="restart scoring",
        system_prompt="You are testing restart scoring.",
        turns=["Find the blocker", "Choose the next step"],
    )


def test_restart_bootstrap_scores_recalled_context(monkeypatch: pytest.MonkeyPatch) -> None:
    responses = iter([
        "The blocker is migration ordering in /tmp/app.py.",
        "The next step is rerun python tests after fixing migration ordering.",
        "The blocker was migration ordering and next step is rerun python tests.",
    ])

    monkeypatch.setattr(restart, "send_chat", lambda *args, **kwargs: (next(responses), 10.0, {}))

    with httpx.Client() as client:
        result = restart.run_restart_bootstrap(
            client,
            _scenario(),
            proxy_url="http://proxy.test/v1",
            direct_url="http://direct.test/v1",
            model="unit-model",
            api_key="test-key",
        )

    assert result["orientation_score"] > 0
    assert result["explicit_reread"] is False
    assert result["facts_recalled"] > 0


def test_restart_bootstrap_flags_reread_without_penalizing_recalled_facts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses = iter([
        "The blocker is migration ordering.",
        "The next step is rerun python tests after fixing migration ordering.",
        "I should re-read the files before saying; migration ordering may be the blocker.",
    ])

    monkeypatch.setattr(restart, "send_chat", lambda *args, **kwargs: (next(responses), 10.0, {}))

    with httpx.Client() as client:
        result = restart.run_restart_bootstrap(
            client,
            _scenario(),
            proxy_url="http://proxy.test/v1",
            direct_url="http://direct.test/v1",
            model="unit-model",
            api_key="test-key",
        )

    assert result["explicit_reread"] is True
    assert result["reread_intent_penalized"] is False
    assert result["orientation_score"] >= result["fact_recovery"]
