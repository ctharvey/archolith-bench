"""Benchmark-local L4 institutional-artifact loop v0 (menhir L4 slice, bench-first).

The smallest safe slice of the L3/L4 overlay: Decision/Failure/Incident artifacts
backed by first-class Evidence, written only through the ArtifactMutator (R9-lite),
read by a MemoryOracle, surfaced in a ColdStartBrief v0. Pure-Python, deterministic;
nothing here touches menhir production. Plan: menhir `.agent/plans/l4-artifact-loop-v0.md`.
"""

from __future__ import annotations

from .models import (
    EVIDENCE_KINDS,
    STRUCTURAL_EVIDENCE,
    Artifact,
    ArtifactFixture,
    ArtifactType,
    Evidence,
    Source,
    Status,
)
from .memory_oracle import ArtifactMatch, MemoryOracle
from .mutator import ArtifactMutator, MutatorError

__all__ = [
    "EVIDENCE_KINDS",
    "STRUCTURAL_EVIDENCE",
    "Artifact",
    "ArtifactFixture",
    "ArtifactMatch",
    "ArtifactMutator",
    "ArtifactType",
    "Evidence",
    "MemoryOracle",
    "MutatorError",
    "Source",
    "Status",
]
