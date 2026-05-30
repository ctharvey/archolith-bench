"""Audit suite: measure MCP token-waste reduction before/after via archolith-audit.

Produces a per-server token-waste BEFORE/AFTER delta from two JSON audit
report inputs. Uses archolith_mcp_audit.comparator.compare_reports to
compare the reports and format_delta_report for human-readable output.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict
from pathlib import Path

from archolith_mcp_audit.comparator import ServerDelta, compare_reports, format_delta_report


def run_audit_comparison(
    before_path: Path,
    after_path: Path,
    output_dir: Path = Path("results"),
) -> dict:
    """Compare two JSON audit reports and return the delta.

    Args:
        before_path: Path to the 'before' JSON audit report.
        after_path: Path to the 'after' JSON audit report.
        output_dir: Directory to write results.

    Returns:
        Dict with per-server deltas, aggregate stats, and the raw deltas.
    """
    with open(before_path, encoding="utf-8") as f:
        before = json.load(f)
    with open(after_path, encoding="utf-8") as f:
        after = json.load(f)

    deltas = compare_reports(before, after)

    before_total = sum(s.get("token_share", 0) for s in before.get("servers", {}).values())
    after_total = sum(s.get("token_share", 0) for s in after.get("servers", {}).values())
    before_waste = sum(
        f.get("tokens_wasted", 0)
        for s in before.get("servers", {}).values()
        for f in s.get("findings", [])
    )
    after_waste = sum(
        f.get("tokens_wasted", 0)
        for s in after.get("servers", {}).values()
        for f in s.get("findings", [])
    )
    token_reduction = before_total - after_total
    token_reduction_pct = (token_reduction / before_total * 100) if before_total > 0 else 0.0
    waste_reduction = before_waste - after_waste
    waste_reduction_pct = (waste_reduction / before_waste * 100) if before_waste > 0 else 0.0

    human_report = format_delta_report(deltas, after=after)

    result = {
        "suite": "audit",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "before_path": str(before_path),
        "after_path": str(after_path),
        "before_total_tokens": before_total,
        "after_total_tokens": after_total,
        "token_reduction": token_reduction,
        "token_reduction_pct": round(token_reduction_pct, 2),
        "before_total_waste": before_waste,
        "after_total_waste": after_waste,
        "waste_reduction": waste_reduction,
        "waste_reduction_pct": round(waste_reduction_pct, 2),
        "servers_before": len(before.get("servers", {})),
        "servers_after": len(after.get("servers", {})),
        "per_server": [
            {
                "server": d.server,
                "before_tokens": d.before_tokens,
                "after_tokens": d.after_tokens,
                "token_change": d.token_change,
                "token_change_pct": d.token_change_pct,
                "before_waste": d.before_waste,
                "after_waste": d.after_waste,
                "waste_change": d.waste_change,
                "waste_change_pct": d.waste_change_pct,
                "status": d.status,
                "new_waste_types": d.new_waste_types or [],
                "resolved_waste_types": d.resolved_waste_types or [],
            }
            for d in deltas
        ],
        "human_report": human_report,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "audit_comparison.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"  Audit comparison saved to {path}")

    return result


def print_audit_summary(result: dict) -> None:
    """Print a human-readable audit comparison summary."""
    print(f"\n{'='*80}")
    print(f"  AUDIT COMPARISON: BEFORE vs AFTER")
    print(f"{'='*80}")
    print(f"  Before: {result['before_path']}")
    print(f"  After:  {result['after_path']}")
    print(f"{'='*80}")
    print(f"  {'Server':<16} {'Before':>10} {'After':>10} {'Change':>10} {'Pct':>8} {'Status':<12}")
    print(f"  {'-'*16} {'-'*10} {'-'*10} {'-'*10} {'-'*8} {'-'*12}")
    for s in result.get("per_server", []):
        pct = f"{s['token_change_pct']:+.1f}%"
        print(f"  {s['server']:<16} {s['before_tokens']:>10,} {s['after_tokens']:>10,} "
              f"{s['token_change']:>+10,} {pct:>8} {s['status']:<12}")
    print(f"  {'-'*16} {'-'*10} {'-'*10} {'-'*10} {'-'*8} {'-'*12}")
    print(f"  {'TOTAL':<16} {result['before_total_tokens']:>10,} {result['after_total_tokens']:>10,} "
          f"{result['token_reduction']:>+10,} {result['token_reduction_pct']:+.1f}%")
    print()
    print(f"  Token reduction:   {result['token_reduction']:,} ({result['token_reduction_pct']:.1f}%)")
    print(f"  Waste reduction:   {result['waste_reduction']:,} ({result['waste_reduction_pct']:.1f}%)")
    print()
    if result.get("human_report"):
        print(result["human_report"])