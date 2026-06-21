"""Offline coverage for the proxy suite's main run loop."""

from __future__ import annotations

from pathlib import Path

import pytest

from archolith_bench.core.scenario import Scenario
from archolith_bench.suites.checkpoints import checkpoint_path, save_checkpoint
from archolith_bench.suites import proxy


def _scenario(turns: list[str]) -> Scenario:
    return Scenario(
        name="unit",
        description="unit test scenario",
        system_prompt="You are testing.",
        turns=turns,
    )


def _patch_offline_dependencies(
    monkeypatch: pytest.MonkeyPatch,
    *,
    completion_tokens: int = 80,
    text: str = "Finished the planned implementation and verification.",
) -> list[list[dict]]:
    calls: list[list[dict]] = []

    def fake_send_chat(client, base_url, api_key, messages, model, **kwargs):
        calls.append(list(messages))
        return text, 12.0, {
            "prompt_tokens": len(messages) * 10,
            "completion_tokens": completion_tokens,
        }

    monkeypatch.setattr(proxy, "send_chat", fake_send_chat)
    monkeypatch.setattr(proxy, "snapshot_proxy_config", lambda *args, **kwargs: {"mode": "test"})
    return calls


def test_run_benchmark_direct_arm_runs_offline(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls = _patch_offline_dependencies(monkeypatch)

    data = proxy.run_benchmark(
        _scenario(["first turn", "second turn"]),
        "direct",
        proxy_url="http://proxy.test/v1",
        direct_url="http://direct.test/v1",
        model="unit-model",
        output_dir=tmp_path,
        api_key="test-key",
        run_probes=False,
        run_restart=False,
    )

    assert data["turns_run"] == 2
    assert data["aborted"] is False
    assert data["summary"]["total_direct_input_tokens"] == 60
    assert data["summary"]["upstream_input_reduction_ratio"] == 0.0
    assert len(calls) == 2
    assert not checkpoint_path(tmp_path, "unit", "direct", None).exists()


def test_run_benchmark_resume_preserves_checkpointed_results(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _patch_offline_dependencies(monkeypatch)
    ckpt = checkpoint_path(tmp_path, "unit", "direct", None)
    saved_result = {
        "turn": 1,
        "user_msg_preview": "first turn",
        "user_msg": "first turn",
        "direct": {"input_tokens": 10, "output_tokens": 80, "latency_ms": 12.0, "response": "done"},
        "arm": {"input_tokens": 10, "output_tokens": 80, "latency_ms": 12.0, "response": "done"},
        "trace": {
            "assembly_mode": "direct",
            "input_tokens": 10,
            "rewritten_tokens": 10,
            "savings_tokens": 0,
            "savings_ratio": 0.0,
            "facts_stored": 0,
            "assembly_latency_ms": 0.0,
            "extraction_latency_ms": 0.0,
            "session_id": "",
            "cache_hit_tokens": 0,
            "cache_miss_tokens": 0,
            "prompt_tokens_actual": 10,
            "output_tokens": 80,
            "turn": 1,
        },
        "continuity": {},
    }
    save_checkpoint(
        ckpt,
        "unit",
        "direct",
        None,
        [saved_result],
        [],
        [{"role": "system", "content": "You are testing."}, {"role": "user", "content": "first turn"}],
        [{"role": "system", "content": "You are testing."}, {"role": "user", "content": "first turn"}],
        "session-1",
    )

    data = proxy.run_benchmark(
        _scenario(["first turn", "second turn"]),
        "direct",
        proxy_url="http://proxy.test/v1",
        direct_url="http://direct.test/v1",
        model="unit-model",
        output_dir=tmp_path,
        resume=True,
        api_key="test-key",
        run_probes=False,
        run_restart=False,
    )

    assert data["turns_run"] == 2
    assert data["turns"][0]["turn"] == 1
    assert data["turns"][1]["turn"] == 2
    assert data["summary"]["total_direct_input_tokens"] == 40
    assert not ckpt.exists()


def test_run_benchmark_aborts_after_consecutive_collapses(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _patch_offline_dependencies(monkeypatch, completion_tokens=1, text="ok")

    data = proxy.run_benchmark(
        _scenario(["first turn", "second turn", "third turn"]),
        "direct",
        proxy_url="http://proxy.test/v1",
        direct_url="http://direct.test/v1",
        model="unit-model",
        output_dir=tmp_path,
        api_key="test-key",
        run_probes=False,
        run_restart=False,
    )

    assert data["turns_run"] == 2
    assert data["aborted"] is True
    assert data["abort_reason"] == "output_collapse_2_consecutive"
    assert data["summary"]["collapsed_turns"] == [1, 2]


def test_run_benchmark_checkpoint_json_is_removed_after_success(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _patch_offline_dependencies(monkeypatch)

    proxy.run_benchmark(
        _scenario(["first turn"]),
        "direct",
        proxy_url="http://proxy.test/v1",
        direct_url="http://direct.test/v1",
        model="unit-model",
        output_dir=tmp_path,
        api_key="test-key",
        run_probes=False,
        run_restart=False,
    )

    assert list(tmp_path.glob(".checkpoint_*.json")) == []
