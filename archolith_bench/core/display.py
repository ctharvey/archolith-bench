"""Display and report rendering for archolith-bench.

Handles all human-readable output: summary tables, markdown tables,
cross-scenario summaries, and four-way comparison tables.
"""

from __future__ import annotations

from typing import Any


COLLAPSE_TOKEN_THRESHOLD = 50


def render_markdown_table(rows: list[list[str]], headers: list[str]) -> str:
    """Render a markdown table from row data and headers.

    Args:
        rows: List of rows, each row is a list of strings.
        headers: List of header names.

    Returns:
        Markdown table as a multi-line string.
    """
    lines: list[str] = []
    # Header row
    lines.append("| " + " | ".join(headers) + " |")
    # Separator row
    separator = "|" + "|".join(["-" * max(len(h), 5) for h in headers]) + "|"
    lines.append(separator)
    # Data rows
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def print_summary(data: dict) -> None:
    """Print a formatted summary of a single benchmark run.

    Args:
        data: Benchmark result dict from run_benchmark().
    """
    results = data["turns"]
    arm_label = data.get("arm", "proxy")
    print(f"\n{'='*100}")
    print(f"  BENCHMARK SUMMARY: {data['scenario']} (budget={data['budget'] or 'default'}, arm={arm_label})")
    print(f"{'='*100}")

    header = (
        f"{'Turn':>4}  {'Direct In':>10}  {'Arm In':>10}  {'Trace In':>10}  "
        f"{'Rewritten':>10}  {'Savings':>14}  {'Assembly':>14}  {'Facts':>5}  "
        f"{'D Out':>6}  {'P Out':>6}  "
        f"{'D ms':>7}  {'P ms':>7}"
    )
    print(header)
    print("-" * 126)

    for r in results:
        d = r["direct"]
        a = r.get("arm", r.get("proxy", {}))
        t = r["trace"]
        savings_str = f"{t['savings_tokens']:>5} ({t['savings_ratio']:.0%})"
        collapse_marker = " !!" if a["output_tokens"] < COLLAPSE_TOKEN_THRESHOLD else ""
        print(
            f"{r['turn']:>4}  "
            f"{d['input_tokens']:>10}  "
            f"{a['input_tokens']:>10}  "
            f"{t['input_tokens']:>10}  "
            f"{t['rewritten_tokens']:>10}  "
            f"{savings_str:>14}  "
            f"{t.get('assembly_mode', 'unknown'):>14}  "
            f"{t.get('facts_stored', 0):>5}  "
            f"{d['output_tokens']:>6}  "
            f"{a['output_tokens']:>6}{collapse_marker}  "
            f"{d['latency_ms']:>7.0f}  "
            f"{a['latency_ms']:>7.0f}"
        )

    s = data["summary"]
    print("-" * 110)
    if data.get("aborted"):
        print(f"  *** ABORTED: {data['abort_reason']} (ran {data['turns_run']}/{data['turns_total']} turns) ***")
    print(f"  Total direct input tokens: {s['total_direct_input_tokens']:,}")
    print(f"  Total arm input tokens:    {s['total_proxy_input_tokens']:,}")
    print(f"  Total savings:             {s['total_savings_tokens']:,}")
    print(f"  Overall savings ratio:     {s['overall_savings_ratio']:.1%}")
    if s.get("collapsed_turns"):
        print(f"  Output collapses:          {len(s['collapsed_turns'])} turns ({s['collapse_rate']:.0%}) -- turns {s['collapsed_turns']}")

    if data.get("quality"):
        q = data["quality"]
        print(f"\n  Fact Probe Quality:")
        print(f"    Probes run:              {q['total_probes']}")
        print(f"    Avg direct recall:       {q['avg_direct_recall']:.1%}")
        print(f"    Avg arm recall:          {q.get('avg_arm_recall', q.get('avg_proxy_recall', 0)):.1%}")
        print(f"    Recall preservation:     {q['recall_preservation']:.1%}")

    if data.get("continuity"):
        c = data["continuity"]
        print(f"\n  Continuity Metrics:")
        print(f"    Repeat file reads:       {c.get('repeat_file_reads', 0)}")
        print(f"    Repeat diagnostics:      {c.get('repeat_diagnostics', 0)}")
        print(f"    Decision retention:      {c.get('decision_retention', 0):.1%}")
        print(f"    Verification continuity:  {c.get('verification_continuity', 0):.1%}  (experimental)")
        print(f"    Orientation score:        {c.get('turn_one_orientation_score', 0):.1%}  (experimental)")
    print()


