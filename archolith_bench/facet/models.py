"""Data models for benchmark-local facet retrieval.

The facet set mirrors menhir's R2 plan exactly:
`actor, object, operation, file, symbol, test, valid_time, learned_time,
evidence_type, source_id, repo, project, namespace, belief_bucket`.

Facets split three ways by how they are matched:
- SET facets are multi-valued (a memory can touch several files/symbols).
- SCALAR facets are single-valued scope/provenance labels.
- TEMPORAL facets are ISO-8601 strings compared lexically (same format ⇒ same
  ordering as chronological order).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

SET_FACETS: tuple[str, ...] = (
    "actor",
    "object",
    "operation",
    "file",
    "symbol",
    "test",
    "evidence_type",
)
SCALAR_FACETS: tuple[str, ...] = (
    "source_id",
    "repo",
    "project",
    "namespace",
    "belief_bucket",
)
TEMPORAL_FACETS: tuple[str, ...] = ("valid_time", "learned_time")
ALL_FACETS: tuple[str, ...] = SET_FACETS + SCALAR_FACETS + TEMPORAL_FACETS

# Scope facets define *where* a memory lives. A conflict on any of these between
# query and candidate is the "wrong-scope" signal (e.g. wrong_repo_same_topic).
SCOPE_FACETS: tuple[str, ...] = ("repo", "project", "namespace")

# Belief buckets that mark a memory as no-longer-current. Under a "current"
# query intent these draw the stale/superseded penalty.
STALE_BUCKETS: frozenset[str] = frozenset({"historical", "anergic", "blocked"})


@dataclass
class MemoryFacetSet:
    """Explicit facet labels for one memory or one query's constraints."""

    actor: set[str] = field(default_factory=set)
    object: set[str] = field(default_factory=set)
    operation: set[str] = field(default_factory=set)
    file: set[str] = field(default_factory=set)
    symbol: set[str] = field(default_factory=set)
    test: set[str] = field(default_factory=set)
    evidence_type: set[str] = field(default_factory=set)
    source_id: str | None = None
    repo: str | None = None
    project: str | None = None
    namespace: str | None = None
    belief_bucket: str | None = None
    valid_time: str | None = None
    learned_time: str | None = None

    def values(self, facet: str) -> set[str]:
        """Return the value set for any facet (scalars yield a 0/1-element set)."""
        raw = getattr(self, facet)
        if isinstance(raw, set):
            return raw
        return {raw} if raw else set()

    def discrete_pairs(self) -> set[tuple[str, str]]:
        """All (facet, value) pairs usable for overlap indexing.

        Temporal facets are excluded — time is handled as window compatibility in
        the reranker, not as a discrete equality match.
        """
        pairs: set[tuple[str, str]] = set()
        for facet in SET_FACETS:
            for value in getattr(self, facet):
                pairs.add((facet, value))
        for facet in SCALAR_FACETS:
            value = getattr(self, facet)
            if value:
                pairs.add((facet, value))
        return pairs

    @classmethod
    def from_dict(cls, data: dict) -> "MemoryFacetSet":
        """Build from fixture JSON (set facets accept a list or a scalar)."""
        kwargs: dict = {}
        for facet in SET_FACETS:
            raw = data.get(facet, [])
            if isinstance(raw, str):
                raw = [raw]
            kwargs[facet] = {str(v) for v in (raw or [])}
        for facet in (*SCALAR_FACETS, *TEMPORAL_FACETS):
            value = data.get(facet)
            kwargs[facet] = str(value) if value is not None else None
        return cls(**kwargs)

    def to_dict(self) -> dict:
        """Serialize to JSON-friendly form (sorted sets for determinism)."""
        out: dict = {}
        for facet in SET_FACETS:
            values = getattr(self, facet)
            if values:
                out[facet] = sorted(values)
        for facet in (*SCALAR_FACETS, *TEMPORAL_FACETS):
            value = getattr(self, facet)
            if value is not None:
                out[facet] = value
        return out


@dataclass
class Memory:
    """One hand-authored benchmark memory: raw text + gold facet labels."""

    id: str
    text: str
    facets: MemoryFacetSet = field(default_factory=MemoryFacetSet)
    superseded: bool = False

    @property
    def is_stale(self) -> bool:
        """True if explicitly superseded or parked in a non-current belief bucket."""
        return self.superseded or (self.facets.belief_bucket in STALE_BUCKETS)

    @classmethod
    def from_dict(cls, data: dict) -> "Memory":
        return cls(
            id=str(data["id"]),
            text=data.get("text", ""),
            facets=MemoryFacetSet.from_dict(data.get("facets", {})),
            superseded=bool(data.get("superseded", False)),
        )


@dataclass
class Query:
    """One benchmark query with gold support IDs and facet constraints."""

    id: str
    text: str
    facets: MemoryFacetSet = field(default_factory=MemoryFacetSet)
    support_ids: list[str] = field(default_factory=list)
    intent: str = "current"  # current | historical | any
    required_facets: list[str] = field(default_factory=list)
    paraphrase_group: str | None = None
    note: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> "Query":
        return cls(
            id=str(data["id"]),
            text=data.get("text", ""),
            facets=MemoryFacetSet.from_dict(data.get("facets", {})),
            support_ids=[str(s) for s in data.get("support_ids", [])],
            intent=data.get("intent", "current"),
            required_facets=list(data.get("required_facets", [])),
            paraphrase_group=data.get("paraphrase_group"),
            note=data.get("note", ""),
        )


@dataclass
class FacetFixture:
    """A loadable benchmark fixture: a corpus of memories + a set of queries."""

    name: str
    description: str
    memories: list[Memory] = field(default_factory=list)
    queries: list[Query] = field(default_factory=list)

    @property
    def memories_by_id(self) -> dict[str, Memory]:
        return {m.id: m for m in self.memories}

    @classmethod
    def from_dict(cls, data: dict) -> "FacetFixture":
        return cls(
            name=data.get("name", "unnamed"),
            description=data.get("description", ""),
            memories=[Memory.from_dict(m) for m in data.get("memories", [])],
            queries=[Query.from_dict(q) for q in data.get("queries", [])],
        )

    @classmethod
    def from_file(cls, path: str | Path) -> "FacetFixture":
        with open(path) as handle:
            return cls.from_dict(json.load(handle))
