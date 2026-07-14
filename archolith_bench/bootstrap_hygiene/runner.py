"""Runner for the Menhir recent/bootstrap hygiene acceptance gate."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .models import BootstrapFixture, BootstrapRecord


def _tokens(value: str) -> set[str]:
    return {token.strip(".,:;!?()[]{}\"'").casefold() for token in value.split() if token}


def _allowed_scopes(workspace: str) -> set[str]:
    return {"general", f"workspace:{workspace.casefold()}"}


def _contains(items: list[dict[str, Any]], record: BootstrapRecord) -> bool:
    needle = record.content.casefold()
    return any(needle in str(item).casefold() for item in items)


class BootstrapHygieneRunner:
    """Evaluate the same policy offline or through a black-box Menhir client."""

    def __init__(self, fixture: BootstrapFixture, client: Any | None = None) -> None:
        self.fixture = fixture
        self.client = client

    def run(self) -> dict[str, Any]:
        return self._run_offline() if self.client is None else self._run_live()

    def _artifact(
        self,
        *,
        mode: str,
        metrics: dict[str, int | float],
        observations: dict[str, Any],
    ) -> dict[str, Any]:
        gates = {
            "structural_recent_leakage_count": metrics["structural_recent_leakage_count"] == 0,
            "cross_workspace_recent_leakage_count": metrics["cross_workspace_recent_leakage_count"] == 0,
            "cross_workspace_flagged_leakage_count": metrics["cross_workspace_flagged_leakage_count"] == 0,
            "general_pin_recall_rate": metrics["general_pin_recall_rate"] == 1.0,
            "workspace_pin_recall_rate": metrics["workspace_pin_recall_rate"] == 1.0,
            "stale_anchor_advisory_preserved": metrics["stale_anchor_advisory_preserved"] == 1.0,
        }
        return {
            "fixture": self.fixture.name,
            "mode": mode,
            "metrics": metrics,
            "gates": gates,
            "passed": all(gates.values()),
            "observations": observations,
        }

    def _run_offline(self) -> dict[str, Any]:
        records = list(self.fixture.records)
        by_workspace: dict[str, dict[str, list[dict[str, Any]]]] = {}
        for workspace in self.fixture.workspaces:
            recent = [
                asdict(row)
                for row in records
                if row.workspace == workspace and row.structure_role is None and not row.flagged
            ]
            flagged = [
                asdict(row)
                for row in records
                if row.flagged and row.bootstrap_scope in _allowed_scopes(workspace)
            ]
            by_workspace[workspace] = {"recent": recent, "flagged": flagged}

        structural_leaks = sum(
            1
            for bundle in by_workspace.values()
            for row in bundle["recent"]
            if row.get("structure_role") is not None
        )
        recent_cross = sum(
            1
            for workspace, bundle in by_workspace.items()
            for other in self.fixture.workspaces
            if other != workspace
            for row in bundle["recent"]
            if row.get("workspace") == other
        )
        flagged_cross = sum(
            1
            for workspace, bundle in by_workspace.items()
            for row in bundle["flagged"]
            if row.get("bootstrap_scope", "").startswith("workspace:")
            and row.get("bootstrap_scope") != f"workspace:{workspace.casefold()}"
        )
        general = [row for row in records if row.bootstrap_scope == "general"]
        workspace_pins = [
            row for row in records if (row.bootstrap_scope or "").startswith("workspace:")
        ]
        general_hits = sum(
            _contains(by_workspace[workspace]["flagged"], row)
            for workspace in self.fixture.workspaces
            for row in general
        )
        workspace_hits = sum(
            _contains(by_workspace[row.workspace]["flagged"], row) for row in workspace_pins
        )
        query_tokens = _tokens(self.fixture.negative_query)
        negative_returned = sum(
            bool(query_tokens & _tokens(row.content))
            for row in records
            if row.structure_role is None
        )
        stale = [row for row in records if row.stale_advisory]
        bootstrap_text = " ".join(
            str(row.get("content") or "")
            for bundle in by_workspace.values()
            for lane in ("flagged", "recent")
            for row in bundle[lane]
        )
        metrics: dict[str, int | float] = {
            "structural_recent_leakage_count": structural_leaks,
            "cross_workspace_recent_leakage_count": recent_cross,
            "cross_workspace_flagged_leakage_count": flagged_cross,
            "general_pin_recall_rate": general_hits / max(1, len(general) * len(self.fixture.workspaces)),
            "workspace_pin_recall_rate": workspace_hits / max(1, len(workspace_pins)),
            "stale_anchor_advisory_preserved": 1.0 if all(row.stale_advisory for row in stale) else 0.0,
            "negative_query_returned_count": negative_returned,
            "negative_query_false_positive_rate": negative_returned / max(1, len(records)),
            "bootstrap_input_tokens": len(bootstrap_text.split()),
        }
        return self._artifact(mode="offline", metrics=metrics, observations={"workspaces": by_workspace})

    def _run_live(self) -> dict[str, Any]:
        client = self.client
        namespaces = {workspace: client.new_group() for workspace in self.fixture.workspaces}
        reader_ids = {workspace: f"bootstrap-hygiene-{namespaces[workspace]}" for workspace in namespaces}
        print(f"bootstrap-hygiene throwaway namespaces: {namespaces}")
        try:
            for row in self.fixture.records:
                if row.structure_role is not None:
                    continue
                client.ingest(
                    namespaces[row.workspace],
                    "user",
                    row.content,
                    source="user",
                    flagged=row.flagged,
                    bootstrap_scope=row.bootstrap_scope,
                )

            bundles: dict[str, dict[str, Any]] = {}
            for workspace in self.fixture.workspaces:
                flagged = client.bootstrap_flagged(reader_ids[workspace], workspace)
                context = client.bootstrap_context(
                    reader_ids[workspace], workspace, namespaces[workspace]
                )
                bundles[workspace] = {
                    "flagged": list(flagged.get("items", [])),
                    "recent": list(context.get("recent", [])),
                }

            general = [row for row in self.fixture.records if row.bootstrap_scope == "general"]
            workspace_pins = [
                row for row in self.fixture.records
                if (row.bootstrap_scope or "").startswith("workspace:")
            ]
            recent_cross = sum(
                _contains(bundles[workspace]["recent"], row)
                for workspace in self.fixture.workspaces
                for row in self.fixture.records
                if row.workspace != workspace and not row.flagged and row.structure_role is None
            )
            flagged_cross = sum(
                _contains(bundles[workspace]["flagged"], row)
                for workspace in self.fixture.workspaces
                for row in workspace_pins
                if row.workspace != workspace
            )
            general_hits = sum(
                _contains(bundles[workspace]["flagged"], row)
                for workspace in self.fixture.workspaces
                for row in general
            )
            workspace_hits = sum(
                _contains(bundles[row.workspace]["flagged"], row) for row in workspace_pins
            )
            negative = client.recall_raw(
                namespaces[self.fixture.workspaces[0]], self.fixture.negative_query
            )
            negative_count = len(negative.get("results", []))
            bootstrap_text = " ".join(
                str(item)
                for bundle in bundles.values()
                for lane in ("flagged", "recent")
                for item in bundle[lane]
            )
            stale_items = [
                item
                for item in negative.get("results", [])
                if item.get("stale_anchor_info") is not None
            ]
            metrics: dict[str, int | float] = {
                "structural_recent_leakage_count": sum(
                    item.get("structure_role") is not None
                    for bundle in bundles.values()
                    for item in bundle["recent"]
                ),
                "cross_workspace_recent_leakage_count": recent_cross,
                "cross_workspace_flagged_leakage_count": flagged_cross,
                "general_pin_recall_rate": general_hits / max(1, len(general) * len(self.fixture.workspaces)),
                "workspace_pin_recall_rate": workspace_hits / max(1, len(workspace_pins)),
                "stale_anchor_advisory_preserved": float(
                    all(item.get("stale_advisory") for item in stale_items)
                ),
                "negative_query_returned_count": negative_count,
                "negative_query_false_positive_rate": negative_count / max(1, len(self.fixture.records)),
                "bootstrap_input_tokens": len(bootstrap_text.split()),
            }
            return self._artifact(
                mode="live",
                metrics=metrics,
                observations={
                    "workspaces": bundles,
                    "stale_items_observed": len(stale_items),
                    "structural_probe_seeded": False,
                },
            )
        finally:
            for namespace in namespaces.values():
                client.reset(namespace)
