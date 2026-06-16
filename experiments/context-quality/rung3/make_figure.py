#!/usr/bin/env python3
"""Render the rung-3 cascade figure (3 panels) from the committed result numbers.

Portfolio-facing single figure of the three load-bearing findings:
  1. Phase A — only topological keeps load-bearing foundations under budget pressure.
  2. Phase B vs C — the re-read asymmetry: live arms tie (agent re-reads), frozen
     briefing diverges (curation gates recall only when re-reading is denied).
  3. Phase D — strategy recall (graded); xfcombo's edge is its FLOOR (no catastrophic
     cell), not its mean.

Numbers are the committed results (RESULT-phaseA/-phaseC/-phaseD/-graded-rescore).
Offline. Writes figure-cascade.png. Reproduce: python rung3/make_figure.py
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = HERE / "figure-cascade.png"

C = {"fifo": "#9aa0a6", "scored": "#4285f4", "topological": "#ea4335",
     "combo": "#fbbc04", "xfcombo": "#34a853", "passthrough": "#9aa0a6"}


def main() -> int:
    fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(15, 4.6))
    fig.suptitle("archolith rung-3: deterministic context-selection — the falsification cascade",
                 fontsize=13, fontweight="bold")

    # Panel 1 — Phase A: foundation survival vs budget (post-R3a)
    budgets = [6000, 4000, 3000, 2000, 1500]
    x = list(range(len(budgets)))
    ax1.plot(x, [0, 0, 0, 0, 0], "o-", color=C["fifo"], label="FIFO", lw=2)
    ax1.plot(x, [0, 0, 0, 0, 0], "s--", color=C["scored"], label="scored", lw=2)
    ax1.plot(x, [5, 5, 5, 4, 3], "^-", color=C["topological"], label="topological", lw=2.5)
    ax1.set_xticks(x); ax1.set_xticklabels([f"{b//1000}k" for b in budgets])
    ax1.set_xlabel("token budget (tighter →)"); ax1.set_ylabel("foundations kept (/8)")
    ax1.set_ylim(-0.3, 8); ax1.set_title("A — foundation survival under pressure\n(only topological keeps any)")
    ax1.legend(loc="upper right", fontsize=9); ax1.grid(alpha=0.25)

    # Panel 2 — Phase B vs C: the re-read asymmetry (recall /6)
    groups = ["live\n(re-read OK)", "frozen\n(re-read DENIED)"]
    gx = [0, 1]
    # live: passthrough/fifo/topo all 6 ; frozen: fifo 4 / scored 5 / topo 3
    ax2.bar([p - 0.25 for p in gx], [6, 4], width=0.22, color=C["fifo"], label="FIFO")
    ax2.bar(gx, [6, 5], width=0.22, color=C["scored"], label="scored")
    ax2.bar([p + 0.25 for p in gx], [6, 3], width=0.22, color=C["topological"], label="topological")
    ax2.set_xticks(gx); ax2.set_xticklabels(groups)
    ax2.set_ylabel("convention recall (/6)"); ax2.set_ylim(0, 6.5)
    ax2.set_title("B vs C — the re-read asymmetry\n(curation gates recall only when frozen)")
    ax2.legend(loc="lower left", fontsize=9); ax2.grid(alpha=0.25, axis="y")

    # Panel 3 — Phase D: graded mean recall + floor (min cell)
    order = ["fifo", "topological", "combo", "scored", "xfcombo"]
    means = [2.67, 3.33, 3.67, 4.17, 4.67]
    mins = [2.5, 3.0, 1.0, 1.5, 4.0]
    bx = list(range(len(order)))
    bars = ax3.bar(bx, means, color=[C[s] for s in order], width=0.6,
                   label="mean recall (graded /6)")
    ax3.plot(bx, mins, "kv", markersize=9, label="worst cell (floor)")
    for i, (m, mn) in enumerate(zip(means, mins)):
        ax3.text(i, m + 0.08, f"{m:.2f}", ha="center", fontsize=8)
    ax3.set_xticks(bx); ax3.set_xticklabels(order, rotation=20, ha="right")
    ax3.set_ylim(0, 6.5); ax3.set_ylabel("recall (/6, graded)")
    ax3.set_title("D — combo recall (3 tasks)\nxfcombo wins on FLOOR, not just mean")
    ax3.legend(loc="upper left", fontsize=9); ax3.grid(alpha=0.25, axis="y")

    fig.tight_layout(rect=[0, 0, 1, 0.94])
    fig.savefig(OUT, dpi=130)
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
