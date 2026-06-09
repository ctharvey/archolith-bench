"""Report persistence for archolith-bench.

Handles file I/O: saving benchmark results, writing transcripts,
and generating BENCHMARKS.md aggregations.
"""

from __future__ import annotations

import json
from pathlib import Path


def save_results(data: dict, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    budget_str = f"_{data['budget']}b" if data['budget'] else ""
    arm_label = data.get("arm", "proxy")
    filename = f"benchmark_{data['scenario']}_{arm_label}{budget_str}.json"
    path = output_dir / filename
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Results saved to {path}")

    transcripts_dir = output_dir / "transcripts"
    transcripts_dir.mkdir(parents=True, exist_ok=True)
    for label in ("direct", "arm"):
        transcript_path = transcripts_dir / f"{data['scenario']}_{arm_label}{budget_str}_{label}.md"
        with open(transcript_path, "w", encoding="utf-8") as tf:
            tf.write(f"# {data['scenario']} ({arm_label}) -- {label.upper()} transcript\n")
            tf.write(f"Model: {data['model']} | Budget: {data['budget']} | Turns: {data['turns_run']}\n\n")
            for t in data["turns"]:
                tf.write(f"---\n## Turn {t['turn']}\n\n")
                tf.write(f"**User:** {t.get('user_msg', t.get('user_msg_preview', ''))}\n\n")
                resp = t[label].get("response", t[label].get("response_preview", ""))
                tf.write(f"**{label.title()}** ({t[label]['output_tokens']} tokens, "
                         f"{t[label]['input_tokens']} in, {t[label]['latency_ms']:.0f}ms):\n\n")
                tf.write(f"{resp}\n\n")
    print(f"Transcripts saved to {transcripts_dir}/")
    return path




def write_benchmarks_md(results_dir: Path, out_path: Path) -> None:
    """Generate a BENCHMARKS.md from results/ JSON files.

    Reads filter_results.json, audit_comparison.json, and any
    benchmark_*.json files. Writes a markdown report with per-product
    sections and a cross-product roll-up.
    """
    results_dir = Path(results_dir)
    out_path = Path(out_path)

    lines: list[str] = []
    lines.append("# archolith-bench — Benchmark Results\n")
    lines.append(f"Generated: {__import__('time').strftime('%Y-%m-%d %H:%M UTC', __import__('time').gmtime())}\n")

    # ---- Filter section ----
    filter_path = results_dir / "filter_results.json"
    if filter_path.exists():
        with open(filter_path, encoding="utf-8") as f:
            filter_data = json.load(f)
        lines.append("## Filter Suite (archolith-filter)\n")
        lines.append("Token-savings compression ratio measured on real tool-output corpora.\n")
        lines.append("| Category | Samples | Raw Tokens | Filtered | Savings |\n")
        lines.append("|----------|---------|------------|----------|--------|\n")
        for cat in filter_data.get("per_category", []):
            lines.append(
                f"| {cat['category']} | {cat['samples']} | {cat['total_raw_tokens']:,} "
                f"| {cat['total_filtered_tokens']:,} | {cat['savings_ratio']:.1%} |\n"
            )
        lines.append(
            f"| **Total** | {filter_data['total_samples']} | {filter_data['total_raw_tokens']:,} "
            f"| {filter_data['total_filtered_tokens']:,} | **{filter_data['aggregate_savings_ratio']:.1%}** |\n"
        )
        lines.append("\n")
    else:
        lines.append("## Filter Suite (archolith-filter)\n")
        lines.append("*No filter results found. Run `archolith-bench filter --corpora corpora/` to generate.*\n\n")

    # ---- Proxy section ----
    proxy_results = sorted(results_dir.glob("benchmark_*proxy*.json"))
    if proxy_results:
        lines.append("## Proxy Suite\n")
        lines.append("Multi-turn token savings and continuity metrics across proxy experiment arms.\n")
        lines.append("| Scenario | Arm | Budget | Direct In | Arm In | Savings | Recall Pres. |\n")
        lines.append("|----------|-----|--------|-----------|--------|---------|-------------|\n")
        for rp in proxy_results:
            with open(rp, encoding="utf-8") as f:
                d = json.load(f)
            s = d.get("summary", {})
            q = d.get("quality", {})
            recall = f"{q.get('recall_preservation', 0):.0%}" if q else "N/A"
            lines.append(
                f"| {d.get('scenario', '?')} | {d.get('arm', '?')} | "
                f"{d.get('budget', 'default')} | {s.get('total_direct_input_tokens', 0):,} | "
                f"{s.get('total_proxy_input_tokens', 0):,} | {s.get('overall_savings_ratio', 0):.1%} | "
                f"{recall} |\n"
            )
        lines.append("\n")
    else:
        lines.append("## Proxy Suite\n")
        lines.append("*Pending live-proxy run. Run `archolith-bench proxy --all --arms direct,proxy_plus_filter` to generate.*\n\n")

    # ---- Audit section ----
    audit_path = results_dir / "audit_comparison.json"
    if audit_path.exists():
        with open(audit_path, encoding="utf-8") as f:
            audit_data = json.load(f)
        lines.append("## Audit Suite (archolith-audit)\n")
        before_p = str(audit_data.get("before_path", ""))
        after_p = str(audit_data.get("after_path", ""))
        is_sample = "fixture" in before_p.lower() or "fixture" in after_p.lower()
        if is_sample:
            lines.append(
                "> **Note:** sample/fixture data, not a live audit run. The numbers "
                "below reflect the bundled `fixtures/` inputs and demonstrate the "
                "report format only. Run `archolith-bench audit` against real "
                "before/after session logs to produce measured results.\n\n"
            )
        lines.append("MCP token-waste reduction before vs after.\n")
        lines.append(f"Source: `{before_p}` -> `{after_p}`\n\n")
        lines.append("| Server | Before | After | Change | Pct | Status |\n")
        lines.append("|--------|--------|-------|--------|-----|--------|\n")
        for s in audit_data.get("per_server", []):
            lines.append(
                f"| {s['server']} | {s['before_tokens']:,} | {s['after_tokens']:,} "
                f"| {s['token_change']:+,} | {s['token_change_pct']:+.1f}% | {s['status']} |\n"
            )
        # Total row uses the same change convention as the per-server rows
        # (after - before; negative = reduction) for sign consistency.
        agg_change = audit_data["after_total_tokens"] - audit_data["before_total_tokens"]
        agg_change_pct = -audit_data["token_reduction_pct"]
        lines.append(
            f"| **Total** | {audit_data['before_total_tokens']:,} | {audit_data['after_total_tokens']:,} "
            f"| {agg_change:+,} | {agg_change_pct:+.1f}% | - |\n"
        )
        lines.append(
            f"\n**Token reduction:** {audit_data['token_reduction']:,} ({audit_data['token_reduction_pct']:.1f}%). "
            f"**Waste reduction:** {audit_data['waste_reduction']:,} ({audit_data['waste_reduction_pct']:.1f}%).\n\n"
        )
    else:
        lines.append("## Audit Suite (archolith-audit)\n")
        lines.append("*Pending before/after audit logs. Run `archolith-bench audit --before <log> --after <log>` to generate.*\n\n")

    # ---- Stack section ----
    lines.append("## Stack Suite (Four-Way Comparison)\n")
    lines.append("*Pending live-proxy run. Run `archolith-bench stack --all` to generate.*\n")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.writelines(lines)