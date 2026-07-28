from __future__ import annotations

import json
from pathlib import Path

from archolith_bench.ci import stratified


def test_slice_types_match_official_cached_dataset() -> None:
    assert stratified.DEFAULT_SLICE_TYPES == (
        "temporal-reasoning",
        "multi-session",
        "knowledge-update",
        "single-session-user",
        "single-session-assistant",
        "single-session-preference",
    )


def test_incomplete_type_result_fails_closed(tmp_path: Path, monkeypatch) -> None:
    output = tmp_path / "one.json"
    output.write_text(
        json.dumps({"arms": {"menhir_recall": {"score": 1.0, "n": 1, "results": []}}}),
        encoding="utf-8",
    )

    class Completed:
        returncode = 0
        stderr = ""

    monkeypatch.setattr(stratified.subprocess, "run", lambda *args, **kwargs: Completed())
    result = stratified._run_one_type(
        menhir_url="http://127.0.0.1:8090",
        q_type="knowledge-update",
        limit=20,
        out_file=output,
        judge_model="gpt-4o-mini",
        scorer="llm-judge",
        recall_limit=10,
        extra_args=None,
        dry_run=False,
    )
    assert result.error == "incomplete slice: expected 20 questions, got 1"
