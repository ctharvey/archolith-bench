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
    flagged: bool = False
    bootstrap_scope: str | None = None
    structure_role: str | None = None
    stale_advisory: str | None = None

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "BootstrapRecord":
        return cls(
            id=str(value["id"]),
            content=str(value["content"]),
            workspace=str(value.get("workspace") or ""),
            flagged=bool(value.get("flagged")),
            bootstrap_scope=value.get("bootstrap_scope"),
            structure_role=value.get("structure_role"),
            stale_advisory=value.get("stale_advisory"),
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
