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

OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_MODEL = os.environ.get("OPENAI_EMBED_MODEL", "text-embedding-3-small")


class EmbedderUnavailable(RuntimeError):
    """Raised when the embedding endpoint cannot be reached — never fall back silently."""


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _post_embeddings(url: str, payload: dict, headers: dict, timeout: float) -> list[float]:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json", **headers}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:200] if hasattr(exc, "read") else ""
        if exc.code == 429:
            raise EmbedderUnavailable(f"RATE LIMITED (429) at {url}: {detail}") from exc
        raise EmbedderUnavailable(f"HTTP {exc.code} at {url}: {detail}") from exc
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        raise EmbedderUnavailable(f"embedding endpoint {url} unreachable: {exc}") from exc
    vec = data.get("data", [{}])[0].get("embedding")
    if not vec:
        raise EmbedderUnavailable(f"embedding endpoint {url} returned no vector")
    return vec


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
        if text not in self._cache:
            self._cache[text] = _post_embeddings(
                f"{self.base_url}/embeddings", {"input": text, "model": self.model}, {}, self.timeout
            )
        return self._cache[text]

    def similarity(self, query_text: str, candidate_text: str) -> float:
        q = self._embed(self._prefix(query_text, is_query=True))
        c = self._embed(self._prefix(candidate_text, is_query=False))
        return max(0.0, min(1.0, _cosine(q, c)))


class OpenAIEmbeddingScorer:
    """Cosine similarity from the OpenAI embeddings API (text-embedding-3-small by default).

    Reads the key from `OPENAI_API_KEY` (never hard-coded). No task prefixes (OpenAI models
    do not use them). Caches each unique text; embeddings are cheap (~4 tokens/short input)
    but a 429 is surfaced as EmbedderUnavailable, never silently retried."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = OPENAI_MODEL,
        base_url: str = OPENAI_BASE_URL,
        timeout: float = 30.0,
    ) -> None:
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._cache: dict[str, list[float]] = {}

    @property
    def name(self) -> str:
        return f"openai:{self.model}"

    def _embed(self, text: str) -> list[float]:
        if not self.api_key:
            raise EmbedderUnavailable("OPENAI_API_KEY is not set")
        if text not in self._cache:
            self._cache[text] = _post_embeddings(
                f"{self.base_url}/embeddings", {"input": text, "model": self.model},
                {"Authorization": f"Bearer {self.api_key}"}, self.timeout,
            )
        return self._cache[text]

    def similarity(self, query_text: str, candidate_text: str) -> float:
        return max(0.0, min(1.0, _cosine(self._embed(query_text), self._embed(candidate_text))))
