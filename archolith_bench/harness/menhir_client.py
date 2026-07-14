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
        flagged: bool = False,
        bootstrap_scope: str | None = None,
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
        flagged: bool = False,
        bootstrap_scope: str | None = None,
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
        if flagged:
            payload["flagged"] = True
        if bootstrap_scope is not None:
            payload["bootstrap_scope"] = bootstrap_scope
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

    def recall_raw(self, group_id: str, query: str, limit: int = 10) -> dict[str, Any]:
        """Return the unmodified HTTP recall response for benchmark assertions."""
        url = self._base_url.rstrip("/") + self._recall_path
        response = self._client.post(
            url,
            json={
                "query": query,
                "limit": limit,
                "namespace": group_id,
                "include_session": True,
            },
            headers=self._headers,
        )
        response.raise_for_status()
        data = response.json()
        return data if isinstance(data, dict) else {"results": data}

    def bootstrap_flagged(
        self, reader_id: str, workspace: str, limit: int = 50
    ) -> dict[str, Any]:
        """Read scoped bootstrap pins and establish the matching receipt."""
        url = self._base_url.rstrip("/") + "/api/bootstrap/flagged"
        response = self._client.get(
            url,
            params={"reader_id": reader_id, "workspace": workspace, "limit": limit},
            headers=self._headers,
        )
        response.raise_for_status()
        return response.json()

    def bootstrap_context(
        self, reader_id: str, workspace: str, namespace: str, recent_limit: int = 50
    ) -> dict[str, Any]:
        """Read recent context using the receipt established for this workspace."""
        url = self._base_url.rstrip("/") + "/api/bootstrap/context"
        response = self._client.post(
            url,
            json={
                "reader_id": reader_id,
                "workspace": workspace,
                "namespace": namespace,
                "recent_limit": recent_limit,
            },
            headers=self._headers,
        )
        response.raise_for_status()
        return response.json()

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


