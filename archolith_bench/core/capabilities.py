"""Capability registry for Archolith-family benchmark evidence.

The industry registry maps products to external benchmark families. This registry
maps product abilities to local runners and evidence gates, so the CLI and docs can
answer: "what capability does this command prove, and can it be used in launch copy?"
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


STATUS_VALUES = ("offline-smoke", "live-required", "candidate", "launch-evidence")


@dataclass(frozen=True)
class Capability:
    product: str
    ability: str
    runner_command: str
    dependency: str
    evidence_path: str
    status: str
    launch_claim_rule: str

    def __post_init__(self) -> None:
        if self.status not in STATUS_VALUES:
            raise ValueError(f"unknown capability status: {self.status}")


CAPABILITIES: tuple[Capability, ...] = (
    Capability(
        product="menhir",
        ability="persistent memory QA",
        runner_command="archolith-bench menhir longmemeval",
        dependency="Offline fixture for smoke; throwaway Menhir + Neo4j for live Mode B",
        evidence_path="benchmarks/menhir-longmemeval-mode-b-YYYY-MM-DD.md",
        status="live-required",
        launch_claim_rule="No public persistent-memory score until a throwaway Menhir run is tracked.",
    ),
    Capability(
        product="menhir",
        ability="hybrid retrieval tuning",
        runner_command="archolith-bench menhir r1",
        dependency="Offline fixture for smoke; dummy/live Menhir graph for graduation",
        evidence_path="benchmarks/menhir-r1-hybrid-retrieval-YYYY-MM-DD.md",
        status="offline-smoke",
        launch_claim_rule="Fixture smoke proves harness health only; live graph evidence required for tuning claims.",
    ),
    Capability(
        product="menhir",
        ability="facet retrieval",
        runner_command="archolith-bench menhir r2-facet",
        dependency="Offline fixture; optional real embedder for launch evidence",
        evidence_path="benchmarks/menhir-r2-facet-retrieval-YYYY-MM-DD.md",
        status="offline-smoke",
        launch_claim_rule="Use only as a Menhir claim after real fixture + real embedder evidence is tracked.",
    ),
    Capability(
        product="menhir",
        ability="belief/currentness",
        runner_command="archolith-bench menhir r3-belief",
        dependency="menhir-frontier source import; offline fixture",
        evidence_path="benchmarks/menhir-r3-belief-currentness-YYYY-MM-DD.md",
        status="offline-smoke",
        launch_claim_rule="Can describe harness coverage; do not claim production behavior without live Menhir evidence.",
    ),
    Capability(
        product="menhir",
        ability="oracle combiner",
        runner_command="archolith-bench menhir oracle",
        dependency="Offline fixture; real semantic scorer optional",
        evidence_path="benchmarks/menhir-oracle-combiner-YYYY-MM-DD.md",
        status="offline-smoke",
        launch_claim_rule="Fixture result is architecture evidence, not a production recall score.",
    ),
    Capability(
        product="menhir",
        ability="intent-aware retrieval",
        runner_command="archolith-bench menhir intent",
        dependency="Offline fixture; real semantic scorer optional",
        evidence_path="benchmarks/menhir-intent-routing-YYYY-MM-DD.md",
        status="offline-smoke",
        launch_claim_rule="Claim intent routing only after tracked no-harm and wrong-intent ablation evidence.",
    ),
    Capability(
        product="menhir",
        ability="institutional artifact memory",
        runner_command="archolith-bench menhir l4-artifacts",
        dependency="Offline fixture",
        evidence_path="benchmarks/menhir-l4-artifacts-YYYY-MM-DD.md",
        status="offline-smoke",
        launch_claim_rule="Fixture evidence may explain the capability; live graph walk required for production claims.",
    ),
    Capability(
        product="menhir",
        ability="structure-temporal blast radius",
        runner_command="archolith-bench menhir r5-structure-temporal",
        dependency="menhir-frontier source import; offline fixture",
        evidence_path="benchmarks/menhir-r5-structure-temporal-YYYY-MM-DD.md",
        status="offline-smoke",
        launch_claim_rule="Fixture evidence demonstrates the oracle; launch claims require tracked repo history evidence.",
    ),
    Capability(
        product="menhir",
        ability="extraction model selection",
        runner_command="archolith-bench menhir extraction-models",
        dependency="Provider API keys; Menhir extraction corpus",
        evidence_path="benchmarks/menhir-extraction-models-YYYY-MM-DD.md",
        status="live-required",
        launch_claim_rule="Provider/model recommendations require fresh tracked API-backed evidence.",
    ),
    Capability(
        product="archolith-context",
        ability="context curation and continuity",
        runner_command="archolith-bench proxy --all",
        dependency="Running archolith-context proxy and upstream API key",
        evidence_path="benchmarks/proxy-current-launch-YYYY-MM-DD.md",
        status="live-required",
        launch_claim_rule="No proxy savings claim until current launch config evidence is tracked.",
    ),
    Capability(
        product="archolith-filter",
        ability="tool-output compression",
        runner_command="archolith-bench filter --corpora corpora/",
        dependency="archolith-filter distribution or sibling editable install",
        evidence_path="benchmarks/filter-YYYY-MM-DD.md",
        status="candidate",
        launch_claim_rule="Compression claims require current corpus provenance and tracked aggregate evidence.",
    ),
    Capability(
        product="archolith-skree",
        ability="MCP token-waste reduction",
        runner_command="archolith-bench audit --before <real-before.json> --after <real-after.json>",
        dependency="archolith-audit distribution (`archolith_mcp_audit`) and real before/after logs",
        evidence_path="benchmarks/audit-live-before-after-YYYY-MM-DD.md",
        status="candidate",
        launch_claim_rule="Fixture audit numbers are not public claims; require real before/after logs.",
    ),
    Capability(
        product="archolith-security",
        ability="security benchmark coverage",
        runner_command="archolith-bench harness cyberseceval-4 / agentdojo",
        dependency="Official security benchmark tooling and isolated run environment",
        evidence_path="benchmarks/security-YYYY-MM-DD.md",
        status="candidate",
        launch_claim_rule="No benchmark-backed security claim until tracked CyberSecEval/AgentDojo/OWASP evidence.",
    ),
)


def capabilities_json(product: str | None = None, status: str | None = None) -> dict:
    rows = [
        asdict(c)
        for c in CAPABILITIES
        if (product is None or c.product == product) and (status is None or c.status == status)
    ]
    return {"suite": "capabilities", "total": len(rows), "capabilities": rows}


def render_capabilities_markdown(product: str | None = None, status: str | None = None) -> str:
    data = capabilities_json(product=product, status=status)
    lines = [
        "# Capability Evidence Registry",
        "",
        "| Product | Ability | Status | Runner | Evidence | Launch claim rule |",
        "|---------|---------|--------|--------|----------|-------------------|",
    ]
    for row in data["capabilities"]:
        lines.append(
            f"| {row['product']} | {row['ability']} | {row['status']} | "
            f"`{row['runner_command']}` | `{row['evidence_path']}` | {row['launch_claim_rule']} |"
        )
    return "\n".join(lines) + "\n"


def write_capabilities(path: Path, product: str | None = None, status: str | None = None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() == ".json":
        path.write_text(json.dumps(capabilities_json(product=product, status=status), indent=2), encoding="utf-8")
    else:
        path.write_text(render_capabilities_markdown(product=product, status=status), encoding="utf-8")
    return path
