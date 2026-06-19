"""Industry benchmark coverage suite."""

from __future__ import annotations

import json
from pathlib import Path

from ..core.industry import (
    industry_benchmarks_json,
    render_industry_benchmarks_markdown,
    write_industry_benchmarks,
)


def run_industry_suite(
    output_dir: Path = Path("results"),
    *,
    product: str | None = None,
    suite: str | None = None,
    launch_only: bool = False,
) -> dict:
    """Write the industry benchmark matrix to results/ and return it."""
    output_dir.mkdir(parents=True, exist_ok=True)
    data = industry_benchmarks_json(product=product, suite=suite, launch_only=launch_only)
    path = output_dir / "industry_benchmarks.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    md_path = output_dir / "industry_benchmarks.md"
    write_industry_benchmarks(
        md_path,
        product=product,
        suite=suite,
        launch_only=launch_only,
        output_format="markdown",
    )
    return data


def print_industry_summary(data: dict) -> None:
    """Print a compact industry benchmark coverage table."""
    benchmarks = data.get("benchmarks", [])
    print(f"\n{'='*96}")
    print("  INDUSTRY BENCHMARK COVERAGE")
    print(f"{'='*96}")
    print(f"  {'Product':<20} {'Suite':<8} {'Benchmark':<26} {'Status':<24}")
    print(f"  {'-'*20} {'-'*8} {'-'*26} {'-'*24}")
    for entry in benchmarks:
        print(
            f"  {entry['product']:<20} {entry['suite']:<8} "
            f"{entry['name']:<26} {entry['status']:<24}"
        )
    print()


def render_industry_suite_markdown(
    *,
    product: str | None = None,
    suite: str | None = None,
    launch_only: bool = False,
) -> str:
    """Expose markdown rendering for CLI callers."""
    return render_industry_benchmarks_markdown(
        product=product,
        suite=suite,
        launch_only=launch_only,
    )