class Phase3MenhirClient(HttpMenhirClient):
    """HTTP client for the Phase 3 (personal-memory View consolidation) black-box surface.

    Exercises the SELECTIVE-capture pipeline end to end against a THROWAWAY menhir:
    post `:TurnEvidence` (not `/api/memory` episodes), trigger consolidation, then inspect
    Views / abstention receipts / supersession — without importing menhir or issuing Cypher.
    Uses the endpoints added in menhir's routes.py:

        POST /api/turn-evidence     capture one candidate user turn
        POST /api/phase3/run        run one consolidation pass over a namespace
        GET  /api/phase3/status     dirty flag + turn-evidence count
        GET  /api/views             current counter Views (+ history) and abstention receipts
        POST /api/phase3/reset      tear down the namespace (partition + TurnEvidence)
    """

    def post_turn_evidence(
        self,
        namespace: str,
        text: str,
        *,
        role: str = "user",
        declarant: str = "user",
        session_id: str | None = None,
        source_kind: str = "archolith-bench-phase3",
        source_client: str | None = "archolith_bench",
        hook_version: str | None = "menhir-phase3-bench-v1",
        triage_reason: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        turn_key: str | None = None,
    ) -> dict[str, Any]:
        """Capture one candidate user turn as `:TurnEvidence`.

        `declarant="user"` is required for Phase 3 to consider the turn — the dirty query and
        the user-evidence loader both filter `role='user' AND declarant='user'`. Returns the
        raw response ``{turn_id, created, recorded_at}``.

        `source_client`/`hook_version` are additive provenance labels the menhir route accepts
        (older menhir builds simply ignore unknown body fields). They identify the benchmark as the
        producer of these throwaway evidence rows.
        """
        url = self._base_url.rstrip("/") + "/api/turn-evidence"
        payload: dict[str, Any] = {
            "text": text,
            "role": role,
            "declarant": declarant,
            "namespace": namespace,
            "source_kind": source_kind,
        }
        if source_client is not None:
            payload["source_client"] = source_client
        if hook_version is not None:
            payload["hook_version"] = hook_version
        if session_id is not None:
            payload["session_id"] = session_id
        if triage_reason is not None:
            payload["triage_reason"] = list(triage_reason)
        if metadata is not None:
            payload["metadata"] = metadata
        if turn_key is not None:
            payload["turn_key"] = turn_key
        response = self._client.post(url, json=payload, headers=self._headers)
        response.raise_for_status()
        return response.json()

    def run_phase3(
        self, namespace: str, *, k: int = 3, source: str = "perception"
    ) -> dict[str, Any]:
        """Run one consolidation pass over ``namespace`` and return its metrics dict."""
        url = self._base_url.rstrip("/") + "/api/phase3/run"
        response = self._client.post(
            url, json={"namespace": namespace, "k": k, "source": source}, headers=self._headers
        )
        response.raise_for_status()
        return response.json()

    def phase3_status(self, namespace: str) -> dict[str, Any]:
        """Return ``{namespace, dirty, turn_evidence}`` for the namespace."""
        url = self._base_url.rstrip("/") + "/api/phase3/status"
        response = self._client.get(
            url, params={"namespace": namespace}, headers=self._headers
        )
        response.raise_for_status()
        return response.json()

    def fetch_views(self, namespace: str, *, limit: int = 100) -> dict[str, Any]:
        """Return ``{namespace, count, views, receipts}`` — current counter Views (each with
        ``history`` and ``superseded``) plus ``subject='perception'`` abstention receipts."""
        url = self._base_url.rstrip("/") + "/api/views"
        response = self._client.get(
            url, params={"namespace": namespace, "limit": limit}, headers=self._headers
        )
        response.raise_for_status()
        return response.json()

    def reset_phase3(self, namespace: str) -> dict[str, Any]:
        """Full teardown: graphiti partition (Views + watermark) and namespace-keyed TurnEvidence.

        Returns ``{namespace, nodes_deleted, turn_evidence_deleted}``. Best-effort: a first-run
        teardown of a fresh namespace may 400/404, which is fine.
        """
        url = self._base_url.rstrip("/") + "/api/phase3/reset"
        try:
            response = self._client.post(
                url, params={"namespace": namespace}, headers=self._headers
            )
            response.raise_for_status()
            return response.json()
        except Exception:
            return {"namespace": namespace, "nodes_deleted": 0, "turn_evidence_deleted": 0}


