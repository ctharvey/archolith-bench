"""Focused regressions for proxy-suite remediation fixes."""

from __future__ import annotations

import argparse
import inspect

from archolith_bench.cli import _add_common_proxy_args
from archolith_bench.suites.proxy import (
    _build_run_summary,
    _compute_upstream_input_reduction_ratio,
    _select_trace_turn,
    run_benchmark,
    run_experiment,
)
from archolith_bench.suites.stack import run_stack_suite


def test_trace_turn_selection_uses_one_based_loop_index():
    turns = [
        {"turn_number": 1, "value": "first"},
        {"turn_number": 2, "value": "second"},
        {"turn_number": 3, "value": "third"},
    ]

    assert _select_trace_turn(turns, 1)["value"] == "first"


def test_trace_turn_selection_falls_back_to_last_turn(capsys):
    turns = [{"turn_number": 2, "value": "second"}]

    assert _select_trace_turn(turns, 3)["value"] == "second"
    assert "trace turn 3 not found" in capsys.readouterr().out


def test_upstream_input_reduction_ratio_uses_direct_baseline():
    assert _compute_upstream_input_reduction_ratio(10_000, 6_000) == 0.4
    assert _compute_upstream_input_reduction_ratio(0, 6_000) == 0.0


def test_common_proxy_args_expose_poll_interval_default():
    parser = argparse.ArgumentParser()
    _add_common_proxy_args(parser)

    args = parser.parse_args([])

    assert args.poll_interval == 3.0


def test_proxy_entrypoints_accept_poll_interval():
    assert inspect.signature(run_benchmark).parameters["poll_interval_s"].default == 3.0
    assert inspect.signature(run_experiment).parameters["poll_interval_s"].default == 3.0
    assert inspect.signature(run_stack_suite).parameters["poll_interval_s"].default == 3.0


def test_build_run_summary_separates_internal_and_upstream_savings():
    results = [
        {
            "turn": 1,
            "direct": {"input_tokens": 100},
            "arm": {"input_tokens": 60, "output_tokens": 10},
            "trace": {"savings_tokens": 70},
        }
    ]

    summary = _build_run_summary(results, total_savings=70, pricing=None)

    assert summary["overall_savings_ratio"] == 0.7
    assert summary["upstream_input_reduction_ratio"] == 0.4
    assert summary["collapsed_turns"] == [1]
