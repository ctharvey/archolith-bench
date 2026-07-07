"""Bounded, deterministic oracle executor (menhir R4).

Oracle separation is only useful if it stays fast and deterministic. In menhir
production this fans out across a bounded thread/async pool; in this offline bench
we execute sequentially but enforce the same invariant that matters for the bench:

    parallel oracle execution must not make ranking nondeterministic.

So results are grouped by candidate and reduced in a fixed order
(candidate id, then oracle priority order). Oracles are read-only value-in/value-out
functions, so sequential vs parallel execution yields identical results — the
`max_concurrency` knob is recorded for shape but does not change the output.
"""

from __future__ import annotations

from .models import CandidateMemory, OracleResult, QueryContext
from .oracles import RetrievalOracle


class OracleExecutor:
    """Evaluate every (candidate, oracle) pair and group results deterministically."""

    def __init__(self, oracles: list[RetrievalOracle], max_concurrency: int = 16) -> None:
        if not oracles:
            raise ValueError("OracleExecutor needs at least one oracle")
        self.oracles = oracles
        self.max_concurrency = max_concurrency
        # Stable oracle priority order for deterministic reduction.
        self._order = {oracle.name: i for i, oracle in enumerate(oracles)}

    def evaluate(
        self, query: QueryContext, candidates: list[CandidateMemory]
    ) -> dict[str, list[OracleResult]]:
        """Return {candidate_id: [OracleResult, ...]} in deterministic order."""
        grouped: dict[str, list[OracleResult]] = {}
        for candidate in sorted(candidates, key=lambda c: c.id):
            results = [oracle.evaluate(query, candidate) for oracle in self.oracles]
            results.sort(key=lambda r: self._order.get(r.oracle, len(self._order)))
            grouped[candidate.id] = results
        return grouped
