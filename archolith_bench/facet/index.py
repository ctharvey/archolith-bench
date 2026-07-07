"""`MemoryFacetIndex` — deterministic candidate generation by facet overlap.

This is the candidate *generator*, not the ranker. It returns memories that
share at least one compatible discrete facet pair with the query — by overlap,
**not** by semantic similarity. Final ordering is the reranker's job; the index
only decides who is in the pool.

Determinism: candidates are returned sorted by (descending overlap, memory id),
so ties never depend on dict iteration order.
"""

from __future__ import annotations

from collections import defaultdict

from .models import Memory, MemoryFacetSet


class MemoryFacetIndex:
    """Inverted index from (facet, value) pairs to memory ids."""

    def __init__(self) -> None:
        self._postings: dict[tuple[str, str], set[str]] = defaultdict(set)
        self._ids: list[str] = []
        self._id_set: set[str] = set()

    def add(self, memory: Memory) -> None:
        """Index one memory's discrete facet pairs."""
        if memory.id not in self._id_set:
            self._ids.append(memory.id)
            self._id_set.add(memory.id)
        for pair in memory.facets.discrete_pairs():
            self._postings[pair].add(memory.id)

    def build(self, memories: list[Memory]) -> "MemoryFacetIndex":
        """Index a corpus and return self (for chaining)."""
        for memory in memories:
            self.add(memory)
        return self

    def candidates(self, query_facets: MemoryFacetSet) -> list[tuple[str, int]]:
        """Return (memory_id, overlap_count) for memories sharing ≥1 facet pair.

        `overlap_count` is the number of distinct (facet, value) pairs shared with
        the query — a cheap, transparent signal the reranker refines.
        """
        overlap: dict[str, int] = defaultdict(int)
        for pair in query_facets.discrete_pairs():
            for memory_id in self._postings.get(pair, ()):
                overlap[memory_id] += 1
        return sorted(overlap.items(), key=lambda item: (-item[1], item[0]))

    def candidate_ids(self, query_facets: MemoryFacetSet) -> list[str]:
        """Just the candidate ids, overlap-then-id ordered."""
        return [memory_id for memory_id, _ in self.candidates(query_facets)]

    def __len__(self) -> int:
        return len(self._ids)