def print_cross_scenario_summary(all_results: list[dict]) -> None:
    """Print summary across multiple scenario runs.

    Args:
        all_results: List of result dicts from multiple scenario runs.
    """
    if len(all_results) < 2:
        return
    print(f"\n{'='*90}")
    print("  CROSS-SCENARIO SUMMARY")
    print(f"{'='*90}")
    header = f"{'Scenario':<20} {'Arm':<20} {'Budget':>8} {'Turns':>6} {'Savings':>10} {'Recall':>10}"
    print(header)
    print("-" * 78)
    for data in all_results:
        s = data["summary"]
        q = data.get("quality", {})
        recall_str = f"{q.get('avg_arm_recall', q.get('avg_proxy_recall', 0)):.0%}" if q else "N/A"
        print(
            f"{data['scenario']:<20} "
            f"{data.get('arm', 'proxy'):<20} "
            f"{str(data['budget'] or 'default'):>8} "
            f"{data['turns_run']:>6} "
            f"{s['overall_savings_ratio']:.1%}      "
            f"{recall_str:>10}"
        )
    print()


def print_four_way_table(all_arm_results: list[dict]) -> None:
    """Print the four-way headline comparison: direct/filter/proxy/proxy+filter.

    Each entry in all_arm_results is a run_benchmark result dict with a
    'stack_arm' key identifying which arm produced it.

    Args:
        all_arm_results: List of result dicts from a stack suite run.
    """
    print(f"\n{'='*100}")
    print("  FOUR-WAY COMPARISON TABLE")
    print(f"{'='*100}")

    header = (
        f"{'Scenario':<16} {'Arm':<22} {'Direct In':>10} {'Arm In':>10} "
        f"{'Savings':>10} {'Ratio':>8} {'Recall':>8} {'Dec Ret':>8} {'V Cont':>8}"
    )
    print(header)
    print("-" * 100)

    for data in all_arm_results:
        s = data["summary"]
        q = data.get("quality", {})
        c = data.get("continuity", {})
        recall_str = f"{q.get('avg_arm_recall', 0):.0%}" if q else "N/A"
        dec_ret = f"{c.get('decision_retention', 0):.0%}" if c else "N/A"
        v_cont = f"{c.get('verification_continuity', 0):.0%}" if c else "N/A"
        print(
            f"{data['scenario']:<16} "
            f"{data.get('stack_arm', data.get('arm', '?')):<22} "
            f"{s['total_direct_input_tokens']:>10,} "
            f"{s['total_proxy_input_tokens']:>10,} "
            f"{s['total_savings_tokens']:>10,} "
            f"{s['overall_savings_ratio']:>7.1%} "
            f"{recall_str:>8} "
            f"{dec_ret:>8} "
            f"{v_cont:>8}"
        )

    print("-" * 100)

    arms_seen = set(d.get("stack_arm", d.get("arm", "")) for d in all_arm_results)
    for arm in ["direct", "filter_only", "proxy_only", "proxy_plus_filter"]:
        arm_results = [d for d in all_arm_results if d.get("stack_arm", d.get("arm", "")) == arm]
        if arm_results:
            total_savings = sum(d["summary"]["overall_savings_ratio"] for d in arm_results)
            avg_savings = total_savings / len(arm_results)
            total_recall = sum(d.get("quality", {}).get("recall_preservation", 0) for d in arm_results if d.get("quality"))
            recall_count = sum(1 for d in arm_results if d.get("quality"))
            avg_recall = total_recall / recall_count if recall_count else 0
            total_dec = sum(d.get("continuity", {}).get("decision_retention", 0) for d in arm_results if d.get("continuity"))
            dec_count = sum(1 for d in arm_results if d.get("continuity", {}).get("decision_retention", 0) > 0)
            avg_dec = total_dec / dec_count if dec_count else 0
            total_vcont = sum(d.get("continuity", {}).get("verification_continuity", 0) for d in arm_results if d.get("continuity"))
            vcont_count = sum(1 for d in arm_results if d.get("continuity", {}).get("verification_continuity", 0) > 0)
            avg_vcont = total_vcont / vcont_count if vcont_count else 0
            print(f"  {arm:<22} avg savings: {avg_savings:.1%}  avg recall preservation: {avg_recall:.1%}  "
                  f"avg decision_retention: {avg_dec:.1%}  avg verification_continuity: {avg_vcont:.1%}")

    headline_savings = None
    headline_continuity = None
    proxy_plus = [d for d in all_arm_results if d.get("stack_arm") == "proxy_plus_filter"]
    direct_results = [d for d in all_arm_results if d.get("stack_arm") == "direct"]
    if proxy_plus and direct_results:
        pp_savings = sum(d["summary"]["overall_savings_ratio"] for d in proxy_plus) / len(proxy_plus)
        headline_savings = pp_savings
        pp_cont = [d.get("continuity", {}) for d in proxy_plus]
        dec_vals = [c.get("decision_retention", 0) for c in pp_cont if c.get("decision_retention", 0) > 0]
        headline_continuity = sum(dec_vals) / len(dec_vals) if dec_vals else 0

    if headline_savings is not None:
        cont_str = f", {headline_continuity:.0%} continuity preserved" if headline_continuity else ""
        print(f"\n  HEADLINE: {headline_savings:.0%} token savings{cont_str}")
    print()
