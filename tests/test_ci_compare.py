"""Tests for the compare/gate logic."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from archolith_bench.ci.compare import (
    Baseline,
    GateResult,
    compare_results,
    load_baseline,
)


def _make_baseline(
    overall: float = 0.230,
    by_type: dict[str, float] | None = None,
    per_question: dict[str, dict] | None = None,
) -> Baseline:
    return Baseline(
        baseline_version="test",
        baseline_commit="abc123",
        stratified_slice_hash="sha256:test",
        overall=overall,
        by_type=by_type or {
            "temporal-reasoning": 0.350,
            "multi-session": 0.180,
            "knowledge-update": 0.220,
            "single-session-user": 0.300,
            "single-session-assistant": 0.150,
            "single-session-preference": 0.180,
        },
        per_question=per_question or {},
    )


def test_pass_when_overall_within_threshold():
    baseline = _make_baseline(overall=0.230)
    result = compare_results(baseline, current_overall=0.247, current_by_type={
        "temporal-reasoning": 0.350, "multi-session": 0.180, "knowledge-update": 0.220,
        "single-session-user": 0.300, "single-session-assistant": 0.150,
        "single-session-preference": 0.180,
    })
    assert result.gate == GateResult.PASS
    assert abs(result.overall_delta - 0.017) < 1e-9
    assert "+7.4%" in f"{result.overall_pct_delta:+.1f}%"


def test_fail_when_overall_below_threshold():
    baseline = _make_baseline(overall=0.230)
    result = compare_results(baseline, current_overall=0.200, current_by_type={
        "temporal-reasoning": 0.350, "multi-session": 0.180, "knowledge-update": 0.220,
        "single-session-user": 0.300, "single-session-assistant": 0.150,
        "single-session-preference": 0.180,
    })
    assert result.gate == GateResult.FAIL
    assert result.overall_delta == -0.030


def test_warn_when_overall_pass_but_one_type_regressed():
    baseline = _make_baseline(overall=0.230)
    result = compare_results(baseline, current_overall=0.247, current_by_type={
        "temporal-reasoning": 0.350, "multi-session": 0.180, "knowledge-update": 0.050,  # -0.17
        "single-session-user": 0.350, "single-session-assistant": 0.250,
        "single-session-preference": 0.350,
    })
    assert result.gate == GateResult.WARN
    assert "knowledge-update" in result.gate_reason


def test_regression_detection_in_per_question():
    per_q_base = {
        "Q-001": {"type": "temporal-reasoning", "score": 1.0},
        "Q-002": {"type": "multi-session", "score": 0.0},
    }
    per_q_cur = {
        "Q-001": {"type": "temporal-reasoning", "score": 0.0},  # was ✓ now ✗ → regression
        "Q-002": {"type": "multi-session", "score": 1.0},   # was ✗ now ✓ → improvement
    }
    baseline = _make_baseline(per_question=per_q_base)
    result = compare_results(
        baseline,
        current_overall=0.230,
        current_by_type={"temporal-reasoning": 0.0, "multi-session": 1.0, "knowledge-update": 0.220,
                         "single-session-user": 0.300, "single-session-assistant": 0.150,
                         "single-session-preference": 0.180},
        current_per_question=per_q_cur,
    )
    assert len(result.regressions) == 1
    assert result.regressions[0].id == "Q-001"
    assert len(result.improvements) == 1
    assert result.improvements[0].id == "Q-002"


def test_load_baseline_reads_json():
    raw = {
        "baseline_version": "2026-07-19-v1",
        "baseline_commit": "abc123",
        "stratified_slice_hash": "sha256:abc",
        "results": {
            "overall": 0.230,
            "by_type": {"temporal-reasoning": 0.350},
            "per_question": [{"id": "Q-001", "type": "temporal-reasoning", "score": 1.0}],
        },
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(raw, f)
        path = f.name
    try:
        b = load_baseline(path)
        assert b.baseline_version == "2026-07-19-v1"
        assert b.overall == 0.230
        assert b.by_type["temporal-reasoning"] == 0.350
        assert b.per_question["Q-001"]["type"] == "temporal-reasoning"
    finally:
        Path(path).unlink()


def test_load_baseline_rejects_stub_gate(tmp_path: Path):
    path = tmp_path / "stub.json"
    path.write_text(
        json.dumps({"baseline_version": "v1-stub", "results": {"overall": 0.0}}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="baseline is a stub"):
        load_baseline(path)


def test_type_delta_arrows():
    baseline = _make_baseline()
    result = compare_results(baseline, current_overall=0.230, current_by_type={
        "temporal-reasoning": 0.400,   # +0.050 → ▲
        "multi-session": 0.180,    # 0 → ─
        "knowledge-update": 0.220,
        "single-session-user": 0.300,
        "single-session-assistant": 0.100,   # -0.050 → ▼
        "single-session-preference": 0.180,
    })
    by_type_name = {td.type: td for td in result.type_deltas}
    assert by_type_name["temporal-reasoning"].status == "▲"
    assert by_type_name["multi-session"].status == "─"
    assert by_type_name["single-session-assistant"].status == "▼"
