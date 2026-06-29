"""Real embedding `SemanticScorer` for the intent bench (LM Studio / OpenAI-compatible).

Swaps the lexical stand-in for a real embedding model so the IntentOracle ladder can be
re-confirmed with genuine semantic similarity (the bench's gating discipline: the
lexical run is a harness sanity check, not a promotion decision).

Talks to an OpenAI-compatible `/v1/embeddings` endpoint (LM Studio on :1234 by default;
override via `INTENT_EMBED_BASE_URL` / `INTENT_EMBED_MODEL`). Uses the nomic-embed
`search_query:` / `search_document:` task prefixes and caches each unique text. Cosine of
the (model-normalized) vectors, clamped to [0, 1].

Stdlib-only HTTP (urllib) — no new dependency. Fails loudly if the endpoint is
unreachable rather than silently falling back to lexical (per the no-silent-fallback rule).
"""

from __future__ import annotations

import json
import math
import os
import urllib.error
import urllib.request

DEFAULT_BASE_URL = os.environ.get("INTENT_EMBED_BASE_URL", "http://localhost:1234/v1")
DEFAULT_MODEL = os.environ.get("INTENT_EMBED_MODEL", "text-embedding-nomic-embed-text-v1.5")


class EmbedderUnavailable(RuntimeError):
    """Raised when the embedding endpoint cannot be reached — never fall back silently."""


class LMStudioEmbeddingScorer:
    """Cosine similarity from a real embedding model over an OpenAI-compatible endpoint."""

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        model: str = DEFAULT_MODEL,
        timeout: float = 30.0,
        use_nomic_prefixes: bool = True,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.use_nomic_prefixes = use_nomic_prefixes
        self._cache: dict[str, list[float]] = {}

    @property
    def name(self) -> str:
        return f"lmstudio:{self.model}"

    def _prefix(self, text: str, *, is_query: bool) -> str:
        if not self.use_nomic_prefixes:
            return text
        return f"{'search_query' if is_query else 'search_document'}: {text}"

    def _embed(self, text: str) -> list[float]:
        if text in self._cache:
            return self._cache[text]
        payload = json.dumps({"input": text, "model": self.model}).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/embeddings", data=payload,
            headers={"Content-Type": "application/json"}, method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            raise EmbedderUnavailable(f"embedding endpoint {self.base_url} unreachable: {exc}") from exc
        vec = data.get("data", [{}])[0].get("embedding")
        if not vec:
            raise EmbedderUnavailable(f"embedding endpoint returned no vector for model {self.model!r}")
        self._cache[text] = vec
        return vec

    @staticmethod
    def _cosine(a: list[float], b: list[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a))
        nb = math.sqrt(sum(y * y for y in b))
        if na == 0 or nb == 0:
            return 0.0
        return dot / (na * nb)

    def similarity(self, query_text: str, candidate_text: str) -> float:
        q = self._embed(self._prefix(query_text, is_query=True))
        c = self._embed(self._prefix(candidate_text, is_query=False))
        return max(0.0, min(1.0, self._cosine(q, c)))
