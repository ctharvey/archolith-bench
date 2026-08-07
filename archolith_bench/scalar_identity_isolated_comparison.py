"""Offline baseline versus opt-in isolated scalar research-adapter comparison.

This lane is deliberately additive: the canonical adapter remains the baseline, while the
isolated adapter is loaded from its dedicated Menhir module and fails loudly when unavailable.
Reports contain hashes, statuses, and identity fields only; source text is never copied.
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

from archolith_bench.compositional_scalar_panel import PanelError, load_panel_menhir_api
from archolith_bench.scalar_identity_acceptance_panel import _load_adapter
from archolith_bench.scalar_identity_noisy_panel import _actual, load_panel


REPORT_SCHEMA_VERSION = 1
PROMOTION_STATUS = "not_evaluable"
_ISOLATED_MODULE = "menhir.services.research_scalar_isolated_adapter"
_ISOLATED_FUNCTION = "adapt_isolated_research_candidate"
_ISOLATED_VERSION = "RESEARCH_ISOLATED_ADAPTER_VERSION"
_IDENTITY_FIELDS = ("composition_status", "relation_type", "target", "operation", "value")


def _load_isolated_adapter(menhir_root: str | Path) -> tuple[Callable[..., Any], str]:
    root = Path(menhir_root).expanduser().resolve()
    source_root = str(root / "src")
    if source_root not in sys.path:
        sys.path.insert(0, source_root)
    try:
        module = importlib.import_module(_ISOLATED_MODULE)
        adapter = getattr(module, _ISOLATED_FUNCTION)
        version = getattr(module, _ISOLATED_VERSION)
    except (ImportError, AttributeError) as exc:
        raise PanelError(
            f"isolated research adapter unavailable from {root}: "
            f"expected {_ISOLATED_MODULE}.{_ISOLATED_FUNCTION}"
        ) from exc
    if not callable(adapter) or not isinstance(version, str) or not version:
        raise PanelError("isolated research adapter has an invalid callable/version")
    return adapter, version


def _identity_tuple(actual: dict[str, Any]) -> tuple[Any, ...]:
    return tuple(actual[field] for field in _IDENTITY_FIELDS)


def _isolated_actual(result: Any) -> dict[str, Any]:
    """Project the isolated result into the baseline panel's quote-free actual shape."""
    proposal = result.proposal
    receipt = result.receipt
    relation = target = operation = value = None
    if result.composition is not None and result.composition.identity is not None:
        identity = result.composition.identity
        relation = identity.relation_type
        target = identity.target_or_scope[0]
        operation = identity.operation
        value = identity.value
        if isinstance(value, str):
            try:
                value = int(value)
            except ValueError:
                try:
                    value = float(value)
                except ValueError:
                    pass
    admitted = proposal is not None
    composed = result.composition is not None and result.composition.identity is not None
    return {
        "parse_status": "admitted" if admitted else "rejected",
        "parse_reason": None if admitted else receipt.reason,
        "composition_status": "composed" if composed else ("abstained" if admitted else None),
        "composition_reason": None if composed or not admitted else receipt.reason,
        "relation_type": relation,
        "target": target,
        "operation": operation,
        "value": value,
    }


def _path_summary(rows: list[dict[str, Any]], path: str) -> dict[str, Any]:
    slices: dict[str, Counter[str]] = {"clean": Counter(), "noisy": Counter()}
    for row in rows:
        values = row[path]
        counter = slices[row["slice"]]
        counter["total"] += 1
        counter["correct"] += int(values["correct"])
        counter["parse_admitted"] += int(values["actual"]["parse_status"] == "admitted")
        counter["composed"] += int(values["actual"]["composition_status"] == "composed")
        counter["false_current_state_errors"] += int(values["false_current_state_error"])
    return {
        "cases_total": len(rows),
        "correct": sum(int(row[path]["correct"]) for row in rows),
        "false_current_state_errors": sum(
            int(row[path]["false_current_state_error"]) for row in rows
        ),
        "slices": {name: dict(counter) for name, counter in slices.items()},
    }


