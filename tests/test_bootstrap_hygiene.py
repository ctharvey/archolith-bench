"""Acceptance tests for the Menhir startup hygiene benchmark."""

from __future__ import annotations

import json
from pathlib import Path

from archolith_bench.bootstrap_hygiene import BootstrapFixture, BootstrapHygieneRunner
from archolith_bench.cli import main


FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "menhir_bootstrap_hygiene.json"


def test_offline_bootstrap_hygiene_gate_passes() -> None:
    artifact = BootstrapHygieneRunner(BootstrapFixture.from_file(FIXTURE)).run()

    assert artifact["passed"] is True
    assert artifact["metrics"]["structural_recent_leakage_count"] == 0
    assert artifact["metrics"]["cross_workspace_recent_leakage_count"] == 0
    assert artifact["metrics"]["cross_workspace_flagged_leakage_count"] == 0
    assert artifact["metrics"]["general_pin_recall_rate"] == 1.0
    assert artifact["metrics"]["workspace_pin_recall_rate"] == 1.0
    assert artifact["metrics"]["stale_anchor_advisory_preserved"] == 1.0


def test_cli_writes_offline_artifact(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    out = tmp_path / "artifact.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            "archolith-bench",
            "menhir",
            "bootstrap-hygiene",
            "--offline",
            "--fixture",
            str(FIXTURE),
            "--out",
            str(out),
        ],
    )

    main()

    artifact = json.loads(out.read_text(encoding="utf-8"))
    assert artifact["passed"] is True
    assert artifact["mode"] == "offline"
