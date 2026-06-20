"""Representative token-estimator validation fixtures."""

from __future__ import annotations

import json

import pytest

from archolith_bench.core.metrics import estimate_messages_tokens, estimate_tokens


PLAIN_ENGLISH = (
    "The benchmark runner compares a direct upstream conversation with a proxy-curated conversation across "
    "several turns. The goal is to measure whether the proxy preserves context while reducing prompt tokens "
    "and effective cost."
)

JSON_TOOL_SCHEMA = json.dumps(
    {
        "type": "function",
        "function": {
            "name": "search_cards",
            "description": "Search Pokemon cards by set, rarity, type, and price range.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "filters": {
                        "type": "object",
                        "properties": {
                            "set": {"type": "string"},
                            "rarity": {"type": "array", "items": {"type": "string"}},
                            "price_max": {"type": "number"},
                        },
                    },
                    "limit": {"type": "integer", "minimum": 1, "maximum": 100},
                },
                "required": ["query"],
            },
        },
    },
    indent=2,
)

CODE_SNIPPET = (
    "def summarize_turns(turns: list[dict[str, object]]) -> dict[str, int]:\n"
    "    totals = {\"input\": 0, \"output\": 0}\n"
    "    for turn in turns:\n"
    "        totals[\"input\"] += int(turn.get(\"prompt_tokens\") or 0)\n"
    "        totals[\"output\"] += int(turn.get(\"completion_tokens\") or 0)\n"
    "    return totals\n"
)

MIXED_MESSAGES = [
    {"role": "system", "content": "You are measuring benchmark token accounting accuracy."},
    {"role": "user", "content": JSON_TOOL_SCHEMA},
    {
        "role": "assistant",
        "content": [
            {"type": "text", "text": "I will compare estimates against cl100k_base."},
            {"type": "text", "text": CODE_SNIPPET},
        ],
    },
]


def _legacy_char_divide_estimate(text: str) -> int:
    return max(1, len(text) // 4)


def _cl100k_count(text: str) -> int:
    tiktoken = pytest.importorskip("tiktoken")
    return len(tiktoken.get_encoding("cl100k_base").encode(text))


@pytest.mark.parametrize(
    "fixture",
    [
        PLAIN_ENGLISH,
        JSON_TOOL_SCHEMA,
        CODE_SNIPPET,
    ],
)
def test_estimate_tokens_matches_cl100k_when_available(fixture: str) -> None:
    assert estimate_tokens(fixture) == _cl100k_count(fixture)


def test_estimate_messages_tokens_matches_content_only_cl100k_when_available() -> None:
    expected = (
        _cl100k_count(MIXED_MESSAGES[0]["content"])
        + _cl100k_count(MIXED_MESSAGES[1]["content"])
        + _cl100k_count(MIXED_MESSAGES[2]["content"][0]["text"])
        + _cl100k_count(MIXED_MESSAGES[2]["content"][1]["text"])
    )

    assert estimate_messages_tokens(MIXED_MESSAGES) == expected


def test_representative_fixture_shapes_stay_exercised_without_tiktoken() -> None:
    assert len(PLAIN_ENGLISH) > 100
    assert json.loads(JSON_TOOL_SCHEMA)["function"]["parameters"]["properties"]["filters"]
    assert "prompt_tokens" in CODE_SNIPPET
    assert isinstance(MIXED_MESSAGES[2]["content"], list)


def test_legacy_char_divide_heuristic_has_material_fixture_error_when_available() -> None:
    plain_error = (_legacy_char_divide_estimate(PLAIN_ENGLISH) - _cl100k_count(PLAIN_ENGLISH)) / _cl100k_count(
        PLAIN_ENGLISH
    )
    code_error = (_legacy_char_divide_estimate(CODE_SNIPPET) - _cl100k_count(CODE_SNIPPET)) / _cl100k_count(
        CODE_SNIPPET
    )
    json_error = (_legacy_char_divide_estimate(JSON_TOOL_SCHEMA) - _cl100k_count(JSON_TOOL_SCHEMA)) / _cl100k_count(
        JSON_TOOL_SCHEMA
    )

    assert plain_error > 0.25
    assert code_error < -0.05
    assert abs(json_error) < 0.10
