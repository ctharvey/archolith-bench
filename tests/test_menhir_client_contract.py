"""Contract tests for HttpMenhirClient -- the client the real LME ingest actually uses.

Why this file exists: HttpMenhirClient had NO test coverage, so a `diff` reference was added
to `ingest()`'s body without adding it to `ingest()`'s signature. Every test passed (they all
drive StubMenhirClient, which DID get the parameter) while every real ingest died with
`NameError: name 'diff' is not defined`. It surfaced only when a live LME build was attempted.

Two guards, both cheap:
  1. signature parity between the stub and the real client -- a param added to one must be
     added to the other, which is what actually drifted.
  2. exercise the real ingest()/ingest_raw() bodies against a fake transport, so an unresolved
     name in the payload-building path fails here instead of a day into a graph build.
"""

from __future__ import annotations

import inspect

import pytest

from archolith_bench.harness.menhir_client import HttpMenhirClient, StubMenhirClient


class _FakeResponse:
    status_code = 200

    def raise_for_status(self) -> None:  # pragma: no cover - trivial
        return None

    def json(self) -> dict:  # pragma: no cover - trivial
        return {"results": []}


class _FakeHttpx:
    """Records calls so the test can assert on the built payload."""

    def __init__(self) -> None:
        self.posts: list[dict] = []

    def post(self, url, *, params=None, json=None, headers=None, **kw):
        self.posts.append({"url": url, "params": params, "json": json})
        return _FakeResponse()

    def delete(self, url, **kw):  # pragma: no cover - unused here
        return _FakeResponse()

    def close(self) -> None:  # pragma: no cover - trivial
        return None


@pytest.fixture()
def http_client() -> tuple[HttpMenhirClient, _FakeHttpx]:
    client = HttpMenhirClient("http://localhost:9999")
    fake = _FakeHttpx()
    client._client = fake  # type: ignore[attr-defined]
    return client, fake


def test_ingest_signature_parity_stub_vs_http():
    """A kwarg on one client must exist on the other. This is the drift that shipped."""
    stub = set(inspect.signature(StubMenhirClient.ingest).parameters) - {"self"}
    http = set(inspect.signature(HttpMenhirClient.ingest).parameters) - {"self"}
    assert stub == http, (
        f"ingest() kwargs drifted: stub-only={sorted(stub - http)}, http-only={sorted(http - stub)}"
    )


def test_ingest_body_resolves_every_name(http_client):
    """The regression: ingest() referenced `diff` without declaring it -> NameError at runtime.

    Passing every optional kwarg walks each `if X is not None` branch in the payload builder,
    so any name the body references but the signature omits raises here.
    """
    client, fake = http_client
    client.ingest(
        "ns-1",
        "user",
        "hello world",
        occurred_at="2024-01-01T00:00:00Z",
        session_id="s-1",
        source="user",
        diff="--- a\n+++ b\n",
        wait=False,
        flagged=True,
        bootstrap_scope="general",
    )
    assert len(fake.posts) == 1
    payload = fake.posts[0]["json"]
    assert payload["namespace"] == "ns-1"
    assert payload["episode"] == "user: hello world"
    assert payload["source"] == "user"
    assert payload["diff"] == "--- a\n+++ b\n"
    assert payload["occurred_at"] == "2024-01-01T00:00:00Z"


def test_ingest_omits_unset_optionals(http_client):
    """Unset optionals must stay out of the payload rather than posting explicit nulls."""
    client, fake = http_client
    client.ingest("ns-1", "user", "hello")
    payload = fake.posts[0]["json"]
    for key in ("diff", "source", "occurred_at", "session_id"):
        assert key not in payload, f"unset {key} must not be sent"


def test_ingest_skips_empty_content(http_client):
    """Empty content is a no-op -- LME haystacks contain blank turns."""
    client, fake = http_client
    client.ingest("ns-1", "user", "")
    assert fake.posts == []


def test_ingest_raw_body_resolves_every_name(http_client):
    """ingest_raw() posts an exact episode body for deterministic probes."""
    client, fake = http_client
    client.ingest_raw("ns-1", "exact body", source="user", wait=False)
    payload = fake.posts[0]["json"]
    assert payload == {"episode": "exact body", "namespace": "ns-1", "source": "user"}