class StubPhase3Client:
    """Deterministic in-memory Phase 3 backend — a NETWORK-FREE stand-in for CI smoke.

    Models the HAPPY menhir consumer (F1 semantic-family voting + F2 unique-target corrections)
    so the whole driver + scenario suite + report path runs without a live menhir or Neo4j. It
    is NOT a substitute for the live benchmark (it cannot reveal server-side extraction defects
    or the fold-SUM stochasticity) — it exists so `--offline` smoke can guard the harness itself.

    Per-namespace it tracks posted prompts + a dirty/watermark bit, then batch-re-folds every
    prompt into counter Views on each `fetch_views` (idempotent). Corrections bind to the UNIQUE
    value-matching View, abstaining when >1 matches. Recognizes the exact fixture prompt strings.
    """

    def __init__(self) -> None:
        """Initialize empty per-namespace post + dirty state."""
        self._posts: dict[str, list[str]] = {}
        self._dirty: dict[str, bool] = {}

    def new_group(self) -> str:
        """Return a fresh isolated namespace id."""
        return uuid.uuid4().hex

    def reset_phase3(self, namespace: str) -> dict[str, Any]:
        """Drop all state for the namespace."""
        n = len(self._posts.get(namespace, []))
        self._posts.pop(namespace, None)
        self._dirty.pop(namespace, None)
        return {"namespace": namespace, "nodes_deleted": n, "turn_evidence_deleted": n}

    def post_turn_evidence(self, namespace: str, text: str, *, role: str = "user",
                           declarant: str = "user", triage_reason=None, turn_key=None,
                           **_: Any) -> dict[str, Any]:
        """Record a candidate turn and mark the namespace dirty (new evidence to consolidate)."""
        self._posts.setdefault(namespace, []).append(text)
        self._dirty[namespace] = True
        return {"turn_id": uuid.uuid4().hex, "created": True, "recorded_at": "stub"}

    def phase3_status(self, namespace: str) -> dict[str, Any]:
        """Report the dirty bit + evidence count."""
        return {
            "namespace": namespace,
            "dirty": bool(self._dirty.get(namespace)),
            "turn_evidence": len(self._posts.get(namespace, [])),
        }

    def run_phase3(self, namespace: str, *, k: int = 3, source: str = "perception") -> dict[str, Any]:
        """Consolidate: clear the dirty bit (watermark debounce) and report derived counts."""
        selected = bool(self._dirty.get(namespace))
        self._dirty[namespace] = False
        views = self._build_views(namespace)
        return {
            "namespace": namespace,
            "phase3_selected": selected,
            "dirty_after": False,
            "namespaces_dirty": 1 if selected else 0,
            "namespaces_processed": 1,
            "views_written": len(views),
            "abstained": 0,
            "corrections_applied": self._corrections_applied(namespace),
            "llm_calls": 0,
        }

    def fetch_views(self, namespace: str, *, limit: int = 100) -> dict[str, Any]:
        """Return current counter Views (batch re-fold; idempotent) + empty receipts."""
        views = self._build_views(namespace)
        return {"namespace": namespace, "count": len(views), "views": views, "receipts": []}

    def recall(self, namespace: str, query: str, limit: int = 10) -> list[str]:
        """Return one snippet per current View (so recall_after > recall_before once Views exist)."""
        return [f"{v['subject']} {v['counter']} {v['value']}" for v in self._build_views(namespace)]

    def close(self) -> None:
        """No-op (in-memory)."""

    # ---- deterministic consolidation model ---------------------------------------------------

    def _measures(self, prompt: str) -> list[tuple[str, str, float]]:
        """(subject, counter, value) a prompt yields — matches the core + scenario fixture strings."""
        p = prompt.lower()
        if "movies" in p and "watch list" in p:
            return [("movies", "movies_watchlist", 25.0)]
        if "books" in p and "this year" in p:
            return [("books", "books_read", 25.0)]
        if "50 dollars and 75 dollars" in p:
            return [("bike", "bike_spend", 125.0)]
        if "one bike for $50" in p:
            return [("bike", "bike_spend", 125.0)]
        if "2 bikes for $125" in p:  # count and SUM do not merge (reducer is identity)
            return [("bike", "bikes_count", 2.0), ("bike", "bike_spend", 125.0)]
        return []

    def _correction(self, prompt: str) -> tuple[float, float] | None:
        p = prompt.lower()
        # mirrors menhir's correction_resolver connectives (the happy consumer): the "X, not Y" and
        # "not X anymore, it is Y" forms, plus the consumer-quality-pack additions (arrow "X -> Y" and
        # reverse "to Y from X"). Value-match against an existing View is still the real target guard.
        if "20, not 25" in p or "not 25 anymore, it is 20" in p:
            return (25.0, 20.0)
        if "25 -> 20" in p or "25 --> 20" in p or "to 20 from 25" in p:
            return (25.0, 20.0)
        return None

    def _fold(self, namespace: str) -> tuple[dict[str, dict], int]:
        views: dict[str, dict] = {}
        corrections: list[tuple[float, float]] = []
        for prompt in self._posts.get(namespace, []):
            for subject, counter, value in self._measures(prompt):
                views[counter] = {"subject": subject, "counter": counter, "value": value,
                                  "current": True, "history": [], "superseded": []}
            corr = self._correction(prompt)
            if corr:
                corrections.append(corr)
        applied = 0
        for old, new in corrections:
            matches = [v for v in views.values() if v["value"] == old]
            if len(matches) == 1:  # unique target -> supersede; else abstain
                v = matches[0]
                v["superseded"] = [{"value": old, "current": False,
                                    "valid_at": "t1", "expired_at": "t2"}]
                v["value"] = new
                applied += 1
        return views, applied

    def _build_views(self, namespace: str) -> list[dict[str, Any]]:
        return list(self._fold(namespace)[0].values())

    def _corrections_applied(self, namespace: str) -> int:
        return self._fold(namespace)[1]
