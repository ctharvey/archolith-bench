"""Data models for the L4 institutional-artifact loop v0 (menhir L4 slice, bench-first).

These are the bench-side, pure-Python models for the smallest L4 slice: institutional
artifacts (Decision / Failure / Incident) backed by first-class Evidence. They mirror
the menhir schema they will project onto (`.agent/plans/l4-artifact-loop-v0.md`):

- Evidence is FIRST-CLASS here (a value object), not a loose note — D1.
- TRUSTED vs CANDIDATE reuses the existing trust tier idea (D2); HISTORICAL is the
  superseded-not-deleted state (invariant 7).
- Decision/Failure/Incident are the only types in v0 (D3); L3 is out of scope.

The models hold data only. All transition rules (TRUSTED requires evidence, LLM can't
be TRUSTED on write, superseded -> historical) live in the ArtifactMutator — the single
writer — not here.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

# Evidence kinds. The structural/deterministic ones are anchors that are never
# LLM-derived (invariant 6); agent_inference is the weakest, interpretive kind.
EVIDENCE_KINDS: frozenset[str] = frozenset({"git", "test", "user", "log", "agent_inference"})
STRUCTURAL_EVIDENCE: frozenset[str] = frozenset({"git", "test"})


class ArtifactType(str, Enum):
    DECISION = "decision"
    FAILURE = "failure"
    INCIDENT = "incident"


class Status(str, Enum):
    CANDIDATE = "candidate"   # low-trust, not asserted as fact
    TRUSTED = "trusted"       # reviewed/evidence-backed, recallable as fact
    HISTORICAL = "historical" # superseded — kept, never deleted (invariant 7)


class Source(str, Enum):
    HUMAN = "human"
    LLM = "llm"


@dataclass(frozen=True)
class Evidence:
    """A first-class piece of evidence backing an artifact (not a loose note)."""

    kind: str                 # git | test | user | log | agent_inference
    ref: str                  # anchor: 'file.py:symbol' / commit sha / test id
    directness: float = 1.0   # direct evidence (1.0) vs inferred (lower)
    note: str | None = None

    @property
    def is_structural(self) -> bool:
        """Deterministic anchor (git/test) — never LLM-derived (invariant 6)."""
        return self.kind in STRUCTURAL_EVIDENCE

    @classmethod
    def from_dict(cls, data: dict) -> "Evidence":
        return cls(
            kind=str(data["kind"]),
            ref=str(data["ref"]),
            directness=float(data.get("directness", 1.0)),
            note=data.get("note"),
        )

    def to_dict(self) -> dict:
        out = {"kind": self.kind, "ref": self.ref, "directness": self.directness}
        if self.note:
            out["note"] = self.note
        return out


@dataclass
class Artifact:
    """One L4 institutional artifact (Decision / Failure / Incident)."""

    id: str
    type: ArtifactType
    summary: str
    body: str = ""
    status: Status = Status.CANDIDATE
    source: Source = Source.HUMAN
    evidence: list[Evidence] = field(default_factory=list)
    anchors: list[str] = field(default_factory=list)  # structural anchors (file/symbol/test), deterministic
    supersedes: str | None = None
    superseded_by: str | None = None
    created_at: str | None = None

    @property
    def has_evidence(self) -> bool:
        return len(self.evidence) > 0

    @property
    def is_trusted(self) -> bool:
        return self.status == Status.TRUSTED

    @property
    def is_historical(self) -> bool:
        return self.status == Status.HISTORICAL or self.superseded_by is not None

    @classmethod
    def from_dict(cls, data: dict) -> "Artifact":
        return cls(
            id=str(data["id"]),
            type=ArtifactType(data["type"]),
            summary=data.get("summary", ""),
            body=data.get("body", ""),
            status=Status(data.get("status", "candidate")),
            source=Source(data.get("source", "human")),
            evidence=[Evidence.from_dict(e) for e in data.get("evidence", [])],
            anchors=[str(a) for a in data.get("anchors", [])],
            supersedes=data.get("supersedes"),
            superseded_by=data.get("superseded_by"),
            created_at=data.get("created_at"),
        )

    def to_dict(self) -> dict:
        out: dict = {
            "id": self.id,
            "type": self.type.value,
            "summary": self.summary,
            "status": self.status.value,
            "source": self.source.value,
            "evidence": [e.to_dict() for e in self.evidence],
        }
        if self.body:
            out["body"] = self.body
        if self.anchors:
            out["anchors"] = list(self.anchors)
        if self.supersedes:
            out["supersedes"] = self.supersedes
        if self.superseded_by:
            out["superseded_by"] = self.superseded_by
        if self.created_at:
            out["created_at"] = self.created_at
        return out


@dataclass
class ArtifactFixture:
    """A loadable corpus of artifacts + tasks for the L4 benchmark."""

    name: str
    description: str
    artifacts: list[Artifact] = field(default_factory=list)
    tasks: list[dict] = field(default_factory=list)

    @property
    def artifacts_by_id(self) -> dict[str, Artifact]:
        return {a.id: a for a in self.artifacts}

    @classmethod
    def from_dict(cls, data: dict) -> "ArtifactFixture":
        return cls(
            name=data.get("name", "unnamed"),
            description=data.get("description", ""),
            artifacts=[Artifact.from_dict(a) for a in data.get("artifacts", [])],
            tasks=list(data.get("tasks", [])),
        )

    @classmethod
    def from_file(cls, path: str | Path) -> "ArtifactFixture":
        with open(path) as handle:
            return cls.from_dict(json.load(handle))
