"""Honest baselines for the facet ladder: BM25, embedding seam, fusion, file-context.

These are the conditions facet retrieval has to *beat* (or at least not regress)
to graduate. Two are fully offline and deterministic (BM25, file-context). The
"embedding" condition is a pluggable seam: the default here is a deterministic
lexical stand-in so the ladder runs offline and in CI, but it is **not** a real
embedding model. Plug a real embedder at home via the `EmbeddingScorer` protocol
before quoting condition B/C/E as an embedding comparison.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Protocol, runtime_checkable

from .models import Memory

_TOKEN_RE = re.compile(r"[a-z0-9_]+")


def tokenize(text: str) -> list[str]:
    """Lowercase word/identifier tokenization shared by all lexical baselines."""
    return _TOKEN_RE.findall(text.lower())


@runtime_checkable
class EmbeddingScorer(Protocol):
    """Seam for a real embedding model. Returns {memory_id: similarity}."""

    def score(self, query_text: str, memories: list[Memory]) -> dict[str, float]:
        ...


class BM25:
    """Classic Okapi BM25 over memory text (k1=1.5, b=0.75 by default)."""

    def __init__(self, memories: list[Memory], k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self.memories = memories
        self.doc_tokens: dict[str, list[str]] = {m.id: tokenize(m.text) for m in memories}
        self.doc_len: dict[str, int] = {mid: len(toks) for mid, toks in self.doc_tokens.items()}
        self.avg_len = (sum(self.doc_len.values()) / len(self.doc_len)) if self.doc_len else 0.0
        self.doc_freq: Counter[str] = Counter()
        for toks in self.doc_tokens.values():
            self.doc_freq.update(set(toks))
        self.n_docs = len(memories)

    def _idf(self, term: str) -> float:
        df = self.doc_freq.get(term, 0)
        # BM25+ style non-negative idf floor avoids negative weights for very
        # common terms flipping the ranking.
        return math.log(1 + (self.n_docs - df + 0.5) / (df + 0.5))

    def score(self, query_text: str, memories: list[Memory] | None = None) -> dict[str, float]:
        query_terms = tokenize(query_text)
        scores: dict[str, float] = {}
        for mid, toks in self.doc_tokens.items():
            tf = Counter(toks)
            length = self.doc_len[mid]
            denom_norm = self.k1 * (1 - self.b + self.b * (length / self.avg_len if self.avg_len else 0))
            total = 0.0
            for term in query_terms:
                freq = tf.get(term, 0)
                if not freq:
                    continue
                total += self._idf(term) * (freq * (self.k1 + 1)) / (freq + denom_norm)
            scores[mid] = total
        return scores


class LexicalEmbeddingStub:
    """Deterministic offline stand-in for an embedding model.

    Cosine similarity over term-frequency vectors. This is **not** a real
    embedding — it has no semantics beyond shared tokens — but it gives the
    ladder a runnable, deterministic condition B/E until a real `EmbeddingScorer`
    is injected. Treated as a baseline seam, clearly labeled in run artifacts.
    """

    name = "lexical-embedding-stub"

    def score(self, query_text: str, memories: list[Memory]) -> dict[str, float]:
        q_vec = Counter(tokenize(query_text))
        q_norm = math.sqrt(sum(v * v for v in q_vec.values())) or 1.0
        scores: dict[str, float] = {}
        for memory in memories:
            d_vec = Counter(tokenize(memory.text))
            d_norm = math.sqrt(sum(v * v for v in d_vec.values())) or 1.0
            dot = sum(q_vec[t] * d_vec[t] for t in q_vec.keys() & d_vec.keys())
            scores[memory.id] = dot / (q_norm * d_norm)
        return scores


def rank_from_scores(scores: dict[str, float]) -> list[str]:
    """Rank memory ids by (descending score, id) — stable and deterministic.

    Zero-score documents are dropped: an empty BM25/embedding score means the
    query shares nothing with the document, which is a non-match, not rank-N.
    """
    ranked = [(mid, s) for mid, s in scores.items() if s > 0.0]
    ranked.sort(key=lambda item: (-item[1], item[0]))
    return [mid for mid, _ in ranked]


def rrf_fuse(rank_lists: list[list[str]], k: int = 60) -> list[str]:
    """Reciprocal-rank fusion of several ranked id lists (rank, not raw score).

    Mirrors the rationale of menhir R1's `weighted_rrf`: fuse on rank to avoid the
    BM25/cosine scale mismatch. Returns a single ranked list, (−rrf, id) ordered.
    """
    fused: dict[str, float] = {}
    for ranking in rank_lists:
        for position, memory_id in enumerate(ranking, start=1):
            fused[memory_id] = fused.get(memory_id, 0.0) + 1.0 / (k + position)
    return [mid for mid, _ in sorted(fused.items(), key=lambda item: (-item[1], item[0]))]


def file_context_rank(query, memories: list[Memory]) -> list[str]:
    """Stand-in for menhir's existing graph/file-context recall (condition D).

    Ranks memories by how many file/symbol/test values they share with the query,
    a deterministic proxy for "candidates reachable through the file/structure
    graph." Labeled as a stand-in: it is not the live menhir graph retriever.
    """
    qf = query.facets
    q_struct = qf.values("file") | qf.values("symbol") | qf.values("test")
    if not q_struct:
        return []
    overlap: dict[str, int] = {}
    for memory in memories:
        mf = memory.facets
        m_struct = mf.values("file") | mf.values("symbol") | mf.values("test")
        shared = len(q_struct & m_struct)
        if shared:
            overlap[memory.id] = shared
    return [mid for mid, _ in sorted(overlap.items(), key=lambda item: (-item[1], item[0]))]
