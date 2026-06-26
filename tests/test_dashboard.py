"""Offline tests for the live benchmark dashboard (no network, no running benchmark)."""

from __future__ import annotations

import json

from archolith_bench.dashboard import (
    _parse_checkpoint_name,
    read_checkpoint,
    render,
    render_html,
    scan_runs,
)


def _write_checkpoint(path, records):
    with open(path, "w", encoding="utf-8") as f:
        for arm, task_id, correct, in_tok, out_tok in records:
            f.write(json.dumps({
                "arm": arm,
                "task_id": task_id,
                "result": {
                    "task_id": task_id, "response_text": "x", "input_tokens": in_tok,
                    "output_tokens": out_tok, "latency_ms": 1.0, "correct": correct, "raw_usage": {},
                },
            }) + "\n")


def test_parse_checkpoint_name_handles_hyphenated_benchmark():
    from pathlib import Path
    b, v, m = _parse_checkpoint_name(Path(".checkpoint_longmemeval-menhir_oracle_deepseek-v4-flash.jsonl"))
    assert b == "longmemeval-menhir"
    assert v == "oracle"
    assert m == "deepseek-v4-flash"


def test_read_checkpoint_aggregates_and_computes_lift(tmp_path):
    ck = tmp_path / ".checkpoint_longmemeval-menhir_oracle_deepseek-v4-flash.jsonl"
    _write_checkpoint(ck, [
        ("no_memory", "q1", False, 100, 5),
        ("no_memory", "q2", False, 100, 5),
        ("menhir_recall", "q1", True, 900, 20),
        ("menhir_recall", "q2", False, 900, 20),
    ])
    snap = read_checkpoint(ck)
    assert snap.benchmark == "longmemeval-menhir"
    assert snap.arms["no_memory"].n == 2
    assert snap.arms["no_memory"].score == 0.0
    assert snap.arms["menhir_recall"].n == 2
    assert snap.arms["menhir_recall"].score == 0.5
    assert snap.arms["menhir_recall"].input_tokens == 1800
    assert snap.total_done == 4
    assert snap.lift == 0.5  # 0.5 - 0.0


def test_lift_none_when_one_arm_missing(tmp_path):
    ck = tmp_path / ".checkpoint_longmemeval-menhir_oracle_x.jsonl"
    _write_checkpoint(ck, [("no_memory", "q1", True, 1, 1)])
    snap = read_checkpoint(ck)
    assert snap.lift is None


def test_read_checkpoint_tolerates_torn_final_line(tmp_path):
    ck = tmp_path / ".checkpoint_b_oracle_m.jsonl"
    _write_checkpoint(ck, [("no_memory", "q1", True, 1, 1)])
    with open(ck, "a", encoding="utf-8") as f:
        f.write('{"arm": "no_memory", "task_id": "q2", "resu')  # torn write from a hard kill
    snap = read_checkpoint(ck)
    assert snap.arms["no_memory"].n == 1  # the good record survives, torn line ignored


def test_scan_and_render_smoke(tmp_path):
    ck = tmp_path / ".checkpoint_longmemeval-menhir_oracle_deepseek-v4-flash.jsonl"
    _write_checkpoint(ck, [
        ("no_memory", "q1", False, 100, 5),
        ("menhir_recall", "q1", True, 900, 20),
    ])
    snaps = scan_runs(tmp_path)
    assert len(snaps) == 1
    out = render(snaps, {"health": True, "queue_depth": 0, "startup_mode": "full"},
                 total_items=500, rate_per_min=2.0, eta_min=10.0)
    assert "longmemeval-menhir" in out
    assert "menhir: UP" in out
    assert "memory lift" in out


def test_scan_runs_empty_dir(tmp_path):
    assert scan_runs(tmp_path) == []


def test_render_html_is_valid_autorefreshing_page(tmp_path):
    ck = tmp_path / ".checkpoint_longmemeval-menhir_oracle_deepseek-v4-flash.jsonl"
    _write_checkpoint(ck, [
        ("no_memory", "q1", False, 100, 5),
        ("menhir_recall", "q1", True, 900, 20),
    ])
    snaps = scan_runs(tmp_path)
    html = render_html(snaps, {"health": True, "queue_depth": 0, "startup_mode": "full"},
                       total_items=500, refresh_s=5)
    assert html.startswith("<!doctype html>")
    # Auto-refreshes in place (preserves open <details> + scroll) instead of a full
    # meta-refresh page reload.
    assert 'http-equiv="refresh"' not in html
    assert "setInterval" in html and "replaceWith" in html
    assert 'id="content"' in html
    assert "longmemeval-menhir" in html
    assert "menhir UP" in html
    assert "memory lift" in html


def test_render_html_handles_no_runs_and_no_menhir():
    html = render_html([], None, total_items=None)
    assert "<!doctype html>" in html
    assert "No checkpoints yet" in html
