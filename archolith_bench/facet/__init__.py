"""Benchmark-local facet retrieval (menhir R2, bench-first).

This package implements the *benchmark-local* facet mechanism described in
menhir's `.agent/plans/r2-facet-candidate-generation.md`. It is deliberately
self-contained inside archolith-bench: R2 is a **bench-first** rung, so nothing
here is wired into menhir production recall. The goal is a falsifiable
comparison of facet-first candidate generation + meet-point reranking against
honest baselines (BM25 / embedding / hybrid / file-context).

Pieces (all pure Python, deterministic, explainable):
- `models`     — `MemoryFacetSet`, `Memory`, `Query`, `FacetFixture`, facet vocab.
- `extractor`  — `FacetExtractor`: cheap deterministic rules (not LLM-heavy).
- `index`      — `MemoryFacetIndex`: candidates by compatible facet overlap.
- `reranker`   — `MeetPointReranker`: convergence scoring + explanation trace.
- `baselines`  — BM25, a deterministic embedding stand-in, RRF fusion, file-context.
- `metrics`    — recall@k / precision@k / MRR / NDCG / stale-hit / wrong-scope / ...
- `runner`     — condition ladder A-F over a fixture, gold vs extracted facet modes.
"""

from __future__ import annotations

from .extractor import ExtractorConfig, FacetExtractor
from .index import MemoryFacetIndex
from .models import (
    ALL_FACETS,
    SCALAR_FACETS,
    SCOPE_FACETS,
    SET_FACETS,
    STALE_BUCKETS,
    TEMPORAL_FACETS,
    FacetFixture,
    Memory,
    MemoryFacetSet,
    Query,
)
from .reranker import MeetPointExplanation, MeetPointReranker, MeetPointWeights

__all__ = [
    "ALL_FACETS",
    "SCALAR_FACETS",
    "SCOPE_FACETS",
    "SET_FACETS",
    "STALE_BUCKETS",
    "TEMPORAL_FACETS",
    "ExtractorConfig",
    "FacetExtractor",
    "FacetFixture",
    "Memory",
    "MemoryFacetIndex",
    "MemoryFacetSet",
    "MeetPointExplanation",
    "MeetPointReranker",
    "MeetPointWeights",
    "Query",
]
