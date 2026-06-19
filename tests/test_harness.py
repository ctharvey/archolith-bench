"""Offline tests for the external benchmark harness (no network, no API spend)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from archolith_bench.core.api import DIRECT_URL
from archolith_bench.harness import (
    ABResult,
    get_adapter,
    run_ab,
    write_harness_evidence,
)
from archolith_bench.harness.longbench_v2 import LongBenchV2Adapter, _extract_choice

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "longbench_v2_sample.json"


def _make_send_fn(answer_by_task: dict[str, str], proxy_input_tokens: int | None = None):
    """Build a deterministic send_fn keyed by the gold letter in the prompt.

    Returns the mapped answer per task. When proxy_input_tokens is set, proxy arms
    report fewer input tokens than direct so token-reduction deltas are non-zero.
    """

    def send_fn(client, base_url, api_key, messages, model, **kwargs):
        # Identify task by its question text (present in the user message).
        user = next((m["content"] for m in messages if m["role"] == "user"), "")
        ans = "A"
        for marker, letter in answer_by_task.items():
            if marker in user:
                ans = letter
                break
        is_proxy = base_url != DIRECT_URL and proxy_input_tokens is not None
        inp = proxy_input_tokens if is_proxy else 1000
        return ans, 1.0, {"prompt_tokens": inp, "completion_tokens": 2}

    return send_fn


def test_longbench_load_tasks_from_fixture():
    adapter = LongBenchV2Adapter()
    tasks = adapter.load_tasks(fixture_path=FIXTURE)
    assert len(tasks) == 4
    assert tasks[0].answer == "A"
    assert tasks[1].answer == "B"
    assert any("ARENA_MAX" in m["content"] for m in tasks[2].prompt_messages)


def test_longbench_subset_and_limit():
    adapter = LongBenchV2Adapter()
    tasks = adapter.load_tasks(subset="single_document_qa", fixture_path=FIXTURE)
    assert len(tasks) == 2
    limited = adapter.load_tasks(limit=1, fixture_path=FIXTURE)
    assert len(limited) == 1


def test_extract_choice():
    assert _extract_choice("The answer is B.") == "B"
    assert _extract_choice("answer: C") == "C"
    assert _extract_choice("(D)") == "D"
    assert _extract_choice("A") == "A"
    assert _extract_choice("I am not sure") == ""


def test_score_letter_matching():
    adapter = LongBenchV2Adapter()
    tasks = adapter.load_tasks(fixture_path=FIXTURE)
    assert adapter.score(tasks[1], "The answer is B") is True
    assert adapter.score(tasks[1], "A") is False


def test_run_ab_offline_scores_and_deltas(tmp_path):
    adapter = LongBenchV2Adapter()
    # Map each task's question to a returned letter: get 3/4 right on every arm.
    answers = {
        "satellite uplink operate": "A",   # gold A -> correct
        "silt-corrected reservoir": "B",   # gold B -> correct
        "raises the heap arena cap": "A",  # gold A -> correct
        "launch date slip": "A",           # gold C -> wrong
    }
    ab = run_ab(
        adapter,
        arms=("direct", "proxy_only", "proxy_plus_filter"),
        fixture_path=FIXTURE,
        send_fn=_make_send_fn(answers, proxy_input_tokens=600),
        configure_proxy=False,
    )
    assert isinstance(ab, ABResult)
    assert ab.arms["direct"].n == 4
    assert ab.arms["direct"].score == 0.75
    # Proxy arms send fewer input tokens -> positive reduction delta vs direct.
    assert ab.deltas["proxy_only"]["input_token_reduction_pct"] > 0
    assert ab.deltas["proxy_only"]["score_delta"] == 0.0

    out = write_harness_evidence(ab, tmp_path / "ev.json", output_format="json")
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["benchmark_id"] == "longbench-v2"
    assert data["arms"]["direct"]["score"] == 0.75


def test_get_adapter_unknown_raises():
    try:
        get_adapter("does-not-exist")
    except KeyError as e:
        assert "available" in str(e)
    else:
        raise AssertionError("expected KeyError for unknown benchmark_id")


def test_harness_cli_offline(tmp_path):
    result = subprocess.run(
        [
            sys.executable, "-m", "archolith_bench", "harness", "longbench-v2",
            "--offline-fixture", str(FIXTURE),
            "--format", "json",
            "--output-dir", str(tmp_path),
        ],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert (tmp_path / "harness_longbench-v2.json").exists()


def test_harness_cli_list():
    result = subprocess.run(
        [sys.executable, "-m", "archolith_bench", "harness", "--list"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "longbench-v2" in result.stdout
