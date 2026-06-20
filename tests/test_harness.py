"""Offline tests for the external benchmark harness (no network, no API spend)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from archolith_bench.core.api import DIRECT_URL
from archolith_bench.harness import (
    ABResult,
    AgentDojoAdapter,
    BigCodeBenchHardAdapter,
    CyberSecEvalAdapter,
    MtebAdapter,
    SweBenchAdapter,
    get_adapter,
    is_external,
    run_ab,
    run_external_ab,
    write_harness_evidence,
)
from archolith_bench.harness.longbench_v2 import LongBenchV2Adapter, _extract_choice

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
FIXTURE = FIXTURES / "longbench_v2_sample.json"


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
    for bid in ("longbench-v2", "bigcodebench-hard", "swe-bench", "cyberseceval-4",
                "agentdojo", "mteb-retrieval"):
        assert bid in result.stdout


# ---- BigCodeBench (in-process, real code execution) ----

BCB_FIXTURE = FIXTURES / "bigcodebench_hard_sample.json"


def test_bigcodebench_load_and_score():
    adapter = BigCodeBenchHardAdapter()
    tasks = adapter.load_tasks(fixture_path=BCB_FIXTURE)
    assert len(tasks) == 1
    good = "```python\ndef add(a, b):\n    return a + b\n```"
    bad = "```python\ndef add(a, b):\n    return a - b\n```"
    assert adapter.score(tasks[0], good) is True
    assert adapter.score(tasks[0], bad) is False


def test_bigcodebench_run_ab_executes(tmp_path):
    adapter = BigCodeBenchHardAdapter()

    def send_fn(client, base_url, api_key, messages, model, **kwargs):
        return "```python\ndef add(a, b):\n    return a + b\n```", 1.0, {
            "prompt_tokens": 100, "completion_tokens": 20,
        }

    ab = run_ab(adapter, arms=("direct",), fixture_path=BCB_FIXTURE,
                send_fn=send_fn, configure_proxy=False)
    assert ab.arms["direct"].score == 1.0


# ---- External-harness wrappers (parser + A/B over fixtures) ----

def test_external_adapters_are_external():
    for a in (SweBenchAdapter(), CyberSecEvalAdapter(), AgentDojoAdapter(), MtebAdapter()):
        assert is_external(a)


def test_swebench_parse_summary():
    adapter = SweBenchAdapter()
    s = adapter.parse_summary({"total_instances": 10, "resolved_instances": 4})
    assert s["n"] == 10 and s["score"] == 0.4


def test_mteb_parse_summary_mean():
    adapter = MtebAdapter()
    s = adapter.parse_summary({"results": [{"main_score": 0.7}, {"main_score": 0.5}]})
    assert s["n"] == 2 and abs(s["score"] - 0.6) < 1e-9


def test_run_external_ab_with_per_arm_fixtures(tmp_path):
    adapter = SweBenchAdapter()
    # direct uses more input tokens than the proxy arm -> positive reduction delta.
    direct_f = tmp_path / "direct.json"
    proxy_f = tmp_path / "proxy.json"
    direct_f.write_text(json.dumps(
        {"total_instances": 10, "resolved_instances": 4, "input_tokens": 100000, "output_tokens": 2000}))
    proxy_f.write_text(json.dumps(
        {"total_instances": 10, "resolved_instances": 4, "input_tokens": 60000, "output_tokens": 2000}))
    ab = run_external_ab(
        adapter,
        arms=("direct", "proxy_only"),
        configure_proxy=False,
        results_fixtures={"direct": direct_f, "proxy_only": proxy_f},
    )
    assert ab.arms["direct"].score == 0.4
    assert ab.deltas["proxy_only"]["input_token_reduction_pct"] == 40.0
    assert ab.deltas["proxy_only"]["score_delta"] == 0.0


def test_harness_cli_external_offline(tmp_path):
    result = subprocess.run(
        [
            sys.executable, "-m", "archolith_bench", "harness", "swe-bench",
            "--arms", "direct,proxy_only",
            "--offline-fixture", str(FIXTURES / "swebench_report_sample.json"),
            "--format", "json", "--output-dir", str(tmp_path),
        ],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert (tmp_path / "harness_swe-bench.json").exists()
