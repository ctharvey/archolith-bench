"""Tests for industry benchmark coverage registry."""

from __future__ import annotations

from pathlib import Path

from archolith_bench.core.industry import (
    INDUSTRY_BENCHMARKS,
    industry_benchmarks_json,
    render_industry_benchmarks_markdown,
    write_industry_benchmarks,
)
from archolith_bench.suites.industry import run_industry_suite


def test_registry_covers_launch_products() -> None:
    products = {entry.product for entry in INDUSTRY_BENCHMARKS}

    assert "archolith-context" in products
    assert "archolith-filter" in products
    assert "archolith-audit" in products
    assert "archolith-security" in products


def test_registry_has_required_source_fields() -> None:
    for entry in INDUSTRY_BENCHMARKS:
        assert entry.benchmark_id
        assert entry.name
        assert entry.source_url.startswith("https://")
        assert entry.paper_url.startswith("https://")
        assert entry.launch_gate
        assert entry.run_command


def test_json_filter_by_product() -> None:
    data = industry_benchmarks_json(product="archolith-context")

    assert data["total"] >= 1
    assert {entry["product"] for entry in data["benchmarks"]} == {"archolith-context"}


def test_json_filter_by_security_suite() -> None:
    data = industry_benchmarks_json(suite="security")

    assert data["total"] >= 3
    assert {entry["suite"] for entry in data["benchmarks"]} == {"security"}
    assert {"CyberSecEval 4", "AgentDojo", "OWASP LLM Top 10 + ASVS"}.issubset(
        {entry["name"] for entry in data["benchmarks"]}
    )


def test_markdown_mentions_candidate_caveat() -> None:
    markdown = render_industry_benchmarks_markdown(launch_only=True)

    assert "candidate-before-launch" in markdown
    assert "must not be claimed" in markdown


def test_write_industry_benchmarks_json(tmp_path: Path) -> None:
    out = tmp_path / "industry.json"

    write_industry_benchmarks(out, output_format="json", product="archolith-filter")

    text = out.read_text(encoding="utf-8")
    assert '"suite": "industry"' in text
    assert "archolith-filter" in text


def test_run_industry_suite_writes_outputs(tmp_path: Path) -> None:
    data = run_industry_suite(output_dir=tmp_path, launch_only=True)

    assert data["total"] >= 1
    assert (tmp_path / "industry_benchmarks.json").exists()
    assert (tmp_path / "industry_benchmarks.md").exists()
