"""Fixture models for the intent benchmark.

An intent fixture is ONE topic's corpus (roles spanning the matrix) + queries that vary
only the task intent, each with the candidate that *should* surface for that intent. A
separate `no_harm_queries` set (generic/orientation) checks that intent-awareness never
degrades ordinary retrieval.

Memories project to the SHARED `oracle.models.CandidateMemory` (so they flow through the
existing OracleExecutor + combiner) but carry the extra `artifact_type`/`anchors` keys the
IntentOracle's role deriver reads.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from archolith_bench.oracle.models import CandidateMemory


@dataclass
class IntentMemory:
    """One hand-authored memory: text + the metadata the oracles read (incl. role)."""

    id: str
    text: str = ""
    artifact_type: str = "reference"
    anchors: list[str] = field(default_factory=list)
    repo: str | None = None
    branch: str | None = None
    project: str | None = None
    namespace: str | None = None
    valid_at: str | None = None
    invalid_at: str | None = None
    created_at: str | None = None
    superseded: bool = False
    belief_bucket: str | None = None
    evidence_kinds: list[str] = field(default_factory=list)

    def to_candidate(self) -> CandidateMemory:
        return CandidateMemory(
            id=self.id,
            content=self.text,
            metadata={
                "artifact_type": self.artifact_type,
                "anchors": tuple(self.anchors),
                "repo": self.repo,
                "branch": self.branch,
                "project": self.project,
                "namespace": self.namespace,
                "valid_at": self.valid_at,
                "invalid_at": self.invalid_at,
                "created_at": self.created_at,
                "superseded": self.superseded,
                "belief_bucket": self.belief_bucket,
                "evidence_kinds": tuple(self.evidence_kinds),
            },
        )

    @classmethod
    def from_dict(cls, data: dict) -> "IntentMemory":
        return cls(
            id=str(data["id"]),
            text=data.get("text", ""),
            artifact_type=data.get("artifact_type", "reference"),
            anchors=[str(a) for a in data.get("anchors", [])],
            repo=data.get("repo"),
            branch=data.get("branch"),
            project=data.get("project"),
            namespace=data.get("namespace"),
            valid_at=data.get("valid_at"),
            invalid_at=data.get("invalid_at"),
            created_at=data.get("created_at"),
            superseded=bool(data.get("superseded", False)),
            belief_bucket=data.get("belief_bucket"),
            evidence_kinds=[str(k) for k in data.get("evidence_kinds", [])],
        )


@dataclass
class IntentQuery:
    """One query. `expected_top` is the gold candidate id for documentation; the headline
    metric is role-based (top-1 role must be PREFERRED for the classified intent).
    `support_ids` is used by the no-harm arm (nDCG against a known good answer)."""

    id: str
    text: str = ""
    expected_top: str | None = None
    support_ids: list[str] = field(default_factory=list)
    note: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> "IntentQuery":
        return cls(
            id=str(data["id"]),
            text=data.get("text", ""),
            expected_top=data.get("expected_top"),
            support_ids=[str(s) for s in data.get("support_ids", [])],
            note=data.get("note", ""),
        )


@dataclass
class IntentFixture:
    name: str
    description: str
    memories: list[IntentMemory] = field(default_factory=list)
    queries: list[IntentQuery] = field(default_factory=list)
    no_harm_queries: list[IntentQuery] = field(default_factory=list)

    @property
    def candidates(self) -> list[CandidateMemory]:
        return [m.to_candidate() for m in self.memories]

    @classmethod
    def from_dict(cls, data: dict) -> "IntentFixture":
        return cls(
            name=data.get("name", "unnamed"),
            description=data.get("description", ""),
            memories=[IntentMemory.from_dict(m) for m in data.get("memories", [])],
            queries=[IntentQuery.from_dict(q) for q in data.get("queries", [])],
            no_harm_queries=[IntentQuery.from_dict(q) for q in data.get("no_harm_queries", [])],
        )

    @classmethod
    def from_file(cls, path: str | Path) -> "IntentFixture":
        with open(path) as handle:
            return cls.from_dict(json.load(handle))
