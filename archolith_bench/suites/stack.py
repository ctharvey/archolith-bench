"""Stack suite: four-way comparison (direct / filter_only / proxy_only / proxy_plus_filter).

Runs a scenario through the four headline arms and emits a single comparison
table showing each layer's additive contribution to savings and continuity.
"""

from __future__ import annotations

from pathlib import Path

from ..arms import ARMS
from ..core.scenario import Scenario
from .proxy import run_benchmark


STACK_ARMS = ["direct", "filter_only", "proxy_only", "proxy_plus_filter"]


def run_stack_suite(
    scenarios: list[Scenario],
    proxy_url: str,
    direct_url: str,
    model: str,
    budget: int | None = None,
    output_dir: Path = Path("results"),
    api_key: str = "",
    max_turns: int | None = None,
    run_probes: bool = True,
    run_restart: bool = True,
) -> list[dict]:
    """Run each scenario through the four stack arms and collect results."""
    all_arm_results: list[dict] = []

    for scenario in scenarios:
        for arm in STACK_ARMS:
            arm_def = ARMS.get(arm)
            if not arm_def:
                print(f"  WARNING: Unknown arm '{arm}', skipping")
                continue

            print(f"\n{'#'*70}")
            print(f"  [stack] Running: {scenario.name} / {arm}")
            print(f"{'#'*70}")

            data = run_benchmark(
                scenario, arm, proxy_url, direct_url, model,
                budget, output_dir, api_key=api_key,
                max_turns=max_turns,
                run_probes=run_probes,
                run_restart=run_restart,
            )
            data["stack_arm"] = arm
            all_arm_results.append(data)

    return all_arm_results