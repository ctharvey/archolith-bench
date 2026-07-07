"""Offline tests for the Menhir Phase 3 View-consolidation benchmark driver.

A stateful fake models menhir's Phase 3 behavior over the driver's fixed call sequence
(reset -> capture -> run#1 -> idempotent re-fold -> correction -> run#3 -> inspect), so the
driver, per-case validators, metrics, and report writers are covered without a live server.
"""

from __future__ import annotations

import json

import pytest

from archolith_bench.harness import (
    MenhirPhase3Adapter,
    default_phase3_cases,
    is_phase3,
    phase3_result_to_dict,
    run_phase3,
    write_phase3_evidence,
)
from archolith_bench.harness.menhir_phase3 import fixture_hash


class FakePhase3Client:
    """Deterministic in-memory stand-in for Phase3MenhirClient.

    Models the happy path unless a defect is injected: `never_supersede` leaves the corrected
    measure stale (25), `abstained_per_run` emits abstentions with no receipt (silent).
    """

    def __init__(self, *, never_supersede: bool = False, abstained_per_run: int = 0) -> None:
        self.never_supersede = never_supersede
        self.abstained_per_run = abstained_per_run
        self.dirty = False
        self.correction_posted = False
        self.correction_applied = False
        self.runs = 0
        self.reset_calls = 0

    def reset_phase3(self, namespace: str) -> dict:
        self.reset_calls += 1
        self.dirty = False
        self.correction_posted = False
        self.correction_applied = False
        self.runs = 0
        return {"namespace": namespace, "nodes_deleted": 0, "turn_evidence_deleted": 0}

    def post_turn_evidence(self, namespace: str, text: str, *, triage_reason=None, **_) -> dict:
        if "not 25" in text or text.lower().startswith("actually"):
            self.correction_posted = True
        self.dirty = True
        return {"turn_id": "t", "created": True, "recorded_at": "now"}

    def phase3_status(self, namespace: str) -> dict:
        return {"namespace": namespace, "dirty": self.dirty, "turn_evidence": 3}

    def run_phase3(self, namespace: str, *, k: int = 3, source: str = "perception") -> dict:
        self.runs += 1
        self.dirty = False
        corrections = 0
        if self.correction_posted and not self.correction_applied and not self.never_supersede:
            self.correction_applied = True
            corrections = 1
        return {
            "namespace": namespace,
            "phase3_selected": True,
            "dirty_after": False,
            "namespaces_dirty": 1,
            "namespaces_processed": 1,
            "views_written": 2 if self.runs == 1 else 0,
            "abstained": self.abstained_per_run,
            "corrections_applied": corrections,
            "llm_calls": 6,
        }

    def fetch_views(self, namespace: str, *, limit: int = 100) -> dict:
        views: list[dict] = []
        if self.runs >= 1:
            if self.correction_applied:
                movies = {
                    "subject": "movies",
                    "counter": "movies_watchlist",
                    "value": 20.0,
                    "current": True,
                    "history": [
                        {"value": 20.0, "current": True, "valid_at": "t2", "expired_at": None},
                        {"value": 25.0, "current": False, "valid_at": "t1", "expired_at": "t2"},
                    ],
                    "superseded": [
                        {"value": 25.0, "current": False, "valid_at": "t1", "expired_at": "t2"}
                    ],
                }
            else:
                movies = {
                    "subject": "movies",
                    "counter": "movies_watchlist",
                    "value": 25.0,
                    "current": True,
                    "history": [{"value": 25.0, "current": True, "valid_at": "t1", "expired_at": None}],
                    "superseded": [],
                }
            bike = {
                "subject": "bike",
                "counter": "bike_spend",
                "value": 125.0,
                "current": True,
                "history": [{"value": 125.0, "current": True, "valid_at": "t1", "expired_at": None}],
                "superseded": [],
            }
            views = [movies, bike]
        return {"namespace": namespace, "count": len(views), "views": views, "receipts": []}

    def recall(self, namespace: str, query: str, limit: int = 10) -> list[str]:
        return ["movies watchlist 20"] if self.runs >= 1 else []

    def close(self) -> None:
        pass


def test_is_phase3_and_adapter_cases():
    adapter = MenhirPhase3Adapter()
    assert is_phase3(adapter)
    assert adapter.benchmark_id == "menhir-phase3"
    assert len(adapter.cases()) == 4


def test_fixture_hash_is_stable():
    assert fixture_hash(default_phase3_cases()) == fixture_hash(default_phase3_cases())


def test_run_phase3_requires_reset_confirmation():
    with pytest.raises(ValueError, match="confirm-menhir-reset"):
        run_phase3(FakePhase3Client(), reset_confirmed=False)


def test_happy_path_passes_all_cases():
    client = FakePhase3Client()
    result = run_phase3(client, reset_confirmed=True, menhir_url="http://localhost:9",
                        model="fake")
    assert client.reset_calls == 1
    assert result.verdict is True
    assert {c.case_id: c.passed for c in result.cases} == {
        "phase3-movies-stated": True,
        "phase3-bike-sum": True,
        "phase3-movies-correction": True,
        "phase3-junk-drop": True,
    }
    m = result.metrics
    assert m["turn_evidence_submitted"] == 3  # movies + bike + correction (junk dropped)
    assert m["turn_evidence_dropped"] == 1
    assert m["views_current"] == 2
    assert m["views_superseded"] == 1
    assert m["supersessions_applied"] == 1
    assert m["duplicate_writes_on_rerun"] == 0
    assert m["wrong_view_writes"] == 0
    assert m["silent_abstentions"] == 0
    assert m["watermark_debounce_hit"] is True
    assert m["re_dirtied_after_new_evidence"] is True


def test_stale_correction_flags_wrong_view_write_and_fails():
    client = FakePhase3Client(never_supersede=True)
    result = run_phase3(client, reset_confirmed=True, menhir_url="http://localhost:9")
    assert result.verdict is False
    correction = next(c for c in result.cases if c.kind == "correction")
    assert correction.passed is False
    # the movies View is still 25 (stale) -> counts as a wrong write vs the corrected target
    assert result.metrics["wrong_view_writes"] >= 1


def test_silent_abstention_fails_verdict():
    client = FakePhase3Client(abstained_per_run=1)
    result = run_phase3(client, reset_confirmed=True, menhir_url="http://localhost:9")
    assert result.metrics["abstentions"] >= 1
    assert result.metrics["silent_abstentions"] >= 1
    assert result.verdict is False


def test_report_writers_markdown_and_json(tmp_path):
    result = run_phase3(FakePhase3Client(), reset_confirmed=True,
                        menhir_url="http://localhost:9", model="fake")

    md = write_phase3_evidence(result, tmp_path / "phase3.md", output_format="markdown")
    text = md.read_text(encoding="utf-8")
    assert "# Menhir Phase 3 View Consolidation Benchmark" in text
    assert "Wrong View writes" in text
    assert "## Reproduction command" in text

    js = write_phase3_evidence(result, tmp_path / "phase3.json", output_format="json")
    data = json.loads(js.read_text(encoding="utf-8"))
    assert data["verdict"] == "pass"
    assert data["benchmark_id"] == "menhir-phase3"
    assert data["metrics"]["wrong_view_writes"] == 0
    assert len(data["cases"]) == 4


def test_result_to_dict_is_json_serializable():
    result = run_phase3(FakePhase3Client(), reset_confirmed=True, menhir_url="http://localhost:9")
    json.dumps(phase3_result_to_dict(result))  # must not raise
