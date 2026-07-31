"""Offline tests for the live benchmark dashboard (no network, no running benchmark)."""

from __future__ import annotations

import json

from archolith_bench.dashboard import (
    _parse_checkpoint_name,
    _task_path,
    read_ingest_manifest,
    read_checkpoint,
    render,
    render_html,
    scan_ingests,
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


def test_task_path_normalizes_and_encodes_benchmark_item_ids():
    assert _task_path("42ec0761") == "/tasks/lme-42ec0761"
    assert _task_path("lme-42ec0761") == "/tasks/lme-42ec0761"
    assert _task_path("task with spaces") == "/tasks/lme-task%20with%20spaces"


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


def test_read_and_scan_ingest_manifest(tmp_path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps([
        {"question_id": "q1", "ready": 2, "failed_remaining": 0, "turn_evidence": 3, "scalar_views": 1},
        {"question_id": "q2", "ready": 4, "failed_remaining": 0, "turn_evidence": 5, "scalar_views": 2},
        {"question_id": "q3", "ready": 6, "failed_remaining": 0, "turn_evidence": 7, "scalar_views": 3},
    ]), encoding="utf-8")

    snap = read_ingest_manifest(manifest)
    assert snap.completed == 3
    assert snap.source == tmp_path.name
    assert scan_ingests(tmp_path) == [snap]


def test_render_html_shows_ingest_progress_before_scoring(tmp_path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps([
        {"question_id": "q1", "question": "One?", "ready": 2},
        {"question_id": "q2", "question": "Two?", "ready": 3},
        {"question_id": "q3", "question": "Three?", "ready": 4},
    ]), encoding="utf-8")

    html = render_html([], {"health": True}, total_items=78, ingests=scan_ingests(tmp_path))

    assert "LongMemEval graph ingest" in html
    assert "3/78 (3.8%)" in html
    assert "latest completed: Three?" in html
    assert "Graph ingest is active" in html
    assert "No ingest manifest" not in html


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
    assert "item ↗ task" in html
    assert "href='/tasks/lme-q1'" in html
    assert "Open task page" in html


def test_render_html_handles_no_runs_and_no_menhir():
    html = render_html([], None, total_items=None)
    assert "<!doctype html>" in html
    assert "No ingest manifest or scoring checkpoints yet" in html


def test_render_html_adds_scalar_viewer_only_when_enabled():
    plain = render_html([], None, total_items=None)
    viewer = render_html(
        [],
        None,
        total_items=None,
        scalar_viewer_enabled=True,
        scalar_default_namespace="lme-postcards",
    )

    assert 'id="scalar-viewer"' not in plain
    assert 'id="scalar-viewer"' in viewer
    assert "How one scalar view is made" in viewer
    assert 'const preferred = "lme-postcards"' in viewer
    assert "/api/scalar-task?namespace=" in viewer
    assert '"source " + when(t.occurred_at) : "source time unavailable"' in viewer
    assert "ingested ${when(t.recorded_at)}" in viewer
    assert 'picker.addEventListener("change", loadTask)' in viewer
    assert 'window.addEventListener("dashboard:refresh"' in viewer
    assert "graph unavailable" in viewer
    assert "scalar graph evidence is not available yet" in viewer
    assert "fold_outcome" in viewer
    assert "could not be folded" in viewer
    assert "ORIGINAL SOURCE TURN" in viewer
    assert "sourceTurnFor" in viewer
    assert "Original source turn unavailable in this graph" in viewer
    assert "Gate rejections remain in stage 2" in viewer
    assert 'id="scalar-open"' in viewer
    assert '"/tasks/" + encodeURIComponent(namespace)' in viewer
    assert "Memory map" in viewer
    assert "Task memory inventory" in viewer
    assert "DELTA-DERIVED" in viewer
    assert "ABSOLUTE" in viewer
    assert "ordinary relationship fact" in viewer
    assert '<a href="/tasks/">all tasks</a>' in viewer


def test_scalar_task_detail_page_uses_stable_task_url():
    viewer = render_html(
        [],
        None,
        total_items=None,
        scalar_viewer_enabled=True,
        scalar_default_namespace="lme-42ec0761",
        scalar_detail_page=True,
    )

    assert "const detailPage = true;" in viewer
    assert 'history.replaceState(null, "", taskPath)' in viewer
    assert 'const preferred = "lme-42ec0761"' in viewer


def test_render_html_task_directory_lists_and_filters_every_task():
    html = render_html(
        [],
        None,
        total_items=2,
        task_directory=[
            {
                "namespace": "lme-one",
                "question_id": "one",
                "question": "Where is the first item?",
                "answer": "Shelf",
                "question_type": "knowledge-update",
                "turns": 5,
                "typed_assertions": 2,
                "scalar_views": 1,
                "graph_available": True,
                "scoring": [
                    {"arm": "menhir_recall", "correct": True},
                    {"arm": "no_memory", "correct": False},
                ],
            },
            {
                "namespace": "lme-two",
                "question_id": "two",
                "question": "How many second items?",
                "answer": "2",
                "question_type": "single-session-user",
                "turns": 4,
                "typed_assertions": 1,
                "scalar_views": 0,
                "graph_available": False,
                "scoring": [],
            },
        ],
    )

    assert "All tasks <span>2</span>" in html
    assert "href='/tasks/lme-one'" in html
    assert "href='/tasks/lme-two'" in html
    assert "Where is the first item?" in html
    assert "memory &#10003;" in html
    assert "no memory &#10007;" in html
    assert "memory pending" in html
    assert "graph ready" in html
    assert "graph missing" in html
    assert "window.filterTaskDirectory" in html
    assert "taskSearch" in html and "taskScore" in html


def test_scalar_viewer_connects_only_versions_of_the_same_view():
    viewer = render_html(
        [],
        None,
        total_items=None,
        scalar_viewer_enabled=True,
    )

    assert "function scalarViewLaneKey(view)" in viewer
    assert "const stateLanes = new Map();" in viewer
    assert "stateLanes.get(key).push(view);" in viewer
    assert "i < lane.length - 1" in viewer
    assert "i < views.length - 1" not in viewer
    assert '<div class="view-lanes">${cards' in viewer
