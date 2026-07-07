"""Data models for the benchmark-local oracle pipeline (menhir R4-R7).

This mirrors the interface in menhir's `docs/research/oracle-amplified-retrieval.md`
(the *retrieval* altitude: per-candidate evidence scoring) and the runtime contract
in `oracle-runtime-interfaces.md`. Two object groups live here:

1. The oracle interface objects (`QueryContext`, `CandidateMemory`, `OracleResult`,
   `OraclePacket`) — immutable value objects so oracle execution stays thread-safe
   and deterministic by construction.
2. The fixture objects (`OracleMemory`, `OracleQuery`, `OracleFixture`) — the
   hand-authored benchmark corpus + queries with known support ids.

Everything is pure-Python and deterministic: this is the bench-first prototype of
the R4 (interface) / R6 (cheap oracles) / R7 (one-pass combiner) rungs. Nothing
here is wired into menhir production.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Mapping

# Scope keys define *where* a memory lives. A disagreement on any of these between
# query and candidate is the wrong-scope signal.
SCOPE_KEYS: tuple[str, ...] = ("repo", "branch", "project", "namespace")

# Belief buckets that mark a memory as no-longer-current. Under a current-intent
# query these are stale and should be suppressed for current truth.
STALE_BUCKETS: frozenset[str] = frozenset({"historical", "anergic", "blocked"})

# Evidence kinds ordered weakest -> strongest for the EvidenceOracle.
INFERRED_EVIDENCE: frozenset[str] = frozenset({"agent_inference"})
STRONG_EVIDENCE: frozenset[str] = frozenset({"git", "test", "user"})


class OraclePolarity(str, Enum):
    """Whether an oracle's evidence supports, contradicts, or is absent."""

    SUPPORT = "support"
    CONTRADICT = "contradict"
    MISSING = "missing"
    NEUTRAL = "neutral"


class OracleTarget(str, Enum):
    """Which retrieval property the oracle is speaking to."""

    RELEVANCE = "relevance"
    CURRENTNESS = "currentness"
    HISTORICALITY = "historicality"
    CONFLICT = "conflict"
    SCOPE = "scope"
    SAFETY = "safety"


class Role(str, Enum):
    """Role-specific logits the combiner maintains (not a single hidden score)."""

    RELEVANT = "relevant"
    CURRENT = "current"
    HISTORICAL = "historical"
    CONFLICT = "conflict"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class QueryContext:
    """Immutable query snapshot handed to every oracle.

    Extends the `oracle-amplified-retrieval.md` shape: file/symbol/test are tuples
    here (a query can touch several) rather than a single string.
    """

    text: str
    intent: str = "current"  # current | historical | any
    as_of_time: str | None = None
    repo: str | None = None
    branch: str | None = None
    project: str | None = None
    namespace: str | None = None
    files: tuple[str, ...] = ()
    symbols: tuple[str, ...] = ()
    tests: tuple[str, ...] = ()


@dataclass(frozen=True)
class CandidateMemory:
    """Immutable candidate handed to every oracle.

    Oracles read `metadata` (a prefetched snapshot) — they never fetch the world.
    Known metadata keys: repo, branch, project, namespace, files, symbols, tests,
    valid_at, invalid_at, created_at, superseded, belief_bucket, evidence_kinds,
    conflict_group, similarity (precomputed real cosine; SemanticOracle prefers it).
    """

    id: str
    content: str
    metadata: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class OracleResult:
    """One oracle's evidence about one candidate. Evidence, never final truth."""

    oracle: str
    probability: float
    confidence: float = 1.0
    polarity: OraclePolarity = OraclePolarity.SUPPORT
    target: OracleTarget = OracleTarget.RELEVANCE
    directness: float = 1.0
    scope_match: float = 1.0
    source_family: str = "semantic"
    note: str = ""


@dataclass
class OraclePacket:
    """Per-candidate reduction of all oracle results (the R7 OraclePacket).

    This is the retrieval-shaped evidence packet — NOT the task-shaped
    ColdStartBrief (see oracle-runtime-interfaces.md).
    """

    candidate_id: str
    results: list[OracleResult]
    role_logits: dict[str, float]
    combined_probability: float
    uncertainty: float
    rationale: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "candidate_id": self.candidate_id,
            "role_logits": {k: round(v, 4) for k, v in self.role_logits.items()},
            "combined_probability": round(self.combined_probability, 4),
            "uncertainty": round(self.uncertainty, 4),
            "rationale": self.rationale,
        }


