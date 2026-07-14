"""Write-sensitive graph fingerprints: prove a benchmark did not mutate what it measured.

A retrieval benchmark that writes to the graph it measures produces order-dependent
results: condition B then runs against a graph condition A already modified. Menhir's
``RecallService.recall()`` defaults to ``update_access=True``, and both R1 recall call
sites historically omitted the override -- see the fix in ``retriever.py`` /
``run_r1_dummy.py``. Passing ``update_access=False`` makes that *intended*; this module
makes it *enforced*.

WHAT ``update_access=True`` ACTUALLY MUTATES (verified in menhir):
  - ``SET n.last_accessed = datetime()``   -- memory_queries.touch_retrieved_nodes
  - ``SET r.weight = ...``                 -- consolidation_queries.increment_edge_weight
  - rehydration scheduling                 -- lifecycle_service (freshness / rehydration_count)

Also covered, because the clone protocol forbids it:
  - ``SET n.edge_count = ...``             -- consolidation_queries.sync_edge_counts, invoked
    unconditionally by ``prepare_memory_runtime()``. Recomputing edge_count against a clone's
    partial topology silently flattens ``prominence_bonus``, so a benchmark clone must copy
    edge_count from prod and NEVER resynchronize it. A drift here means someone called
    ``prepare_memory_runtime()`` on the clone.

WHY A HASH AND NOT A SUM: an aggregate like ``sum(last_accessed)`` is collision-prone and
blind to offsetting changes -- one node moving forward and another back can leave the sum
unchanged. These fingerprints hash the sorted ``uuid|value`` pairs, so ANY per-entity change
is detected, including reorderings and compensating edits.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

# Each probe is (name, cypher). Every query must RETURN exactly `k` (a stable identity)
# and `v` (the write-sensitive value, stringified), and must be ORDER BY k so the hash is
# deterministic regardless of storage order.
WRITE_SENSITIVE_PROBES: tuple[tuple[str, str], ...] = (
    (
        "node_last_accessed",
        "MATCH (n:Entity) RETURN n.uuid AS k, toString(n.last_accessed) AS v ORDER BY k",
    ),
    (
        "node_edge_count",
        "MATCH (n:Entity) RETURN n.uuid AS k, toString(n.edge_count) AS v ORDER BY k",
    ),
    (
        "node_freshness",
        "MATCH (n:Entity) RETURN n.uuid AS k, toString(n.freshness) AS v ORDER BY k",
    ),
    (
        "node_rehydration_count",
        "MATCH (n:Entity) RETURN n.uuid AS k, toString(n.rehydration_count) AS v ORDER BY k",
    ),
    (
        "edge_weight",
        "MATCH ()-[r]->() WHERE r.uuid IS NOT NULL "
        "RETURN r.uuid AS k, toString(r.weight) AS v ORDER BY k",
    ),
)


@dataclass(frozen=True)
class GraphWriteFingerprint:
    """A hash per write-sensitive surface. Compare two of these across a benchmark run."""

    hashes: dict[str, str]

    def drift(self, other: "GraphWriteFingerprint") -> list[str]:
        """Surfaces whose contents changed between self and other."""
        names = set(self.hashes) | set(other.hashes)
        return sorted(n for n in names if self.hashes.get(n) != other.hashes.get(n))


def _hash_rows(session: Any, cypher: str) -> str:
    h = hashlib.sha256()
    for record in session.run(cypher):
        k = record["k"]
        v = record["v"]
        # A NULL must hash distinctly from a literal "None" string a caller could have
        # written, so encode absence with a sentinel rather than relying on str() coercion.
        value = "\x00NULL" if v is None else str(v)
        h.update(str(k).encode("utf-8"))
        h.update(b"\x1f")
        h.update(value.encode("utf-8"))
        h.update(b"\x1e")
    return h.hexdigest()


def graph_write_fingerprint(session: Any) -> GraphWriteFingerprint:
    """Fingerprint every write-sensitive surface a benchmark must leave untouched.

    ``session`` is a neo4j driver session (anything with ``.run(cypher)``).
    """
    return GraphWriteFingerprint(
        hashes={name: _hash_rows(session, cypher) for name, cypher in WRITE_SENSITIVE_PROBES}
    )


def assert_no_writes(
    before: GraphWriteFingerprint,
    after: GraphWriteFingerprint,
    *,
    context: str = "benchmark run",
) -> None:
    """Raise if the graph changed. Call around the whole condition loop, not per query.

    A benchmark that mutates its own corpus yields order-dependent results and its
    multi-condition comparisons are void. Failing loudly here is the point: a silent
    pass would let a contaminated result be reported as evidence.
    """
    drifted = before.drift(after)
    if drifted:
        detail = "\n".join(
            f"  {name}: {before.hashes.get(name, '<absent>')[:16]}"
            f" -> {after.hashes.get(name, '<absent>')[:16]}"
            for name in drifted
        )
        raise AssertionError(
            f"{context} MUTATED the graph it measured; these surfaces drifted:\n{detail}\n"
            f"Multi-condition results are order-contaminated and must not be reported.\n"
            f"Likely causes: a recall() call missing update_access=False, or "
            f"prepare_memory_runtime() being called on the clone (it runs sync_edge_counts(), "
            f"which rewrites node_edge_count)."
        )
