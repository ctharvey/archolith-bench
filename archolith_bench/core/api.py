"""HTTP API helpers for communicating with the archolith proxy and upstream."""

from __future__ import annotations

import json
import os
import time

import httpx
from dotenv import load_dotenv

load_dotenv()

_proxy_port = os.getenv("PROXY_PORT", "9800")
PROXY_URL = os.getenv("PROXY_URL", f"http://localhost:{_proxy_port}/v1")
DIRECT_URL = os.getenv("UPSTREAM_BASE_URL", "https://api.openai.com/v1")
API_KEY = os.getenv("UPSTREAM_API_KEY", "")
MODEL = os.getenv("BENCHMARK_MODEL", "gpt-4o-mini")


def send_chat(
    client: httpx.Client,
    base_url: str,
    api_key: str,
    messages: list[dict],
    model: str,
    max_retries: int = 5,
    session_id: str | None = None,
    session_config: dict | None = None,
) -> tuple[str, float, dict]:
    """Send a chat completion request. Returns (response_text, latency_ms, usage_dict).

    Retries on 429 (rate limit) with exponential backoff.

    When session_id is provided it is sent as the X-Session-ID header so the proxy
    pins this conversation to a known session id (which the trace query then reads
    directly, instead of guessing sessions[0]).

    When session_config is provided it is sent as the X-Session-Config header (JSON
    object) so the proxy scopes those config overrides to this session only, without
    mutating global config. The proxy merges + persists it on the session, so it is
    safe (idempotent) to send on every turn.
    """
    url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if session_id:
        headers["X-Session-ID"] = session_id
    if session_config:
        headers["X-Session-Config"] = json.dumps(session_config)
    body = {
        "model": model,
        "messages": messages,
        "max_tokens": 2048,
        "temperature": 0.3,
    }
    # deepseek-v4-flash "thinks" by default (~2.3x latency, ~3x output tokens). The
    # benchmark answers do not need chain-of-thought, so disable it for deepseek
    # targets. This is the ONLY accepted disable form for the DeepSeek API
    # (boolean / enable_thinking / reasoning_effort are rejected or ignored).
    if "deepseek" in (base_url or "").lower() or "deepseek" in (model or "").lower():
        body["thinking"] = {"type": "disabled"}

    total_start = time.monotonic()
    for attempt in range(max_retries + 1):
        try:
            resp = client.post(url, json=body, headers=headers, timeout=300)
        except httpx.TimeoutException:
            latency_ms = (time.monotonic() - total_start) * 1000
            return f"[TIMEOUT after {latency_ms/1000:.0f}s]", latency_ms, {}
        except httpx.HTTPError as e:
            latency_ms = (time.monotonic() - total_start) * 1000
            return f"[HTTP ERROR]: {e}", latency_ms, {}

        if resp.status_code == 429 and attempt < max_retries:
            retry_after = resp.headers.get("Retry-After") or resp.headers.get("retry-after")
            if retry_after:
                try:
                    wait = int(retry_after)
                except ValueError:
                    wait = 2 ** attempt * 10
            else:
                wait = 2 ** attempt * 10
            wait = min(wait, 300)
            print(f"  [429] Rate limited, waiting {wait}s before retry {attempt + 1}/{max_retries}...")
            time.sleep(wait)
            continue

        break

    latency_ms = (time.monotonic() - total_start) * 1000

    if resp.status_code != 200:
        return f"[ERROR {resp.status_code}]: {resp.text[:300]}", latency_ms, {}

    data = resp.json()
    text = data.get("choices", [{}])[0].get("message", {}).get("content", "") or ""
    usage = data.get("usage", {})
    return text, latency_ms, usage


def _proxy_base(proxy_url: str) -> str:
    return proxy_url.rstrip("/").removesuffix("/v1")


def get_proxy_trace(client: httpx.Client, proxy_url: str, session_id: str | None = None) -> dict:
    base = _proxy_base(proxy_url)
    # A session_id is REQUIRED. The old sessions[0] fallback read whatever session
    # happened to be first in the proxy's store (often a stale/unrelated run), which
    # silently reported the wrong session's assembly_mode/savings. Fail loudly instead.
    if not session_id:
        return {"error": "get_proxy_trace requires an explicit session_id (no sessions[0] fallback)"}
    try:
        resp2 = client.get(f"{base}/trace/sessions/{session_id}", timeout=10)
        if resp2.status_code != 200:
            return {"error": f"trace session detail {resp2.status_code}"}
        return resp2.json()
    except Exception as e:
        return {"error": str(e)}


def set_proxy_budget(
    client: httpx.Client, proxy_url: str, budget: int, persist: bool = False
) -> bool:
    """Set the proxy context token budget. Returns True if successful.

    Applies ephemerally by default so a benchmark run does not mutate the proxy's
    persisted config_overrides.json.
    """
    base = _proxy_base(proxy_url)
    try:
        resp = client.post(
            f"{base}/admin/config",
            params={"persist": str(persist).lower()},
            json={"context_token_budget": budget},
            timeout=5,
        )
        return resp.status_code == 200
    except Exception:
        return False


def apply_arm_config(
    client: httpx.Client, proxy_url: str, config_overrides: dict, persist: bool = False
) -> bool:
    """Apply experiment-arm config overrides to the proxy. Returns True if successful.

    Applies ephemerally by default (persist=False): the proxy holds the override
    in memory for its current process but does NOT write config_overrides.json, so a
    benchmark run never mutates the proxy's persisted config. (Older proxies that do
    not support ?persist ignore the query param and persist as before.)
    """
    base = _proxy_base(proxy_url)
    try:
        resp = client.post(
            f"{base}/admin/config",
            params={"persist": str(persist).lower()},
            json=config_overrides,
            timeout=5,
        )
        if resp.status_code == 200:
            result = resp.json()
            if result.get("rejected"):
                print(f"  WARNING: rejected overrides: {result['rejected']}")
            else:
                _mode = "persisted" if result.get("persisted", True) else "ephemeral"
                print(f"  Config overrides applied ({_mode}): {result.get('updated', {})}")
            return True
        print(f"  WARNING: Failed to apply config overrides: {resp.status_code}")
        return False
    except Exception as e:
        print(f"  WARNING: Failed to apply config overrides: {e}")
        return False


def snapshot_proxy_config(client: httpx.Client, proxy_url: str) -> dict:
    """Capture the proxy runtime config for experiment recording."""
    base = _proxy_base(proxy_url)
    try:
        resp = client.get(f"{base}/admin/config", timeout=5)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return {}


def check_proxy_health(proxy_url: str) -> dict | None:
    """Check proxy health. Returns health dict on success, None on failure."""
    base = _proxy_base(proxy_url)
    try:
        with httpx.Client() as client:
            resp = client.get(f"{base}/health", timeout=5)
            if resp.status_code == 200:
                return resp.json()
    except Exception:
        pass
    return None
