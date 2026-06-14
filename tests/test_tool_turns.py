"""Tests for tool-loop (agent-solo) turn assembly and scenario loading."""

from __future__ import annotations

import json

from archolith_bench.core.scenario import (
    Scenario,
    build_turn_messages,
    is_tool_turn,
    list_scenarios,
)


# ---------------------------------------------------------------------------
# is_tool_turn
# ---------------------------------------------------------------------------


def test_is_tool_turn() -> None:
    assert is_tool_turn({"user": "go", "tool_calls": []}) is True
    assert is_tool_turn("just a string") is False
    assert is_tool_turn({"user": "no tools"}) is False  # dict without tool_calls


# ---------------------------------------------------------------------------
# build_turn_messages — string turn (unchanged behavior)
# ---------------------------------------------------------------------------


def test_string_turn_is_single_user_message() -> None:
    msgs = build_turn_messages("read the file")
    assert msgs == [{"role": "user", "content": "read the file"}]


# ---------------------------------------------------------------------------
# build_turn_messages — tool-loop turn (agent-solo)
# ---------------------------------------------------------------------------


def test_tool_loop_turn_ends_in_tool_result() -> None:
    """The assembled history must END in a role:'tool' message so the proxy
    classifies the request as an agent-solo turn (mechanical levers fire)."""
    turn = {
        "user": "Read app/models.py and run the tests.",
        "tool_calls": [
            {"name": "read_file", "arguments": {"path": "app/models.py"}, "result": "X" * 500},
            {"name": "bash", "arguments": {"cmd": "pytest -q"}, "result": "Y" * 500},
        ],
    }
    msgs = build_turn_messages(turn)

    # user first, then (assistant tool_call, tool result) per call
    assert msgs[0] == {"role": "user", "content": "Read app/models.py and run the tests."}
    assert len(msgs) == 1 + 2 * 2
    assert msgs[-1]["role"] == "tool"  # ENDS in a tool result -> agent-solo

    # assistant tool_call shape is well-formed (OpenAI function-call shape)
    a = msgs[1]
    assert a["role"] == "assistant" and a["content"] is None
    tc = a["tool_calls"][0]
    assert tc["type"] == "function"
    assert tc["function"]["name"] == "read_file"
    # arguments serialized to a JSON string
    assert json.loads(tc["function"]["arguments"]) == {"path": "app/models.py"}
    # tool result references the assistant call's id
    assert msgs[2]["role"] == "tool"
    assert msgs[2]["tool_call_id"] == tc["id"]
    assert msgs[2]["content"] == "X" * 500


def test_tool_call_ids_are_stable_and_deterministic() -> None:
    turn = {"user": "go", "tool_calls": [{"name": "grep", "arguments": {"q": "foo"}, "result": "r"}]}
    a = build_turn_messages(turn)
    b = build_turn_messages(turn)
    assert a[1]["tool_calls"][0]["id"] == b[1]["tool_calls"][0]["id"]
    assert a[1]["tool_calls"][0]["id"].startswith("call_")


# ---------------------------------------------------------------------------
# Scenario loading — new tool_heavy + existing string scenarios
# ---------------------------------------------------------------------------


def test_tool_heavy_scenario_loads_and_has_tool_turns() -> None:
    paths = {p.name: p for p in list_scenarios()}
    assert "tool_heavy.json" in paths
    scen = Scenario.from_file(paths["tool_heavy.json"])
    tool_turns = [t for t in scen.turns if is_tool_turn(t)]
    assert len(tool_turns) >= 1
    # every tool-loop turn assembles to a history ending in a tool result
    for t in tool_turns:
        assert build_turn_messages(t)[-1]["role"] == "tool"


def test_existing_string_scenarios_still_load() -> None:
    paths = {p.name: p for p in list_scenarios()}
    for name in ("long_agent.json", "taskflow.json"):
        scen = Scenario.from_file(paths[name])
        assert all(isinstance(t, str) for t in scen.turns)
        assert build_turn_messages(scen.turns[0]) == [{"role": "user", "content": scen.turns[0]}]
