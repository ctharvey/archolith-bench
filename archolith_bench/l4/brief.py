"""ColdStartBrief v0 — assemble a task-shaped brief from L4 artifacts (bench-first).

The smallest useful brief: given a task, ask the MemoryOracle for relevant artifacts
and bucket them, carrying provenance. It enforces invariant 8 structurally —

    TRUSTED (current)  -> a FACT bucket (failed_approaches / decisions / risks)
    CANDIDATE          -> hypotheses           (never a fact)
    HISTORICAL/superseded -> stale_or_contradicted  (flagged, never asserted as current)

so a CANDIDATE or superseded artifact can never be presented as a current fact. This is
NOT a ColdStartOracle (no LLM synthesis) — it is a deterministic bucketing + a
recommended first action. Schema is a subset of `docs/research/cold-start-brief.md`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .memory_oracle import MemoryOracle
from .models import Artifact, ArtifactType, Status


class Epistemic(str, Enum):
    FACT = "fact"             # TRUSTED, current
    HYPOTHESIS = "hypothesis"  # CANDIDATE
    HISTORICAL = "historical"  # superseded


def _epistemic(a: Artifact) -> Epistemic:
    if a.is_historical:
        return Epistemic.HISTORICAL
    if a.status == Status.CANDIDATE:
        return Epistemic.HYPOTHESIS
    return Epistemic.FACT


@dataclass(frozen=True)
class BriefItem:
    artifact_id: str
    artifact_type: str
    text: str
    epistemic: Epistemic
    evidence_refs: tuple[str, ...]

    def to_dict(self) -> dict:
        return {
            "artifact_id": self.artifact_id,
            "type": self.artifact_type,
            "text": self.text,
            "epistemic": self.epistemic.value,
            "evidence": list(self.evidence_refs),
        }


@dataclass
class ColdStartBriefV0:
    task: str
    failed_approaches: list[BriefItem] = field(default_factory=list)
    decisions: list[BriefItem] = field(default_factory=list)
    risks: list[BriefItem] = field(default_factory=list)
    hypotheses: list[BriefItem] = field(default_factory=list)
    stale_or_contradicted: list[BriefItem] = field(default_factory=list)
    recommended_first_action: str | None = None

    def facts(self) -> list[BriefItem]:
        """The FACT-labeled items (TRUSTED, current)."""
        return [*self.failed_approaches, *self.decisions, *self.risks]

    def render(self) -> str:
        lines = [f"TASK: {self.task}"]
        for label, items in (
            ("FAILED APPROACHES (avoid)", self.failed_approaches),
            ("DECISIONS", self.decisions),
            ("RISKS", self.risks),
            ("HYPOTHESES (unverified)", self.hypotheses),
            ("STALE / CONTRADICTED", self.stale_or_contradicted),
        ):
            for it in items:
                refs = f" [{', '.join(it.evidence_refs)}]" if it.evidence_refs else ""
                lines.append(f"{label}: {it.text} ({it.epistemic.value}){refs}")
        if self.recommended_first_action:
            lines.append(f"RECOMMENDED FIRST ACTION: {self.recommended_first_action}")
        return "\n".join(lines)

    def token_count(self) -> int:
        return len(self.render().split())

    def to_dict(self) -> dict:
        return {
            "task": self.task,
            "failed_approaches": [i.to_dict() for i in self.failed_approaches],
            "decisions": [i.to_dict() for i in self.decisions],
            "risks": [i.to_dict() for i in self.risks],
            "hypotheses": [i.to_dict() for i in self.hypotheses],
            "stale_or_contradicted": [i.to_dict() for i in self.stale_or_contradicted],
            "recommended_first_action": self.recommended_first_action,
        }


def _item(a: Artifact) -> BriefItem:
    return BriefItem(
        artifact_id=a.id,
        artifact_type=a.type.value,
        text=a.summary,
        epistemic=_epistemic(a),
        evidence_refs=tuple(f"{e.kind}:{e.ref}" for e in a.evidence),
    )


def build_brief(*, task: str, anchors: list[str] | None, oracle: MemoryOracle, limit: int = 10) -> ColdStartBriefV0:
    """Build a ColdStartBrief v0 for a task from the artifacts the oracle surfaces."""
    brief = ColdStartBriefV0(task=task)
    matched_artifacts = [m.artifact for m in oracle.find(text=task, anchors=anchors, limit=limit)]

    for a in matched_artifacts:
        item = _item(a)
        if a.is_historical:
            brief.stale_or_contradicted.append(item)       # invariant 8: flagged, not current
        elif a.status == Status.CANDIDATE:
            brief.hypotheses.append(item)                  # invariant 8: hypothesis, never fact
        elif a.type == ArtifactType.FAILURE:
            brief.failed_approaches.append(item)
        elif a.type == ArtifactType.DECISION:
            brief.decisions.append(item)
        elif a.type == ArtifactType.INCIDENT:
            brief.risks.append(item)

    brief.recommended_first_action = _recommend(matched_artifacts)
    return brief


def _recommend(artifacts: list[Artifact]) -> str | None:
    """Deterministic first action: avoid the top current FAILURE, prefer its corrective DECISION."""
    failures = [a for a in artifacts if a.type == ArtifactType.FAILURE and a.is_trusted and not a.is_historical]
    if not failures:
        return None
    fa = failures[0]
    rec = f"Avoid the known failed approach ({fa.id}): {fa.summary}"
    # a current TRUSTED DECISION sharing an anchor with the failure is the corrective
    corrective = next(
        (a for a in artifacts
         if a.type == ArtifactType.DECISION and a.is_trusted and not a.is_historical
         and set(a.anchors) & set(fa.anchors)),
        None,
    )
    if corrective:
        rec += f". Prefer {corrective.id}: {corrective.summary}"
    return rec
