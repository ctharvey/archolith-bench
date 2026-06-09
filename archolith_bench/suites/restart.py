"""Restart/bootstrap scoring: measures turn-one orientation after a fresh session start."""

from __future__ import annotations

import re

import httpx

from ..core.api import API_KEY, send_chat
from .continuity import _COMMAND_RE, _FILE_PATH_RE, _REREAD_PHRASES


def run_restart_bootstrap(
    client: httpx.Client,
    scenario,
    proxy_url: str,
    direct_url: str,
    model: str,
    api_key: str,
    arm_config: dict | None = None,
) -> dict:
    """Replay a scenario, then start a fresh conversation in the same proxy
    session and score turn_one_orientation_score.

    The orientation prompt asks the model to recall the last blocker/next step.
    A good response should reference key facts from earlier turns (high keyword
    overlap with the last response) WITHOUT expressing intent to re-read files
    (which indicates information loss).
    """
    _key = api_key or API_KEY
    system_msg = {"role": "system", "content": scenario.system_prompt}
    history = [system_msg]

    for i, user_msg in enumerate(scenario.turns, 1):
        history.append({"role": "user", "content": user_msg})
        text, _, _ = send_chat(client, proxy_url, _key, history, model, session_config=arm_config)
        history.append({"role": "assistant", "content": text})

    last_response = history[-1]["content"] if history else ""
    last_files = set(_FILE_PATH_RE.findall(last_response))
    last_commands = set(_COMMAND_RE.findall(last_response))

    all_keywords: set[str] = set()
    for turn_text in [m["content"] for m in history if m["role"] == "assistant"]:
        words = turn_text.lower().split()
        all_keywords.update(w for w in words if len(w) >= 4)
    last_keywords = set(last_response.lower().split())
    key_facts = last_keywords & all_keywords

    orientation_prompt = (
        "This is a new conversation in the same project. Without re-reading any "
        "files, what was the last blocker or next step we were working on, and "
        "what should we do next?"
    )

    fresh_history = [system_msg, {"role": "user", "content": orientation_prompt}]
    orientation_text, _, _ = send_chat(client, proxy_url, _key, fresh_history, model, session_config=arm_config)

    orientation_lower = orientation_text.lower()

    if key_facts:
        facts_recalled = sum(1 for kw in key_facts if kw in orientation_lower)
        fact_recovery = facts_recalled / len(key_facts)
    else:
        fact_recovery = 1.0 if orientation_text.strip() else 0.0

    explicit_reread = bool(_REREAD_PHRASES.search(orientation_text))

    if fact_recovery > 0 and not explicit_reread:
        orientation_score = min(fact_recovery * 1.2, 1.0)
    elif fact_recovery > 0 and explicit_reread:
        orientation_score = fact_recovery * 0.5
    else:
        orientation_score = 0.0

    return {
        "orientation_prompt": orientation_prompt,
        "orientation_response_preview": orientation_text[:500],
        "orientation_score": round(orientation_score, 4),
        "fact_recovery": round(fact_recovery, 4),
        "key_facts_count": len(key_facts),
        "facts_recalled": facts_recalled if key_facts else 0,
        "explicit_reread": explicit_reread,
        "last_files_count": len(last_files),
        "last_commands_count": len(last_commands),
    }
