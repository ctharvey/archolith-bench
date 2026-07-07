"""Data models for the R1 hybrid-retrieval benchmark.

A fixture is a corpus of memories + a set of queries grouped into the seven R1
families. Each memory carries the gold labels the R1 metrics need: scope
(repo/project — the wrong-scope signal), symbols, the exact strings it contains
(error strings, identifiers), and a stale flag (superseded / historical).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

# The seven R1 fixture families (deferred-verification.md, R1 ladder).
R1_FAMILIES: tuple[str, ...] = (
    "exact_error_string",
    "symbol_name_query",
    "paraphrased_debug_question",
    "stale_semantic_neighbor",
    "wrong_repo_same_topic",
    "buried_relevant_memory",
    "historical_only_vs_current_truth",
)


@dataclass
class R1Memory:
    """One benchmark memory: raw text + gold labels for the R1 metrics."""

    id: str
    text: str
    repo: str | None = None
    project: str | None = None
    symbols: set[str] = field(default_factory=set)
    exact_strings: set[str] = field(default_factory=set)
    stale: bool = False  # superseded or historical-only

    @classmethod
    def from_dict(cls, data: dict) -> "R1Memory":
        return cls(
            id=str(data["id"]),
            text=data.get("text", ""),
            repo=_opt_str(data.get("repo")),
            project=_opt_str(data.get("project")),
            symbols={str(s) for s in (data.get("symbols") or [])},
            exact_strings={str(s) for s in (data.get("exact_strings") or [])},
            stale=bool(data.get("stale", False)),
        )


@dataclass
class R1Query:
    """One benchmark query with gold support IDs and family/scope/target labels."""

    id: str
    text: str
    family: str
    support_ids: list[str] = field(default_factory=list)
    intent: str = "current"  # current | historical
    repo: str | None = None
    project: str | None = None
    target_symbol: str | None = None  # symbol_name_query: the symbol that must surface
    target_exact_string: str | None = None  # exact_error_string: the literal that must surface
    paraphrase_group: str | None = None
    note: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> "R1Query":
        return cls(
            id=str(data["id"]),
            text=data.get("text", ""),
            family=str(data.get("family", "")),
            support_ids=[str(s) for s in data.get("support_ids", [])],
            intent=data.get("intent", "current"),
            repo=_opt_str(data.get("repo")),
            project=_opt_str(data.get("project")),
            target_symbol=_opt_str(data.get("target_symbol")),
            target_exact_string=_opt_str(data.get("target_exact_string")),
            paraphrase_group=_opt_str(data.get("paraphrase_group")),
            note=data.get("note", ""),
        )


@dataclass
class R1Fixture:
    """A loadable R1 benchmark fixture."""

    name: str
    description: str
    memories: list[R1Memory] = field(default_factory=list)
    queries: list[R1Query] = field(default_factory=list)

    @property
    def memories_by_id(self) -> dict[str, R1Memory]:
        return {m.id: m for m in self.memories}

    @classmethod
    def from_dict(cls, data: dict) -> "R1Fixture":
        return cls(
            name=data.get("name", "unnamed"),
            description=data.get("description", ""),
            memories=[R1Memory.from_dict(m) for m in data.get("memories", [])],
            queries=[R1Query.from_dict(q) for q in data.get("queries", [])],
        )

    @classmethod
    def from_file(cls, path: str | Path) -> "R1Fixture":
        with open(path) as handle:
            return cls.from_dict(json.load(handle))


def _opt_str(value: object) -> str | None:
    return str(value) if value not in (None, "") else None
