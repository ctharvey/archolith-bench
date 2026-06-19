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
