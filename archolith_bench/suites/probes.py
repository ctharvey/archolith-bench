"""Fact probe evaluation: measure keyword recall after scenario turns."""

from __future__ import annotations

import httpx

from ..core.api import API_KEY, send_chat
from ..core.scenario import Scenario


def run_fact_probes(
    client: httpx.Client,
    scenario: Scenario,
    direct_history: list[dict],
    arm_history: list[dict],
    proxy_url: str,
    direct_url: str,
    model: str,
    current_turn: int,
    api_key: str = "",
    proxy_session_id: str | None = None,
    arm_config: dict | None = None,
) -> list[dict]:
    """Run fact probes after a specific turn.

    For each probe scheduled to run after current_turn, sends the probe question
    to both direct and proxy paths, counts keyword recall, and records results.

    Returns a list of probe result dicts with recall metrics for both arms.
    """
    _key = api_key or API_KEY
    results = []
    for probe in scenario.fact_probes:
        if probe.after_turn != current_turn:
            continue
        probe_msg = {"role": "user", "content": probe.question}
        direct_messages = direct_history + [probe_msg]
        direct_text, _, _ = send_chat(client, direct_url, _key, direct_messages, model)
        arm_messages = arm_history + [probe_msg]
        arm_text, _, _ = send_chat(
            client, proxy_url, _key, arm_messages, model,
            session_id=proxy_session_id, session_config=arm_config,
        )
        direct_hits = sum(1 for kw in probe.expected_keywords if kw.lower() in direct_text.lower())
        arm_hits = sum(1 for kw in probe.expected_keywords if kw.lower() in arm_text.lower())
        total_kw = len(probe.expected_keywords)
        result = {
            "after_turn": probe.after_turn,
            "question": probe.question,
            "expected_keywords": probe.expected_keywords,
            "direct_recall": round(direct_hits / total_kw, 3) if total_kw else 0,
            "arm_recall": round(arm_hits / total_kw, 3) if total_kw else 0,
            "direct_hits": direct_hits,
            "arm_hits": arm_hits,
            "total_keywords": total_kw,
            "direct_response_preview": direct_text[:200],
            "arm_response_preview": arm_text[:200],
        }
        results.append(result)
        status = "PASS" if arm_hits >= direct_hits else "DEGRADED"
        print(f"  [probe]  After turn {current_turn}: {status} -- "
              f"arm {arm_hits}/{total_kw} vs direct {direct_hits}/{total_kw} keywords recalled")
    return results
