"""Shared evidence publisher for benchmark artifacts."""

from __future__ import annotations

import json
import subprocess
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class EvidenceRecord:
    title: str
    command: str
    commit: str
    product: str
    ability: str
    fixture_or_live_source: str
    model_provider: str
    environment_caveats: list[str]
    public_copy_allowed: bool
    metric_rows: list[dict[str, Any]]
    artifact: dict[str, Any] = field(default_factory=dict)
    generated_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))


def current_commit(cwd: Path | None = None) -> str:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(cwd) if cwd else None,
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError:
        return "unknown"
    return proc.stdout.strip() if proc.returncode == 0 else "unknown"


def publish_evidence(record: EvidenceRecord, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() == ".json":
        path.write_text(json.dumps(asdict(record), indent=2, ensure_ascii=False), encoding="utf-8")
    else:
        path.write_text(render_evidence_markdown(record), encoding="utf-8")
    return path


def render_evidence_markdown(record: EvidenceRecord) -> str:
    lines = [
        f"# {record.title}",
        "",
        "## Metadata",
        "",
        f"- Command: `{record.command}`",
        f"- Commit: `{record.commit}`",
        f"- Product: `{record.product}`",
        f"- Ability: `{record.ability}`",
        f"- Fixture/live source: `{record.fixture_or_live_source}`",
        f"- Model/provider: `{record.model_provider}`",
        f"- Public copy allowed: `{str(record.public_copy_allowed).lower()}`",
        f"- Generated at: `{record.generated_at}`",
        "",
    ]
    if record.environment_caveats:
        lines.extend(["## Environment Caveats", ""])
        lines.extend(f"- {c}" for c in record.environment_caveats)
        lines.append("")

    if record.metric_rows:
        keys = list(record.metric_rows[0].keys())
        lines.extend(["## Metrics", ""])
        lines.append("| " + " | ".join(keys) + " |")
        lines.append("|" + "|".join("---" for _ in keys) + "|")
        for row in record.metric_rows:
            lines.append("| " + " | ".join(_fmt(row.get(k)) for k in keys) + " |")
        lines.append("")

    lines.extend([
        "## Artifact",
        "",
        "```json",
        json.dumps(record.artifact, indent=2, ensure_ascii=False, sort_keys=True),
        "```",
        "",
    ])
    return "\n".join(lines)


def _fmt(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.4f}"
    if value is None:
        return ""
    return str(value).replace("|", "\\|")
