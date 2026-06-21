"""Report persistence and BENCHMARKS.md generation tests."""

from __future__ import annotations

import json
from pathlib import Path

from archolith_bench.core.report import save_results, write_benchmarks_md


def _run_result() -> dict:
    return {
        "scenario": "unit",
        "model": "unit-model",
        "budget": None,
        "arm": "proxy_only",
        "turns_run": 1,
        "summary": {
            "total_direct_input_tokens": 1_000,
            "total_proxy_input_tokens": 600,
            "overall_savings_ratio": 0.7,
            "upstream_input_reduction_ratio": 0.4,
        },
        "quality": {"recall_preservation": 1.0},
        "turns": [
            {
                "turn": 1,
                "user_msg": "hello",
                "direct": {
                    "input_tokens": 1_000,
                    "output_tokens": 20,
                    "latency_ms": 5.0,
                    "response": "direct response",
                },
                "arm": {
                    "input_tokens": 600,
                    "output_tokens": 20,
                    "latency_ms": 6.0,
                    "response": "arm response",
                },
            }
        ],
    }


def test_save_results_writes_json_and_transcripts(tmp_path: Path) -> None:
    path = save_results(_run_result(), tmp_path)

    assert path.exists()
    assert json.loads(path.read_text(encoding="utf-8"))["scenario"] == "unit"
    assert (tmp_path / "transcripts" / "unit_proxy_only_direct.md").exists()
    assert (tmp_path / "transcripts" / "unit_proxy_only_arm.md").exists()


def test_write_benchmarks_md_includes_stale_caveat_and_separate_savings(tmp_path: Path) -> None:
    (tmp_path / "benchmark_unit_proxy_only.json").write_text(json.dumps(_run_result()), encoding="utf-8")

    out_path = tmp_path / "BENCHMARKS.md"
    write_benchmarks_md(tmp_path, out_path)

    report = out_path.read_text(encoding="utf-8")
    assert "Stale evidence caveat" in report
    assert "Upstream Input Reduction" in report
    assert "Internal Curation Savings" in report
    assert "| unit | proxy_only | default | 1,000 | 600 | 40.0% | 70.0% | 100% |" in report
