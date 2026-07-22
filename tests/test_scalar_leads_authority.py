from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


def _load_fixture_module():
    script = Path(__file__).parents[1] / "scripts" / "scalar_leads_authority_live.py"
    spec = importlib.util.spec_from_file_location("scalar_leads_authority_live", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_leads_current_accepts_canonical_clock_zero_padding() -> None:
    fixture = _load_fixture_module()
    results = [{"name": "wake_time: 07:30", "content": None, "is_scalar_authority": True}]

    assert fixture._leads_current("7:30", results)


def test_leads_current_requires_authority_marker() -> None:
    fixture = _load_fixture_module()
    results = [{"name": "wake_time: 07:30", "content": None, "is_scalar_authority": False}]

    assert not fixture._leads_current("7:30", results)


def test_leads_current_keeps_numeric_boundaries() -> None:
    fixture = _load_fixture_module()
    results = [{"name": "I own 137 coins", "content": None, "is_scalar_authority": True}]

    assert not fixture._leads_current("37", results)


def test_structured_authority_verdict_is_a_distinct_leads_signal() -> None:
    fixture = _load_fixture_module()
    authority = [{
        "kind": "current",
        "status": "leads",
        "attribute": "wake_time",
        "value": "07:30",
    }]

    assert fixture._structured_leads_current("wake_time", "7:30", authority)
    assert not fixture._structured_leads_current("owned", "7:30", authority)
    assert not fixture._structured_leads_current(
        "wake_time", "7:30", [{**authority[0], "status": "advisory"}])


def test_measurement_exit_code_requires_materialized_proven_leads() -> None:
    fixture = _load_fixture_module()

    assert fixture._measurement_exit_code(True, True, 0) == 0
    assert fixture._measurement_exit_code(True, False, 0) == 1
    assert fixture._measurement_exit_code(True, True, 1) == 1
    assert fixture._measurement_exit_code(False, True, 0) == 2
