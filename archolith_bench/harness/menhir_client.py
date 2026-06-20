"""
Menhir memory client implementations for Mode-B benchmark driver.

StubMenhirClient: deterministic in-memory backend for offline/deterministic tests.
HttpMenhirClient: HTTP client scaffolded for a real throwaway menhir instance.
"""

from __future__ import annotations

import uuid
from typing import Any

import httpx


class StubMenhirClient:
    """In-memory menhir stub for offline, deterministic testing."""

    def __init__(self) -> None:
        """Initialize empty group storage."""
        self._groups: dict[str, list[str]] = {}

    def new_group(self) -> str:
        """Return a fresh isolated namespace id."""
        return uuid.uuid4().hex

    def ingest(self, group_id: str, role: str, content: str) -> None:
        """Append a formatted snippet to the group's list."""
        if not content:
            return
        if group_id not in self._groups:
            self._groups[group_id] = []
        self._groups[group_id].append(f"{role}: {content}")

    def recall(
        self, group_id: str, query: str, limit: int = 10
    ) -> list[str]:
        """
        Return up to `limit` snippets for the group, ranked by word-token overlap.

        Snippets sharing the most lowercased word-tokens with the query come first
        (ties broken by insertion order), followed by remaining snippets in insertion order.
        If the group is unknown, return [].
        """
        if group_id not in self._groups:
            return []

        snippets = self._groups[group_id]
        query_tokens = set(query.lower().split())

        def score_snippet(snippet: str) -> tuple[int, int]:
            """Return (negative overlap count, insertion index) for sorting."""
            snippet_tokens = set(snippet.lower().split())
            overlap = len(query_tokens & snippet_tokens)
            return (-overlap, snippets.index(snippet))

        ranked = sorted(enumerate(snippets), key=lambda x: score_snippet(x[1]))
        return [snippet for _, snippet in ranked[:limit]]

    def reset(self, group_id: str) -> None:
        """Delete the group's entry if present."""
        self._groups.pop(group_id, None)


class HttpMenhirClient:
    """HTTP client for a real menhir instance (OpenAI-compatible style)."""

    def __init__(
        self,
        base_url: str,
        *,
        api_key: str = "",
        ingest_path: str = "/ingest",
        recall_path: str = "/recall",
        timeout: float = 60.0,
    ) -> None:
        """
        Initialize HTTP client with configurable paths and auth.

        Args:
            base_url: Root URL of the menhir instance.
            api_key: Optional Bearer token for authorization.
            ingest_path: Endpoint path for ingestion (default "/ingest").
            recall_path: Endpoint path for recall (default "/recall").
            timeout: Request timeout in seconds.
        """
        self._base_url = base_url
        self._ingest_path = ingest_path
        self._recall_path = recall_path
        self._client = httpx.Client(timeout=timeout)
        self._headers: dict[str, str] = {}
        if api_key:
            self._headers["Authorization"] = f"Bearer {api_key}"

    def new_group(self) -> str:
        """Return a fresh isolated namespace id."""
        return uuid.uuid4().hex

    def ingest(self, group_id: str, role: str, content: str) -> None:
        """POST a snippet to the ingest endpoint."""
        url = self._base_url.rstrip("/") + self._ingest_path
        payload = {"group_id": group_id, "role": role, "content": content}
        response = self._client.post(url, json=payload, headers=self._headers)
        response.raise_for_status()

    def recall(
        self, group_id: str, query: str, limit: int = 10
    ) -> list[str]:
        """
        POST a query to the recall endpoint and extract snippets.

        Tolerant of response shape: accepts top-level list or dict with
        "results"/"memories"/"snippets" key. Each element may be a string or
        dict with "text"/"content"/"summary" key.
        """
        url = self._base_url.rstrip("/") + self._recall_path
        payload = {"group_id": group_id, "query": query, "limit": limit}
        response = self._client.post(url, json=payload, headers=self._headers)
        response.raise_for_status()
        data = response.json()

        # Extract list of items (top-level list or nested in a known key)
        items: list[Any] = []
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            for key in ("results", "memories", "snippets"):
                if key in data and isinstance(data[key], list):
                    items = data[key]
                    break

        # Extract snippet strings from items
        snippets: list[str] = []
        for item in items:
            if isinstance(item, str):
                snippets.append(item)
            elif isinstance(item, dict):
                for key in ("text", "content", "summary"):
                    if key in item and isinstance(item[key], str):
                        snippets.append(item[key])
                        break

        return snippets

    def reset(self, group_id: str) -> None:
        """Best-effort reset; swallow any exception."""
        try:
            url = self._base_url.rstrip("/") + "/reset"
            payload = {"group_id": group_id}
            response = self._client.post(url, json=payload, headers=self._headers)
            response.raise_for_status()
        except Exception:
            pass

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._client.close()
