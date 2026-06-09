"""Checkpoint helpers for saving and resuming multi-turn benchmark runs."""

from __future__ import annotations

import json
from pathlib import Path


def checkpoint_path(output_dir: Path, scenario_name: str, arm: str, budget: int | None) -> Path:
    """Compute the checkpoint file path for a scenario/arm/budget combination."""
    budget_str = f"_{budget}b" if budget else ""
    return output_dir / f".checkpoint_{scenario_name}_{arm}{budget_str}.json"


def save_checkpoint(
    path: Path, scenario_name: str, arm: str, budget: int | None,
    results: list, probe_results: list,
    direct_history: list, arm_history: list,
    proxy_session_id: str | None,
) -> None:
    """Save checkpoint data to a JSON file.

    Allows resuming from a point in the middle of a scenario run.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({
            "scenario": scenario_name,
            "arm": arm,
            "budget": budget,
            "results": results,
            "probe_results": probe_results,
            "direct_history": direct_history,
            "arm_history": arm_history,
            "proxy_session_id": proxy_session_id,
        }, f)


def load_checkpoint(path: Path) -> dict | None:
    """Load checkpoint data from a JSON file, or None if the file doesn't exist."""
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return None
