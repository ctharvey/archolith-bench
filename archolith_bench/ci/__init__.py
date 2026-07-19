"""CI recall-benchmark tooling for archolith-bench.

Protects API keys from PR code via a budget-capped reverse proxy, runs a
stratified LongMemEval slice against a PR's menhir checkout, compares to a
pinned baseline, and renders a PR comment card.

See `archolith_bench/ci/README.md` for the full workflow.
"""

from __future__ import annotations

from .budget_proxy import BudgetProxy, BudgetState
from .compare import Baseline, Comparison, GateResult, compare_results, load_baseline
from .card import render_pr_card
from .stratified import StratifiedResult, run_stratified_slice, aggregate_results
from .orchestrator import run_bench_for_pr, OrchestratorConfig

__all__ = [
    "BudgetProxy",
    "BudgetState",
    "Baseline",
    "Comparison",
    "GateResult",
    "compare_results",
    "load_baseline",
    "render_pr_card",
    "StratifiedResult",
    "run_stratified_slice",
    "aggregate_results",
    "run_bench_for_pr",
    "OrchestratorConfig",
]
