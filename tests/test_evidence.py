"""Tests for the shared evidence publisher."""

from __future__ import annotations

import json

from archolith_bench.core.evidence import EvidenceRecord, publish_evidence


def test_publish_evidence_markdown(tmp_path) -> None:
    record = EvidenceRecord(
        title="Test Evidence",
        command="archolith-bench test",
        commit="abc123",
        product="menhir",
        ability="facet retrieval",
        fixture_or_live_source="fixtures/demo.json",
        model_provider="offline",
        environment_caveats=["fixture only"],
        public_copy_allowed=False,
        metric_rows=[{"condition": "A", "score": 1.0}],
        artifact={"ok": True},
    )

    out = publish_evidence(record, tmp_path / "evidence.md")
    text = out.read_text(encoding="utf-8")

    assert "Test Evidence" in text
    assert "archolith-bench test" in text
    assert "Public copy allowed: `false`" in text
    assert "| condition | score |" in text


def test_publish_evidence_json(tmp_path) -> None:
    record = EvidenceRecord(
        title="Test Evidence",
        command="archolith-bench test",
        commit="abc123",
        product="menhir",
        ability="facet retrieval",
        fixture_or_live_source="fixtures/demo.json",
        model_provider="offline",
        environment_caveats=[],
        public_copy_allowed=True,
        metric_rows=[],
        artifact={"ok": True},
    )

    out = publish_evidence(record, tmp_path / "evidence.json")
    data = json.loads(out.read_text(encoding="utf-8"))

    assert data["public_copy_allowed"] is True
    assert data["artifact"] == {"ok": True}
