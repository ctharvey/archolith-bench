"""Smoke tests for archolith-bench suites without live proxy.

These tests use bundled corpora and fixtures to validate that the
filter and audit suites work without requiring API keys or a live proxy.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from archolith_bench.core.corpus import list_corpora
from archolith_bench.suites.audit import run_audit_comparison
from archolith_bench.suites.filter import run_filter_suite


@pytest.fixture
def project_root() -> Path:
    """Return the project root directory."""
    return Path(__file__).parent.parent


@pytest.fixture
def fixtures_dir(project_root: Path) -> Path:
    """Return the fixtures directory."""
    return project_root / "fixtures"


@pytest.fixture
def corpora_dir(project_root: Path) -> Path:
    """Return the corpora directory."""
    return project_root / "corpora"


@pytest.fixture
def results_dir(tmp_path: Path) -> Path:
    """Return a temporary results directory."""
    return tmp_path / "results"


def test_filter_suite_bundled_corpora(
    corpora_dir: Path,
    results_dir: Path,
) -> None:
    """Test filter suite on bundled corpora without live proxy."""
    if not corpora_dir.exists():
        pytest.skip(f"Corpora directory not found: {corpora_dir}")

    samples = list_corpora(corpora_dir)
    if not samples:
        pytest.skip("No corpus samples found")

    results, summary = run_filter_suite(corpora_dir=corpora_dir, output_dir=results_dir)

    # Validate that results were generated
    assert summary is not None, "Summary should not be None"
    assert isinstance(summary, dict), "Summary should be a dict"
    assert "total_samples" in summary, "Summary should have total_samples"
    assert summary["total_samples"] > 0, "At least one sample should be processed"
    assert "aggregate_savings_ratio" in summary, "Summary should have aggregate_savings_ratio"


def test_audit_suite_bundled_fixtures(
    fixtures_dir: Path,
    results_dir: Path,
) -> None:
    """Test audit suite on bundled fixtures without live proxy."""
    before_path = fixtures_dir / "audit_before.json"
    after_path = fixtures_dir / "audit_after.json"

    if not before_path.exists():
        pytest.skip(f"Before fixture not found: {before_path}")
    if not after_path.exists():
        pytest.skip(f"After fixture not found: {after_path}")

    result = run_audit_comparison(
        before_path=before_path,
        after_path=after_path,
        output_dir=results_dir,
    )

    # Validate that comparison was successful
    assert result is not None, "Result should not be None"
    assert isinstance(result, dict), "Result should be a dict"
    assert "before_total_tokens" in result, "Result should have before_total_tokens"
    assert "after_total_tokens" in result, "Result should have after_total_tokens"
    assert "token_reduction" in result, "Result should have token_reduction"
    assert "waste_reduction" in result, "Result should have waste_reduction"
    assert "per_server" in result, "Result should have per_server data"
