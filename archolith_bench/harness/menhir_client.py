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

    def ingest(
        self,
        group_id: str,
        role: str,
        content: str,
        *,
        occurred_at: str | None = None,
        session_id: str | None = None,
        source: str | None = None,
        wait: bool = True,
    ) -> None:
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

        def score_snippet(indexed_snippet: tuple[int, str]) -> tuple[int, int]:
            """Return (negative overlap count, insertion index) for sorting."""
            index, snippet = indexed_snippet
            snippet_tokens = set(snippet.lower().split())
            overlap = len(query_tokens & snippet_tokens)
            return (-overlap, index)

        ranked = sorted(enumerate(snippets), key=score_snippet)
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
        ingest_path: str = "/api/memory",
        recall_path: str = "/api/recall",
        timeout: float = 180.0,
    ) -> None:
        """
        Initialize HTTP client against a real menhir instance.

        A benchmark "group_id" maps to a menhir namespace (silo). Memory is ingested
        with ``wait=true`` so enrichment completes before recall; teardown uses
        ``DELETE /api/namespace/{namespace}``.

        Args:
            base_url: Root URL of the menhir instance.
            api_key: Optional Bearer token (menhir MENHIR_API_KEY) for authorization.
            ingest_path: Episode ingest endpoint (default "/api/memory").
            recall_path: Recall endpoint (default "/api/recall").
            timeout: Request timeout in seconds.
        """
        self._base_url = base_url
        self._ingest_path = ingest_path
        self._recall_path = recall_path
        self._client = httpx.Client(timeout=timeout)
        self._headers: dict[str, str] = {}
        if api_key:
            self._headers["Authorization"] = f"Bearer {api_key}"

    def __enter__(self):
        """Return this client for context-manager use."""
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
        """Close the underlying HTTP client on context-manager exit."""
        self.close()

    def new_group(self) -> str:
        """Return a fresh isolated namespace id."""
        return uuid.uuid4().hex

    def ingest(
        self,
        group_id: str,
        role: str,
        content: str,
        *,
        occurred_at: str | None = None,
        session_id: str | None = None,
        source: str | None = None,
        wait: bool = True,
    ) -> None:
        """Ingest a snippet as a menhir episode in the group's namespace silo.

        ``source`` sets the episode provenance label menhir maps to an evidence kind
        (domain/truth/kinds.py). A user's own utterance is external testimony, so pass
        ``source="user"`` for user turns — that becomes a Guard-5 external anchor, so the
        EvidenceAnchorWarden admits facts the user stated. Omit (default "remote-api" ->
        agent_inference) for assistant/system turns, which are not anchors.

        By default uses ``wait=true`` so the episode is fully enriched before
        the call returns (back-compat for Mode-B per-item driver). Pass
        ``wait=False`` for throughput-optimised bulk ingest where a separate
        drain step provides the completeness guarantee.

        ``occurred_at`` (ISO-8601) backdates the episode's Graphiti
        ``reference_time`` so temporal-KG edges reflect historical event dates
        rather than ingestion time.  ``session_id`` pins all turns of one LME
        haystack session to the same menhir session silo.
        """
        if not content:
            return
        url = self._base_url.rstrip("/") + self._ingest_path
        payload: dict = {"episode": f"{role}: {content}", "namespace": group_id}
        if source is not None:
            payload["source"] = source
        if occurred_at is not None:
            payload["occurred_at"] = occurred_at
        if session_id is not None:
            payload["session_id"] = session_id
        response = self._client.post(
            url,
            params={"wait": "true" if wait else "false"},
            json=payload,
            headers=self._headers,
        )
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
        # include_session=True: benchmark memories are freshly ingested and live at
        # SESSION scope (promotion to PERSISTENT only happens via the scheduler, which
        # is off under MENHIR_BENCHMARK_MODE). Without this the HTTP recall filters them
        # all out. Matches the menhir MCP recall tools, which always pass include_session=True.
        payload = {
            "query": query,
            "limit": limit,
            "namespace": group_id,
            "include_session": True,
        }
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

        # Extract snippet strings from items. menhir's RecallResponse items carry
        # both "name" (entity name / fact) and an optional "content" (which is often
        # None), so prefer content but fall back to name/fact and skip empty values
        # -- otherwise recalled memory silently collapses to an empty context.
        snippets: list[str] = []
        for item in items:
            if isinstance(item, str):
                if item.strip():
                    snippets.append(item)
            elif isinstance(item, dict):
                name = item.get("name") if isinstance(item.get("name"), str) else ""
                body = next(
                    (
                        item[k]
                        for k in ("content", "text", "summary", "fact")
                        if isinstance(item.get(k), str) and item[k].strip()
                    ),
                    "",
                )
                if name and body and name.strip() != body.strip():
                    snippets.append(f"{name.strip()}: {body.strip()}")
                elif body.strip():
                    snippets.append(body.strip())
                elif name.strip():
                    snippets.append(name.strip())

        return snippets

    def reset(self, group_id: str) -> None:
        """Best-effort silo teardown via DELETE /api/namespace/{namespace}.

        Swallows any exception (menhir refuses the default namespace with 400).
        """
        try:
            url = self._base_url.rstrip("/") + "/api/namespace/" + group_id
            response = self._client.delete(url, headers=self._headers)
            response.raise_for_status()
        except Exception:
            pass

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._client.close()