def analyze_comparison(
    path: str | Path,
    *,
    menhir_root: str | Path,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Compare canonical and isolated adapter results on the unchanged noisy fixture."""
    panel = load_panel(path)
    api = load_panel_menhir_api(menhir_root)
    baseline, baseline_version = _load_adapter(menhir_root)
    isolated, isolated_version = _load_isolated_adapter(menhir_root)
    episodes = [SimpleNamespace(uuid=row["uuid"], content=row["content"]) for row in panel["episodes"]]
    rows: list[dict[str, Any]] = []
    for case in panel["cases"]:
        expected = case["expected"]
        expected_actual = {field: expected[field] for field in ("parse_status", "parse_reason", *_IDENTITY_FIELDS)}
        path_values: dict[str, dict[str, Any]] = {}
        for name, adapter in (("baseline", baseline), ("isolated", isolated)):
            result = adapter(case["candidate"], episodes, candidate_id=case["case_id"])
            actual = _actual(result) if name == "baseline" else _isolated_actual(result)
            dimensions = sorted(
                field for field, value in expected_actual.items() if actual[field] != value
            )
            path_values[name] = {
                "actual": actual,
                "correct": not dimensions,
                "mismatch_dimensions": dimensions,
                "false_current_state_error": bool(
                    expected["false_current"] and actual["composition_status"] == "composed"
                ),
            }
        baseline_identity = _identity_tuple(path_values["baseline"]["actual"])
        isolated_identity = _identity_tuple(path_values["isolated"]["actual"])
        rows.append(
            {
                "case_id": case["case_id"],
                "pair_id": case["pair_id"],
                "perturbation_id": case["perturbation_id"],
                "slice": case["slice"],
                "role": expected["role"],
                "expected": expected_actual,
                "baseline": path_values["baseline"],
                "isolated": path_values["isolated"],
                "identity_mismatch": baseline_identity != isolated_identity,
            }
        )
    baseline_summary = _path_summary(rows, "baseline")
    isolated_summary = _path_summary(rows, "isolated")
    gains = {
        name: isolated_summary["slices"][name]["composed"]
        - baseline_summary["slices"][name]["composed"]
        for name in ("clean", "noisy")
    }
    identity_mismatches = [row["case_id"] for row in rows if row["identity_mismatch"]]
    return {
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "promotion_status": PROMOTION_STATUS,
        "provenance": {
            "panel_id": panel["panel_id"],
            "panel_sha256": panel["file_sha256"],
            "source_sha256": panel["source_sha256"],
            "generated_at": generated_at or datetime.now(timezone.utc).isoformat(),
            "llm_used": False,
            "baseline_adapter_version": baseline_version,
            "isolated_adapter_version": isolated_version,
            "composer_version": api.composer_version,
        },
        "aggregate": {
            "cases_total": len(rows),
            "baseline": baseline_summary,
            "isolated": isolated_summary,
            "composition_gains": {
                "clean": gains["clean"],
                "noisy": gains["noisy"],
                "total": gains["clean"] + gains["noisy"],
            },
            "identity_mismatches": {
                "total": len(identity_mismatches),
                "case_ids": identity_mismatches,
            },
            "false_current_state_errors": {
                "baseline": baseline_summary["false_current_state_errors"],
                "isolated": isolated_summary["false_current_state_errors"],
            },
        },
        "cases": rows,
    }


def render_markdown(report: dict[str, Any]) -> str:
    aggregate = report["aggregate"]
    lines = [
        "# Scalar identity isolated comparison",
        "",
        "Offline baseline versus opt-in isolated adapter evidence; promotion remains `not_evaluable`.",
        "",
        f"- Cases: {aggregate['cases_total']}",
        f"- Composition gains (clean/noisy): {aggregate['composition_gains']['clean']}/{aggregate['composition_gains']['noisy']}",
        f"- Identity mismatches: {aggregate['identity_mismatches']['total']}",
        f"- False-current errors (baseline/isolated): {aggregate['false_current_state_errors']['baseline']}/{aggregate['false_current_state_errors']['isolated']}",
        "",
        "| Path | Slice | Correct | Total | Composed |",
        "| --- | --- | ---: | ---: | ---: |",
    ]
    for path_name in ("baseline", "isolated"):
        for slice_name in ("clean", "noisy"):
            values = aggregate[path_name]["slices"][slice_name]
            lines.append(
                f"| `{path_name}` | `{slice_name}` | {values['correct']} | "
                f"{values['total']} | {values['composed']} |"
            )
    return "\n".join(lines) + "\n"


def write_reports(report: dict[str, Any], json_out: str | Path, markdown_out: str | Path) -> None:
    json_path, markdown_path = Path(json_out).resolve(), Path(markdown_out).resolve()
    if json_path == markdown_path or json_path.exists() or markdown_path.exists():
        raise PanelError("output paths must be distinct and non-existing")
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(render_markdown(report), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare baseline and isolated scalar adapters.")
    parser.add_argument("panel")
    parser.add_argument("--menhir-root", required=True)
    parser.add_argument("--json-out", required=True)
    parser.add_argument("--markdown-out", required=True)
    args = parser.parse_args(argv)
    try:
        write_reports(
            analyze_comparison(args.panel, menhir_root=args.menhir_root),
            args.json_out,
            args.markdown_out,
        )
    except PanelError as exc:
        parser.error(str(exc))
    return 0


__all__ = ["analyze_comparison", "main", "render_markdown", "write_reports"]
