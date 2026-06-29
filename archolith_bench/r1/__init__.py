"""Benchmark-local R1 ladder — hybrid candidate generation + source-aware priors.

R1 (menhir research ladder) tests whether menhir's *attributed hybrid* recall
path (vector + BM25 fused on rank, with a source-aware floor) beats today's fused
baseline on exact-string / symbol recall WITHOUT regressing stale-hit or
wrong-scope injection — and, if so, what ``hybrid_alpha`` to ship.

Repo-split discipline: this package lives in archolith-bench and consumes menhir
as a library (via ``recall(trace=True)``, the R0 instrument). It never modifies
menhir ``src/``. The pure-stdlib core (models, metrics, runner, stub retriever)
runs anywhere/CI; the live menhir retriever is an opt-in seam that needs a
throwaway Neo4j + an embedder.
"""
