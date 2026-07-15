"""Fixture types for the Menhir bootstrap-hygiene gate."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class BootstrapRecord:
    id: str
    content: str
    workspace: str
    source: str = "user"
    flagged: bool = False
    bootstrap_scope: str | None = None
    structure_role: str | None = None
    stale_advisory: str | None = None
    stale_action: str | None = None
    stale_reason: str | None = None
    anchor_project: str | None = None
    anchor_path: str | None = None

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "BootstrapRecord":
        return cls(
            id=str(value["id"]),
            content=str(value["content"]),
            workspace=str(value.get("workspace") or ""),
            source=str(value.get("source") or "user"),
            flagged=bool(value.get("flagged")),
            bootstrap_scope=value.get("bootstrap_scope"),
            structure_role=value.get("structure_role"),
            stale_advisory=value.get("stale_advisory"),
            stale_action=value.get("stale_action"),
            stale_reason=value.get("stale_reason"),
            anchor_project=value.get("anchor_project"),
            anchor_path=value.get("anchor_path"),
        )


@dataclass(frozen=True)
class BootstrapFixture:
    name: str
    workspaces: tuple[str, ...]
    records: tuple[BootstrapRecord, ...]
    negative_query: str

    @classmethod
    def from_file(cls, path: Path) -> "BootstrapFixture":
        payload = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            name=str(payload["name"]),
            workspaces=tuple(str(item) for item in payload["workspaces"]),
            records=tuple(BootstrapRecord.from_dict(item) for item in payload["records"]),
            negative_query=str(payload["negative_query"]),
        )
