"""Render the PR comment card as markdown."""

from __future__ import annotations

from .compare import Comparison, GateResult
from .stratified import StratifiedResult


def render_pr_card(
    *,
    pr_number: int,
    pr_author: str,
    head_sha: str,
    result: StratifiedResult,
    comparison: Comparison,
    max_calls: int,
    max_usd: float,
    llm_calls_used: int,
    usd_used: float,
    killed: bool = False,
    kill_reason: str | None = None,
) -> str:
    """Return the markdown for the PR comment."""
    if killed:
        return _render_killed(
            pr_number=pr_number,
            pr_author=pr_author,
            head_sha=head_sha,
            kill_reason=kill_reason or "unknown",
            max_calls=max_calls,
            max_usd=max_usd,
            llm_calls_used=llm_calls_used,
        )
    return _render_pass(
        pr_number=pr_number,
        pr_author=pr_author,
        head_sha=head_sha,
        result=result,
        comparison=comparison,
        max_calls=max_calls,
        max_usd=max_usd,
        llm_calls_used=llm_calls_used,
        usd_used=usd_used,
    )


def _gate_emoji(gate: GateResult) -> str:
    return {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌"}.get(gate, "❓")


def _render_pass(
    *,
    pr_number: int,
    pr_author: str,
    head_sha: str,
    result: StratifiedResult,
    comparison: Comparison,
    max_calls: int,
    max_usd: float,
    llm_calls_used: int,
    usd_used: float,
) -> str:
    gate = comparison.gate
    emoji = _gate_emoji(gate)
    cur = comparison.overall_current
    base = comparison.overall_baseline
    delta = comparison.overall_delta
    pct = comparison.overall_pct_delta

    lines = [
        f"### {emoji} Recall Benchmark — {gate.value}",
        "",
        f"**Recall score:** {cur:.3f}  (baseline {base:.3f}, "
        f"Δ {delta:+.3f} / {pct:+.1f}%)",
        "",
        f"**PR:** #{pr_number} by @{pr_author}",
        f"**Head:** `{head_sha[:12]}`",
        f"**LLM calls:** {llm_calls_used} / {max_calls}   "
        f"**Cost:** ${usd_used:.2f} / ${max_usd:.2f}",
        "",
        "<details>",
        "<summary>Per-type breakdown</summary>",
        "",
        "| Type | Baseline | Current | Δ | Status |",
        "|------|----------|---------|---|--------|",
    ]
    for td in comparison.type_deltas:
        warn = " ⚠" if td.delta < -0.10 else ""
        lines.append(
            f"| {td.type} | {td.baseline:.3f} | {td.current:.3f} | "
            f"{td.delta:+.3f} {td.status} |{warn} |"
        )
    lines.extend([
        "",
        f"**Overall:** {cur:.3f} (baseline {base:.3f}, Δ {delta:+.3f})",
        f"**Gate:** {emoji} {gate.value} — {comparison.gate_reason}",
        "</details>",
        "",
    ])

    if comparison.regressions:
        lines.extend([
            "<details>",
            f"<summary>Regressions ({len(comparison.regressions)})</summary>",
            "",
        ])
        for q in comparison.regressions[:20]:
            lines.append(f"- **{q.id}** ({q.type}): was ✓, now ✗")
        if len(comparison.regressions) > 20:
            lines.append(f"- ... and {len(comparison.regressions) - 20} more")
        lines.extend(["", "</details>", ""])

    if comparison.improvements:
        lines.extend([
            "<details>",
            f"<summary>Improvements ({len(comparison.improvements)})</summary>",
            "",
        ])
        for q in comparison.improvements[:20]:
            lines.append(f"- **{q.id}** ({q.type}): was ✗, now ✓")
        if len(comparison.improvements) > 20:
            lines.append(f"- ... and {len(comparison.improvements) - 20} more")
        lines.extend(["", "</details>", ""])

    if result.type_results:
        errored = [t for t in result.type_results if t.error]
        if errored:
            lines.extend([
                "<details>",
                f"<summary>Type errors ({len(errored)})</summary>",
                "",
            ])
            for t in errored:
                lines.append(f"- **{t.type}**: `{t.error}`")
            lines.extend(["", "</details>", ""])

    lines.extend([
        "<details>",
        "<summary>Artifacts</summary>",
        "",
        f"- Results: `.bench/runs/{pr_number}/results.json`",
        f"- Traces: `.bench/runs/{pr_number}/traces.jsonl`",
        f"- Budget: `.bench/runs/{pr_number}/budget.json`",
        "",
        "**Note:** The bench harness and baseline come from `main`, not your PR. "
        "Your PR's menhir code is what's under test.",
        "</details>",
    ])
    return "\n".join(lines)


def _render_killed(
    *,
    pr_number: int,
    pr_author: str,
    head_sha: str,
    kill_reason: str,
    max_calls: int,
    max_usd: float,
    llm_calls_used: int,
) -> str:
    return "\n".join([
        "### ❌ Recall Benchmark — ABORTED",
        "",
        f"**Reason:** {kill_reason}",
        "",
        f"**PR:** #{pr_number} by @{pr_author}",
        f"**Head:** `{head_sha[:12]}`",
        f"**LLM calls used:** {llm_calls_used} / {max_calls}",
        "",
        "The benchmark runner killed your PR's menhir process. Investigate before re-running.",
        "",
        "Possible causes:",
        "- PR changes that spike enrichment LLM usage",
        "- Recall loop that doesn't terminate",
        "- Accidental infinite retry",
        "",
        "Re-runs remaining: see `.bench/runs/{}/count.txt`".format(pr_number),
    ])
