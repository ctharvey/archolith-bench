"""Fact probe evaluation: measure keyword recall after scenario turns."""

from __future__ import annotations

import re

import httpx

from ..core.api import API_KEY, send_chat
from ..core.scenario import Scenario

_WORD_RE = re.compile(r"[a-z0-9]+")


def _stem_token(token: str) -> str:
    """Small dependency-free stemmer for benchmark probe keywords.

    This is intentionally conservative: it handles common English inflections
    that caused recall undercounts (`run` vs `running`, plurals, simple past)
    without pulling in a heavy NLP dependency for the benchmark CLI.
    """
    token = token.lower()
    for suffix in ("ing", "ed", "es", "s"):
        min_len = len(suffix) + 2
        if len(token) > min_len and token.endswith(suffix):
            stem = token[: -len(suffix)]
            if len(stem) >= 3 and stem[-1] == stem[-2]:
                stem = stem[:-1]
            return stem
    return token


def _keyword_hit(keyword: str, response_text: str) -> bool:
    """Return True when a probe keyword or phrase is recalled.

    Exact normalized phrase matching still wins. If that misses, compare simple
    stems for every token in the keyword phrase so inflection-only differences
    don't count as recall loss.
    """
    keyword_tokens = [_stem_token(t) for t in _WORD_RE.findall(keyword.lower())]
    response_tokens = {_stem_token(t) for t in _WORD_RE.findall(response_text.lower())}
    if not keyword_tokens:
        return False

    normalized_keyword = " ".join(_WORD_RE.findall(keyword.lower()))
    normalized_response = " ".join(_WORD_RE.findall(response_text.lower()))
    if normalized_keyword and normalized_keyword in normalized_response:
        return True

    return all(token in response_tokens for token in keyword_tokens)


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
        direct_hits = sum(1 for kw in probe.expected_keywords if _keyword_hit(kw, direct_text))
        arm_hits = sum(1 for kw in probe.expected_keywords if _keyword_hit(kw, arm_text))
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
