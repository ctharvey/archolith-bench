"""Retrievers for the R1 ladder.

A retriever maps one query to a ranked list of memory ids (plus latency and an
optional R0 trace). Two implementations:

- ``StubRetriever`` — pure-stdlib, deterministic. Blends a lexical "vector"
  signal and an exact-token "bm25" signal by ``alpha`` and models the
  source-aware floor (exact/symbol hits survive even at low overlap). It exists
  so the runner, metrics, and gate are testable in CI without a live graph — the
  R1 analogue of facet's ``LexicalEmbeddingStub``. It is a harness sanity device,
  NOT a source of headline numbers.

- ``MenhirLiveRetriever`` — the real seam. Wraps a seeded menhir ``RecallService``
  and runs ``recall(trace=True)`` under a per-condition ``RetrievalTuningConfig``,
  returning the ranked node uuids and the R0 trace. Needs a throwaway Neo4j + an
  embedder (see ``scripts/run_r1_bench.py``). Grounding fixture support ids to the
  graph's extracted node uuids is the owed pairing step before its numbers count.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

from .models import R1Fixture, R1Memory, R1Query

if TYPE_CHECKING:  # pragma: no cover - typing only
    from menhir.services.recall_service import RecallService

_TOKEN = re.compile(r"[a-zA-Z0-9_]+")


def _tokens(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN.findall(text)]


@dataclass
class RankResult:
    ranked_ids: list[str]
    latency_ms: float
    trace: dict[str, Any] | None = None


class Retriever(Protocol):
    name: str

    def rank(self, query: R1Query, k: int) -> RankResult: ...


@dataclass
class StubRetriever:
    """Deterministic alpha-blended retriever over a fixture corpus.

    score = alpha * vector_sig + (1 - alpha) * bm25_sig, where vector_sig is
    Jaccard token overlap (a smooth, recall-friendly "semantic" stand-in) and
    bm25_sig is exact query-token containment (lexical precision). When
    ``source_aware`` is set, a candidate that contains a query's exact-string or
    symbol target is floor-exempt: it is guaranteed a non-zero score so it cannot
    be dropped purely for low lexical overlap — the behavior R1's source-aware
    floor adds on the real path.
    """

    fixture: R1Fixture
    alpha: float = 0.5
    source_aware: bool = True
    name: str = "stub"

    def __post_init__(self) -> None:
        self._mem_tokens = {m.id: set(_tokens(m.text)) for m in self.fixture.memories}

    def rank(self, query: R1Query, k: int) -> RankResult:
        start = time.perf_counter()
        q_tokens = set(_tokens(query.text))
        scored: list[tuple[float, str]] = []
        for mem in self.fixture.memories:
            m_tokens = self._mem_tokens[mem.id]
            union = q_tokens | m_tokens
            vector_sig = len(q_tokens & m_tokens) / len(union) if union else 0.0
            bm25_sig = (
                sum(1 for t in q_tokens if t in m_tokens) / len(q_tokens) if q_tokens else 0.0
            )
            score = self.alpha * vector_sig + (1.0 - self.alpha) * bm25_sig
            if self.source_aware:
                score = max(score, self._floor_exempt_prior(query, mem))
            if score > 0.0:
                scored.append((score, mem.id))
        # Deterministic: score desc, then id asc to break ties stably.
        scored.sort(key=lambda pair: (-pair[0], pair[1]))
        ranked = [mid for _, mid in scored]
        latency_ms = (time.perf_counter() - start) * 1000.0
        return RankResult(ranked_ids=ranked, latency_ms=latency_ms)

    def _floor_exempt_prior(self, query: R1Query, mem: R1Memory) -> float:
        """A small guaranteed score for exact/symbol hits (only when bm25 is in play)."""
        if self.alpha >= 1.0:  # pure vector: no lexical/source exemption
            return 0.0
        if query.target_exact_string and (
            query.target_exact_string in mem.exact_strings
            or query.target_exact_string in mem.text
        ):
            return 0.05
        if query.target_symbol and query.target_symbol in mem.symbols:
            return 0.05
        return 0.0


@dataclass
class MenhirLiveRetriever:
    """Live seam: rank via menhir ``recall(trace=True)`` under a tuning config.

    ``recall_service`` must already be wired to a seeded (throwaway) graph. Each
    instance pins one ``RetrievalTuningConfig`` (a ladder condition). The returned
    ``ranked_ids`` are graph node uuids; ``trace`` is the serialized R0
    ``RetrievalTrace``. Map uuids back to fixture support ids upstream.
    """

    recall_service: "RecallService"
    tuning: Any  # menhir RetrievalTuningConfig (imported lazily by the caller)
    group_ids: list[str] | None = None
    candidate_k: int = 50
    uuid_to_id: dict[str, str] | None = None  # graph node uuid -> fixture memory id
    name: str = "menhir_live"

    def rank(self, query: R1Query, k: int) -> RankResult:
        import asyncio

        namespace = self.group_ids[0] if self.group_ids else None
        start = time.perf_counter()
        result = asyncio.run(
            self.recall_service.recall(
                query.text,
                limit=self.candidate_k,  # full ranking; metrics slice top-k after id-mapping
                candidate_k=self.candidate_k,
                namespace=namespace,
                tuning=self.tuning,
                trace=True,
            )
        )
        latency_ms = (time.perf_counter() - start) * 1000.0
        ranked = self._to_fixture_ids([r.uuid for r in result.results])
        return RankResult(ranked_ids=ranked, latency_ms=latency_ms, trace=_trace_to_dict(result.trace))

    def _to_fixture_ids(self, uuids: list[str]) -> list[str]:
        """Map graph node uuids -> fixture memory ids (dedup, preserve order).

        When no grounding map is set, return the raw uuids unchanged. Unmapped
        uuids are dropped (a retrieved node with no fixture provenance is not a
        gold support candidate).
        """
        if self.uuid_to_id is None:
            return uuids
        out: list[str] = []
        seen: set[str] = set()
        for u in uuids:
            mid = self.uuid_to_id.get(u)
            if mid is not None and mid not in seen:
                seen.add(mid)
                out.append(mid)
        return out


def _trace_to_dict(trace: Any) -> dict[str, Any] | None:
    """Serialize a menhir RetrievalTrace to JSON-able dict (enum -> value)."""
    if trace is None:
        return None
    return {
        "query": trace.query,
        "preset": trace.preset,
        "total_ms": trace.total_ms,
        "phases": dict(trace.phases),
        "candidates": [
            {
                "uuid": c.uuid,
                "source": getattr(c.source, "value", c.source),
                "similarity": c.similarity,
                "survived_floor": c.survived_floor,
                "final_score": c.final_score,
                "rank": c.rank,
            }
            for c in trace.candidates
        ],
    }
