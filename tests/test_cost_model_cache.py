"""Tests for cache-write asymmetry (P0) and helper-side cache credit (P3).

Kept separate from test_cost_model.py so the existing suite is untouched.
"""

from __future__ import annotations

import pytest

from archolith_bench.core.metrics import (
    PRICING_DEFAULTS,
    PricingModel,
    compute_arm_cost,
    compute_turn_cost,
)


# ---------------------------------------------------------------------------
# P0 — cache-write asymmetry: misses priced at input_cache_write when set
# ---------------------------------------------------------------------------


def test_cache_miss_priced_at_write_rate_when_set() -> None:
    """When input_cache_write is set, the miss bucket bills at the write rate."""
    pricing = PricingModel(
        provider="write-asym",
        input_full=5.00,
        input_cache_hit=0.50,
        input_cache_miss=5.00,
        output=25.00,
        input_cache_write=6.25,
    )
    turn = {
        "turn": 1,
        "cache_hit_tokens": 1_000_000,
        "cache_miss_tokens": 1_000_000,
        "prompt_tokens_actual": 2_000_000,
        "output_tokens": 0,
    }
    tc = compute_turn_cost(turn, pricing)
    # hit: 1M * 0.50/M = 0.50 ; miss priced at WRITE 6.25 (not 5.00): 1M * 6.25/M = 6.25
    assert tc.upstream_input_cost == pytest.approx(6.75, abs=1e-6)


def test_cache_miss_priced_at_miss_rate_when_write_none() -> None:
    """Without input_cache_write, the miss bucket bills at input_cache_miss."""
    pricing = PricingModel(
        provider="no-write",
        input_full=0.14,
        input_cache_hit=0.0028,
        input_cache_miss=0.14,
        output=0.28,
    )
    turn = {
        "turn": 1,
        "cache_hit_tokens": 1_000_000,
        "cache_miss_tokens": 1_000_000,
        "prompt_tokens_actual": 2_000_000,
        "output_tokens": 0,
    }
    tc = compute_turn_cost(turn, pricing)
    # hit: 1M * 0.0028/M = 0.0028 ; miss: 1M * 0.14/M = 0.14
    assert tc.upstream_input_cost == pytest.approx(0.1428, abs=1e-6)


def test_cold_start_turn_does_not_poison_arm_cache_availability() -> None:
    """A cold-start turn-0 (0 hit / 0 miss) must not force the arm to no-cache.

    Defect A regression: the first request of any session is unavoidably a cache
    miss with no cache split reported as activity; AND-ing availability across
    turns made every proxy arm read INCONCLUSIVE. OR semantics fix it.
    """
    pricing = PRICING_DEFAULTS["deepseek-v4-flash"]
    turns = [
        # turn 0: cold start - keys present but both zero
        {"turn": 0, "cache_hit_tokens": 0, "cache_miss_tokens": 0,
         "prompt_tokens_actual": 300, "output_tokens": 50},
        # turn 1+: real cache activity
        {"turn": 1, "cache_hit_tokens": 256, "cache_miss_tokens": 100,
         "prompt_tokens_actual": 356, "output_tokens": 50},
    ]
    ac = compute_arm_cost(turns, pricing)
    assert ac.cache_data_available is True


def test_arm_with_no_cache_activity_stays_unavailable() -> None:
    """When NO turn reports cache activity, the arm is still no-cache (OR of none)."""
    pricing = PRICING_DEFAULTS["deepseek-v4-flash"]
    turns = [
        {"turn": 0, "input_tokens": 300, "output_tokens": 50},
        {"turn": 1, "input_tokens": 400, "output_tokens": 50},
    ]
    ac = compute_arm_cost(turns, pricing)
    assert ac.cache_data_available is False


