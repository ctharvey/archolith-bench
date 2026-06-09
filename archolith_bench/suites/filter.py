"""Filter suite: measure archolith-filter compression ratios on real tool-output corpora.

For each corpus sample, runs filter_output (and shrink_oversized where relevant)
and records raw vs filtered token counts and ratio per command category.
Outputs per-category and aggregate token-savings percentages.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from archolith_filter import count_tokens, filter_output

from ..core.corpus import CATEGORY_FILTER_DEFAULTS, CorpusSample, list_corpora, load_sample


@dataclass
class FilterResult:
    name: str
    category: str
    raw_chars: int
    filtered_chars: int
    raw_tokens: int
    filtered_tokens: int
    savings_ratio: float
    truncated: bool


def run_filter_sample(sample: CorpusSample, command: str = "", tool: str = "") -> FilterResult:
    """Run filter_output on a single corpus sample and record metrics."""
    raw_text = load_sample(sample)

    # Use category-specific defaults so samples route to their specialised
    # filter instead of always hitting generic.
    use_defaults = not command and not tool
    if use_defaults:
        defaults = CATEGORY_FILTER_DEFAULTS.get(sample.category, {})
        command = defaults.get("command", "")
        tool = defaults.get("tool", "")

    # When defaults provide a tool but no command, do NOT fall back to
    # sample.name — that would override the tool-based classification.
    effective_command = command or ("" if (use_defaults and tool) else sample.name)

    result = filter_output(
        raw_text,
        command=effective_command,
        tool=tool,
    )

    raw_tokens = count_tokens(raw_text)
    filtered_tokens = count_tokens(result.output)
    savings_ratio = (raw_tokens - filtered_tokens) / raw_tokens if raw_tokens > 0 else 0.0

    return FilterResult(
        name=sample.name,
        category=sample.category,
        raw_chars=len(raw_text),
        filtered_chars=len(result.output),
        raw_tokens=raw_tokens,
        filtered_tokens=filtered_tokens,
        savings_ratio=round(savings_ratio, 4),
        truncated=result.truncated,
    )


def run_filter_suite(
    corpora_dir: Path | None = None,
    output_dir: Path = Path("results"),
) -> tuple[list[dict], dict]:
    """Run the filter suite across all corpus samples.

    Returns a list of per-sample result dicts plus an aggregate summary.
    """
    samples = list_corpora(corpora_dir)
    if not samples:
        print("No corpus samples found.")
        return []

    results: list[FilterResult] = []
    for sample in samples:
        print(f"  Filtering: {sample.name} ({sample.category})...")
        fr = run_filter_sample(sample)
        results.append(fr)
        print(f"    {fr.raw_tokens} -> {fr.filtered_tokens} tokens "
              f"({fr.savings_ratio:.1%} savings, truncated={fr.truncated})")

    by_category: dict[str, list[FilterResult]] = {}
    for r in results:
        by_category.setdefault(r.category, []).append(r)

    category_summaries = []
    for cat, cat_results in sorted(by_category.items()):
        total_raw = sum(r.raw_tokens for r in cat_results)
        total_filtered = sum(r.filtered_tokens for r in cat_results)
        cat_savings = (total_raw - total_filtered) / total_raw if total_raw > 0 else 0.0
        category_summaries.append({
            "category": cat,
            "samples": len(cat_results),
            "total_raw_tokens": total_raw,
            "total_filtered_tokens": total_filtered,
            "savings_ratio": round(cat_savings, 4),
        })

    total_raw = sum(r.raw_tokens for r in results)
    total_filtered = sum(r.filtered_tokens for r in results)
    aggregate_savings = (total_raw - total_filtered) / total_raw if total_raw > 0 else 0.0

    output_data = {
        "suite": "filter",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_samples": len(results),
        "total_raw_tokens": total_raw,
        "total_filtered_tokens": total_filtered,
        "aggregate_savings_ratio": round(aggregate_savings, 4),
        "per_category": category_summaries,
        "per_sample": [asdict(r) for r in results],
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "filter_results.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    print(f"\n  Filter results saved to {path}")
    print(f"  Aggregate: {total_raw:,} -> {total_filtered:,} tokens ({aggregate_savings:.1%} savings)")

    return [asdict(r) for r in results], output_data


def print_filter_summary(data: dict) -> None:
    """Print a human-readable filter suite summary table."""
    print(f"\n{'='*80}")
    print("  FILTER SUITE SUMMARY")
    print(f"{'='*80}")
    print(f"  {'Category':<15} {'Samples':>8} {'Raw Tokens':>12} {'Filtered':>12} {'Savings':>10}")
    print(f"  {'-'*15} {'-'*8} {'-'*12} {'-'*12} {'-'*10}")
    for cat in data.get("per_category", []):
        print(f"  {cat['category']:<15} {cat['samples']:>8} {cat['total_raw_tokens']:>12,} "
              f"{cat['total_filtered_tokens']:>12,} {cat['savings_ratio']:>9.1%}")
    print(f"  {'-'*15} {'-'*8} {'-'*12} {'-'*12} {'-'*10}")
    print(f"  {'AGGREGATE':<15} {data['total_samples']:>8} {data['total_raw_tokens']:>12,} "
          f"{data['total_filtered_tokens']:>12,} {data['aggregate_savings_ratio']:>9.1%}")
    print()


def apply_filter_to_history(messages: list[dict]) -> list[dict]:
    """Pre-filter tool results in a conversation history using filter_output.

    Used by the filter_only arm to compress tool results before they enter
    the model context, simulating what archolith-filter does as a pre-processing
    step without the proxy.
    """
    filtered = []
    for msg in messages:
        content = msg.get("content", "")
        if msg.get("role") == "tool" or (msg.get("role") == "user" and len(content) > 500):
            result = filter_output(content, command="", tool=msg.get("name", ""))
            filtered.append({**msg, "content": result.output})
        else:
            filtered.append(msg)
    return filtered