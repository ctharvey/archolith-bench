"""Smoke tests for archolith-bench CLI."""

from __future__ import annotations

import subprocess
import sys


def test_cli_help() -> None:
    """Test that --help exits with code 0."""
    result = subprocess.run(
        [sys.executable, "-m", "archolith_bench", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"Expected exit code 0, got {result.returncode}"
    assert "archolith-bench" in result.stdout or "archolith-bench" in result.stderr


def test_proxy_list() -> None:
    """Test that proxy --list exits with code 0."""
    result = subprocess.run(
        [sys.executable, "-m", "archolith_bench", "proxy", "--list"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"Expected exit code 0, got {result.returncode}"
    assert "Available scenarios" in result.stdout or "scenarios" in result.stdout.lower()


def test_industry_cli_json(tmp_path) -> None:
    """Test that industry coverage can be generated without API keys."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "archolith_bench",
            "industry",
            "--format",
            "json",
            "--output-dir",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"Expected exit code 0, got {result.returncode}: {result.stderr}"
    assert "INDUSTRY BENCHMARK COVERAGE" in result.stdout
    assert (tmp_path / "industry_benchmarks.json").exists()


def test_industry_cli_shared_evidence(tmp_path) -> None:
    """Test that existing suites can publish shared evidence records."""
    evidence_path = tmp_path / "industry-evidence.md"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "archolith_bench",
            "industry",
            "--format",
            "json",
            "--output-dir",
            str(tmp_path),
            "--publish-evidence",
            str(evidence_path),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, f"Expected exit code 0, got {result.returncode}: {result.stderr}"
    assert evidence_path.exists()
    text = evidence_path.read_text(encoding="utf-8")
    assert "Industry benchmark registry evidence" in text
    assert "Public copy allowed: `false`" in text


def test_menhir_list_cli() -> None:
    """Test that the first-class Menhir group lists capability gates."""
    result = subprocess.run(
        [sys.executable, "-m", "archolith_bench", "menhir", "list"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, f"Expected exit code 0, got {result.returncode}: {result.stderr}"
    assert "Capability Evidence Registry" in result.stdout
    assert "facet retrieval" in result.stdout


def test_menhir_r1_cli_publishes_evidence(tmp_path) -> None:
    """Test a deterministic Menhir runner and shared evidence artifact."""
    result_path = tmp_path / "r1.json"
    evidence_path = tmp_path / "r1-evidence.md"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "archolith_bench",
            "menhir",
            "r1",
            "--out",
            str(result_path),
            "--publish-evidence",
            str(evidence_path),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, f"Expected exit code 0, got {result.returncode}: {result.stderr}"
    assert result_path.exists()
    assert evidence_path.exists()
    text = evidence_path.read_text(encoding="utf-8")
    assert "Menhir R1 hybrid retrieval" in text
    assert "Public copy allowed: `false`" in text