def test_present_but_none_token_keys_coerce_to_zero() -> None:
    """A cold-start proxy trace can carry present-but-None token fields.

    dict.get(key, default) returns None (not the default) when the key exists
    with a None value, which previously crashed compute_turn_cost on
    `None * rate`. All token reads must coerce None -> 0.
    """
    pricing = PRICING_DEFAULTS["deepseek-v4-flash"]
    turn = {
        "turn": 0,
        "assembly_mode": "unknown",
        "cache_hit_tokens": None,
        "cache_miss_tokens": None,
        "prompt_tokens_actual": None,
        "input_tokens": None,
        "output_tokens": None,
        "curator_prompt_tokens": None,
        "curator_completion_tokens": None,
        "extractor_cached_tokens": None,
    }
    tc = compute_turn_cost(turn, pricing)  # must not raise
    assert tc.effective_cost_usd == 0.0
    assert tc.helper_cost == 0.0
    assert tc.cache_data_available is False


def test_opus_default_carries_cache_write() -> None:
    """The opus-4-8 default models the cache-write premium."""
    a = PRICING_DEFAULTS["opus-4-8"]
    assert a.input_cache_write == 6.25
    assert a.input_cache_write > a.input_full  # write > full input


# ---------------------------------------------------------------------------
# P3 — helper-side cache credit: *_cached_tokens billed at helper_cache_hit
# ---------------------------------------------------------------------------


def test_helper_cached_tokens_credited_at_cache_rate() -> None:
    """Cached helper prompt tokens bill at helper_cache_hit, not helper_input."""
    pricing = PricingModel(
        provider="helper-cache",
        input_full=1.00,
        input_cache_hit=0.10,
        input_cache_miss=1.00,
        output=2.00,
        helper_input=0.40,
        helper_output=1.60,
        helper_cache_hit=0.10,
    )
    turn = {
        "turn": 1,
        "input_tokens": 0,
        "output_tokens": 0,
        # 1M curator prompt tokens, 800K of them served from the helper cache
        "curator_prompt_tokens": 1_000_000,
        "curator_cached_tokens": 800_000,
        "curator_completion_tokens": 0,
    }
    tc = compute_turn_cost(turn, pricing)
    # uncached 200K * 0.40/M = 0.08 ; cached 800K * 0.10/M = 0.08 -> 0.16
    assert tc.helper_cost == pytest.approx(0.16, abs=1e-6)


def test_helper_cache_noop_without_cached_tokens() -> None:
    """No *_cached_tokens field -> identical to full-rate helper pricing."""
    pricing = PricingModel(
        provider="helper-nocache",
        input_full=1.00,
        input_cache_hit=0.10,
        input_cache_miss=1.00,
        output=2.00,
        helper_input=0.40,
        helper_output=1.60,
        helper_cache_hit=0.10,
    )
    turn = {
        "turn": 1,
        "input_tokens": 0,
        "output_tokens": 0,
        "curator_prompt_tokens": 1_000_000,
        "curator_completion_tokens": 0,
    }
    tc = compute_turn_cost(turn, pricing)
    # all 1M uncached at 0.40/M = 0.40
    assert tc.helper_cost == pytest.approx(0.40, abs=1e-6)


def test_helper_cache_hit_unset_falls_back_to_helper_input() -> None:
    """helper_cache_hit unset -> cached tokens bill at the full helper rate."""
    pricing = PricingModel(
        provider="helper-nohc",
        input_full=1.00,
        input_cache_hit=0.10,
        input_cache_miss=1.00,
        output=2.00,
        helper_input=0.40,
        helper_output=1.60,
        # helper_cache_hit unset (0.0)
    )
    turn = {
        "turn": 1,
        "input_tokens": 0,
        "output_tokens": 0,
        "curator_prompt_tokens": 1_000_000,
        "curator_cached_tokens": 800_000,
        "curator_completion_tokens": 0,
    }
    tc = compute_turn_cost(turn, pricing)
    # no cache credit -> all 1M at 0.40/M = 0.40
    assert tc.helper_cost == pytest.approx(0.40, abs=1e-6)