@dataclass
class OracleMemory:
    """One hand-authored benchmark memory: text + the metadata oracles read."""

    id: str
    text: str = ""
    repo: str | None = None
    branch: str | None = None
    project: str | None = None
    namespace: str | None = None
    files: set[str] = field(default_factory=set)
    symbols: set[str] = field(default_factory=set)
    tests: set[str] = field(default_factory=set)
    valid_at: str | None = None
    invalid_at: str | None = None
    created_at: str | None = None
    superseded: bool = False
    belief_bucket: str | None = None
    evidence_kinds: set[str] = field(default_factory=set)
    conflict_group: str | None = None
    similarity: float | None = None  # precomputed real cosine; SemanticOracle prefers it

    @property
    def is_stale(self) -> bool:
        """True if superseded or parked in a non-current belief bucket."""
        return self.superseded or (self.belief_bucket in STALE_BUCKETS)

    def to_candidate(self) -> CandidateMemory:
        """Project to the immutable CandidateMemory an oracle sees."""
        return CandidateMemory(
            id=self.id,
            content=self.text,
            metadata={
                "repo": self.repo,
                "branch": self.branch,
                "project": self.project,
                "namespace": self.namespace,
                "files": tuple(sorted(self.files)),
                "symbols": tuple(sorted(self.symbols)),
                "tests": tuple(sorted(self.tests)),
                "valid_at": self.valid_at,
                "invalid_at": self.invalid_at,
                "created_at": self.created_at,
                "superseded": self.superseded,
                "belief_bucket": self.belief_bucket,
                "evidence_kinds": tuple(sorted(self.evidence_kinds)),
                "conflict_group": self.conflict_group,
                "similarity": self.similarity,
            },
        )

    @classmethod
    def from_dict(cls, data: dict) -> "OracleMemory":
        return cls(
            id=str(data["id"]),
            text=data.get("text", ""),
            repo=data.get("repo"),
            branch=data.get("branch"),
            project=data.get("project"),
            namespace=data.get("namespace"),
            files={str(v) for v in data.get("files", [])},
            symbols={str(v) for v in data.get("symbols", [])},
            tests={str(v) for v in data.get("tests", [])},
            valid_at=data.get("valid_at"),
            invalid_at=data.get("invalid_at"),
            created_at=data.get("created_at"),
            superseded=bool(data.get("superseded", False)),
            belief_bucket=data.get("belief_bucket"),
            evidence_kinds={str(v) for v in data.get("evidence_kinds", [])},
            conflict_group=data.get("conflict_group"),
            similarity=data.get("similarity"),
        )


@dataclass
class OracleQuery:
    """One benchmark query with gold support ids and scope/structure constraints."""

    id: str
    text: str = ""
    intent: str = "current"  # current | historical | any
    as_of_time: str | None = None
    repo: str | None = None
    branch: str | None = None
    project: str | None = None
    namespace: str | None = None
    files: set[str] = field(default_factory=set)
    symbols: set[str] = field(default_factory=set)
    tests: set[str] = field(default_factory=set)
    support_ids: list[str] = field(default_factory=list)
    note: str = ""

    def to_context(self) -> QueryContext:
        return QueryContext(
            text=self.text,
            intent=self.intent,
            as_of_time=self.as_of_time,
            repo=self.repo,
            branch=self.branch,
            project=self.project,
            namespace=self.namespace,
            files=tuple(sorted(self.files)),
            symbols=tuple(sorted(self.symbols)),
            tests=tuple(sorted(self.tests)),
        )

    @classmethod
    def from_dict(cls, data: dict) -> "OracleQuery":
        return cls(
            id=str(data["id"]),
            text=data.get("text", ""),
            intent=data.get("intent", "current"),
            as_of_time=data.get("as_of_time"),
            repo=data.get("repo"),
            branch=data.get("branch"),
            project=data.get("project"),
            namespace=data.get("namespace"),
            files={str(v) for v in data.get("files", [])},
            symbols={str(v) for v in data.get("symbols", [])},
            tests={str(v) for v in data.get("tests", [])},
            support_ids=[str(s) for s in data.get("support_ids", [])],
            note=data.get("note", ""),
        )


@dataclass
class OracleFixture:
    """A loadable benchmark fixture: a corpus of memories + a set of queries."""

    name: str
    description: str
    memories: list[OracleMemory] = field(default_factory=list)
    queries: list[OracleQuery] = field(default_factory=list)

    @property
    def memories_by_id(self) -> dict[str, OracleMemory]:
        return {m.id: m for m in self.memories}

    @classmethod
    def from_dict(cls, data: dict) -> "OracleFixture":
        return cls(
            name=data.get("name", "unnamed"),
            description=data.get("description", ""),
            memories=[OracleMemory.from_dict(m) for m in data.get("memories", [])],
            queries=[OracleQuery.from_dict(q) for q in data.get("queries", [])],
        )

    @classmethod
    def from_file(cls, path: str | Path) -> "OracleFixture":
        with open(path) as handle:
            return cls.from_dict(json.load(handle))
