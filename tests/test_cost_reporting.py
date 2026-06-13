"""Regression tests for cost summary and report surfaces."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from archolith_bench.core.display import print_summary
from archolith_bench.core.metrics import PricingModel
from archolith_bench.core.report import write_benchmarks_md
from archolith_bench.suites.proxy import _compute_cost_summary


def test_cost_summary_persists_passthrough_delta_fields() -> None:
    """The run summary stores both arm cost and passthrough delta fields."""
    pricing = PricingModel(
        provider="test",
        input_full=1.0,
        input_cache_hit=0.1,
        input_cache_miss=1.0,
        output=2.0,
    )
    results = [
        {
            "turn": 1,
            "direct": {"input_tokens": 1_000_000, "output_tokens": 0},
            "trace": {
                "turn": 1,
                "cache_hit_tokens": 500_000,
                "cache_miss_tokens": 0,
                "prompt_tokens_actual": 500_000,
                "output_tokens": 0,
            },
        }
    ]

    summary = _compute_cost_summary(results, pricing)

    assert summary["total_effective_cost_usd"] == pytest.approx(0.05, abs=1e-6)
    assert summary["passthrough_effective_cost_usd"] == pytest.approx(1.0, abs=1e-6)
    assert summary["cost_delta_usd"] == pytest.approx(-0.95, abs=1e-6)
    assert summary["cost_delta_vs_passthrough"] == pytest.approx(-0.95, abs=1e-6)
    assert summary["cost_delta_ratio"] == pytest.approx(-0.95, abs=1e-6)
    assert summary["cache_data_available"] is True
    assert summary["passthrough_cache_data_available"] is False


def test_benchmarks_report_includes_direct_baseline_and_cache_caveat(tmp_path: Path) -> None:
    """The markdown report can compare against direct-arm files but caveats missing cache data."""
    direct = {
        "scenario": "long_agent",
        "arm": "direct",
        "budget": None,
        "summary": {
            "total_direct_input_tokens": 1_000,
            "total_proxy_input_tokens": 1_000,
            "overall_savings_ratio": 0.0,
            "total_effective_cost_usd": 1.0,
            "cache_data_available": False,
        },
    }
    proxy = {
        "scenario": "long_agent",
        "arm": "proxy_plus_filter",
        "budget": None,
        "summary": {
            "total_direct_input_tokens": 1_000,
            "total_proxy_input_tokens": 500,
            "overall_savings_ratio": 0.5,
            "total_effective_cost_usd": 0.5,
            "cache_data_available": True,
        },
    }

    (tmp_path / "benchmark_long_agent_direct.json").write_text(json.dumps(direct), encoding="utf-8")
    (tmp_path / "benchmark_long_agent_proxy_plus_filter.json").write_text(json.dumps(proxy), encoding="utf-8")

    out_path = tmp_path / "BENCHMARKS.md"
    write_benchmarks_md(tmp_path, out_path)

    report = out_path.read_text(encoding="utf-8")
    assert "| long_agent | direct | default |" in report
    assert "| long_agent | proxy_plus_filter | default |" in report
    assert "INCONCLUSIVE (no cache data)" in report
    assert "PROXY CHEAPER" not in report


def test_print_summary_keeps_header_without_cost(capsys: pytest.CaptureFixture[str]) -> None:
    """Pricing remains optional; no-cost summaries still render their table header."""
    data = {
        "scenario": "long_agent",
        "budget": None,
        "arm": "direct",
        "turns_run": 1,
        "turns_total": 1,
        "aborted": False,
        "summary": {
            "total_direct_input_tokens": 100,
            "total_proxy_input_tokens": 100,
            "total_savings_tokens": 0,
            "overall_savings_ratio": 0.0,
            "collapsed_turns": [],
            "collapse_rate": 0.0,
        },
        "turns": [
            {
                "turn": 1,
                "direct": {"input_tokens": 100, "output_tokens": 20, "latency_ms": 10},
                "arm": {"input_tokens": 100, "output_tokens": 20, "latency_ms": 10},
                "trace": {
                    "input_tokens": 100,
                    "rewritten_tokens": 100,
                    "savings_tokens": 0,
                    "savings_ratio": 0.0,
                    "assembly_mode": "direct",
                    "facts_stored": 0,
                },
            }
        ],
    }

    print_summary(data)

    output = capsys.readouterr().out
    assert "Direct In" in output
    assert "Arm In" in output
