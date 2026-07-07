"""Offline tests for the R1 gold miner query-vehicle routing.

No graph and no real LLM: ``mine_r1_gold`` imports neo4j lazily (only in ``main``),
so the module and its pure helpers import cleanly in CI. The graph shapes are faked
with a scripted session; the LLM is faked with a fixed-reply client.
"""

from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import mine_r1_gold as miner  # noqa: E402

_RICH_BODY = "Computes the price of an order given tax and discount rules for checkout."


class _FakeClient:
    """Minimal stand-in for the OpenAI client used by ``_paraphrase``."""

    def __init__(self, reply: str) -> None:
        self._reply = reply
        self.chat = self
        self.completions = self

    def create(self, **_kwargs):
        msg = type("M", (), {"content": self._reply})()
        choice = type("C", (), {"message": msg})()
        return type("R", (), {"choices": [choice]})()


class _FakeSession:
    """Returns each scripted result set in ``session.run`` call order."""

    def __init__(self, result_sets: list[list[dict]]) -> None:
        self._sets = list(result_sets)

    def run(self, *_args, **_kwargs):
        return iter(self._sets.pop(0))


# --- _describe_query routing ----------------------------------------------


def test_describe_query_uses_paraphrase_when_client_and_rich_body() -> None:
    client = _FakeClient("How do I compute an order total with tax and discounts?")
    text, vehicle = miner._describe_query("PricingModel", _RICH_BODY, client)
    assert vehicle == "paraphrase"
    assert text == "How do I compute an order total with tax and discounts?"
    assert "pricingmodel" not in text.lower()


def test_describe_query_falls_back_to_identifier_without_client() -> None:
    assert miner._describe_query("PricingModel", _RICH_BODY, None) == (
        "PricingModel",
        "identifier",
    )


def test_describe_query_falls_back_when_body_too_thin() -> None:
    client = _FakeClient("some unrelated question")
    assert miner._describe_query("PricingModel", "short", client) == (
        "PricingModel",
        "identifier",
    )


def test_describe_query_falls_back_when_paraphrase_leaks_identifier() -> None:
    # _paraphrase returns None when the reply contains the name -> identifier fallback.
    client = _FakeClient("What does PricingModel do exactly?")
    assert miner._describe_query("PricingModel", _RICH_BODY, client) == (
        "PricingModel",
        "identifier",
    )


def test_describe_query_never_emits_the_broken_spaced_identifier() -> None:
    # Regression guard: the old vehicle produced "Pricing Model"; the redesign never does.
    text, _ = miner._describe_query("PricingModel", "short", None)
    assert " " not in text


# --- mine() family routing -------------------------------------------------


def _scripted_session() -> _FakeSession:
    symbol_rows = [
        {"uuid": "u-sym", "name": "PricingModel", "project": "projA", "body": _RICH_BODY}
    ]
    exact_rows = [
        {
            "uuid": "u-ex",
            "name": "resolve_project_root",
            "project": "projA",
            "body": "Resolves the repository root from a nested path.",
        }
    ]
    scope_rows = [
        {
            "name": "SharedThing",
            "projects": ["projA", "projB"],
            "nodes": [
                {"uuid": "u-a", "project": "projA", "body": _RICH_BODY},
                {"uuid": "u-b", "project": "projB", "body": "Project B variant body."},
            ],
        }
    ]
    return _FakeSession([symbol_rows, exact_rows, scope_rows])


def test_mine_routes_symbol_and_scope_through_paraphrase_vehicle() -> None:
    client = _FakeClient("How do I price an order with tax and discounts applied?")
    fixture = miner.mine(
        _scripted_session(), n_symbols=1, n_exact=1, n_scope=1, client=client
    )
    by_family: dict[str, list[dict]] = {}
    for q in fixture["queries"]:
        by_family.setdefault(q["family"], []).append(q)

    sym = by_family["symbol_name_query"][0]
    assert sym["vehicle"] == "paraphrase"
    assert "pricingmodel" not in sym["text"].lower()
    assert sym["target_symbol"] == "PricingModel"

    scope = by_family["wrong_repo_same_topic"][0]
    assert scope["vehicle"] == "paraphrase"
    assert scope["support_ids"] == ["u-a"]  # gold is project A's node
    assert "sharedthing" not in scope["text"].lower()

    exact = by_family["exact_error_string"][0]
    assert exact["text"] == "resolve_project_root"  # verbatim, unchanged


def test_mine_without_client_uses_identifier_vehicle() -> None:
    fixture = miner.mine(_scripted_session(), n_symbols=1, n_exact=1, n_scope=1)
    by_family = {q["family"]: q for q in fixture["queries"]}
    assert by_family["symbol_name_query"]["text"] == "PricingModel"
    assert by_family["symbol_name_query"]["vehicle"] == "identifier"
    assert by_family["wrong_repo_same_topic"]["vehicle"] == "identifier"
