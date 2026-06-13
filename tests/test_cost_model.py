"""Tests for PricingModel, compute_turn_cost, and compute_arm_cost."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from archolith_bench.core.metrics import (
    PRICING_DEFAULTS,
    ArmCost,
    PricingModel,
    TurnCost,
    compute_arm_cost,
    compute_turn_cost,
)


# ---------------------------------------------------------------------------
# PricingModel
# ---------------------------------------------------------------------------


def test_pricing_defaults_exist() -> None:
    """The current-model default providers are registered."""
    assert "deepseek-v4-flash" in PRICING_DEFAULTS
    assert "deepseek-v4-pro" in PRICING_DEFAULTS
    assert "opus-4-8" in PRICING_DEFAULTS
    assert "openai" in PRICING_DEFAULTS
    assert "anthropic" in PRICING_DEFAULTS
    # deprecated deepseek-chat alias has been removed
    assert "deepseek" not in PRICING_DEFAULTS

    d = PRICING_DEFAULTS["deepseek-v4-flash"]
    assert d.input_cache_hit < d.input_full  # cache hits are cheaper
    assert d.input_cache_write is None  # deepseek has no write asymmetry


def test_anthropic_cache_write_asymmetry() -> None:
    """Anthropic has input_cache_write > input_full (write-vs-read asymmetry)."""
    a = PRICING_DEFAULTS["anthropic"]
    assert a.input_cache_write is not None
    assert a.input_cache_write > a.input_full


# ---------------------------------------------------------------------------
# compute_turn_cost — cache data available
# ---------------------------------------------------------------------------


def test_compute_turn_cost_cache_split() -> None:
    """Cache-hit tokens are priced at the hit rate, misses at full rate."""
    pricing = PricingModel(
        provider="test",
        input_full=1.00,
        input_cache_hit=0.10,
        input_cache_miss=1.00,
        output=2.00,
    )
    turn = {
        "turn": 1,
        "cache_hit_tokens": 800_000,
        "cache_miss_tokens": 200_000,
        "prompt_tokens_actual": 1_000_000,
        "output_tokens": 500_000,
    }
    tc = compute_turn_cost(turn, pricing)

    assert tc.cache_data_available is True
    # input: 800K * 0.10/M + 200K * 1.00/M = 0.08 + 0.20 = 0.28
    assert tc.upstream_input_cost == pytest.approx(0.28, abs=1e-6)
    # output: 500K * 2.00/M = 1.00
    assert tc.upstream_output_cost == pytest.approx(1.00, abs=1e-6)
    assert tc.effective_cost_usd == pytest.approx(1.28, abs=1e-6)
    assert tc.helper_cost == 0.0


def test_compute_turn_cost_residual_pricing() -> None:
    """Tokens beyond cache_hit + cache_miss are priced at full rate."""
    pricing = PRICING_DEFAULTS["deepseek-v4-flash"]
    turn = {
        "turn": 1,
        "cache_hit_tokens": 500_000,
        "cache_miss_tokens": 200_000,
        "prompt_tokens_actual": 1_000_000,
        "output_tokens": 100,
    }
    tc = compute_turn_cost(turn, pricing)

    assert tc.cache_data_available is True
    # residual = 1M - 500K - 200K = 300K
    # 500K * 0.0028/M + 200K * 0.14/M + 300K * 0.14/M
    # = 0.0014 + 0.028 + 0.042 = 0.0714
    assert tc.upstream_input_cost == pytest.approx(0.0714, abs=1e-6)


# ---------------------------------------------------------------------------
# compute_turn_cost — no cache data (fallback)
# ---------------------------------------------------------------------------


def test_compute_turn_cost_no_cache_fallback() -> None:
    """When cache_hit + cache_miss == 0, fall back to full-rate pricing."""
    pricing = PRICING_DEFAULTS["deepseek-v4-flash"]
    turn = {
        "turn": 1,
        "cache_hit_tokens": 0,
        "cache_miss_tokens": 0,
        "prompt_tokens_actual": 1_000_000,
        "output_tokens": 500_000,
    }
    tc = compute_turn_cost(turn, pricing)

    assert tc.cache_data_available is False
    assert tc.upstream_input_cost == pytest.approx(0.14, abs=1e-6)  # 1M * 0.14
    assert tc.upstream_output_cost == pytest.approx(0.14, abs=1e-6)  # 500K * 0.28
    assert tc.effective_cost_usd == pytest.approx(0.28, abs=1e-6)


def test_compute_turn_cost_falls_back_to_input_tokens() -> None:
    """When prompt_tokens_actual is missing, fall back to input_tokens."""
    pricing = PRICING_DEFAULTS["deepseek-v4-flash"]
    turn = {
        "turn": 1,
        "input_tokens": 500_000,
        "output_tokens": 100,
    }
    tc = compute_turn_cost(turn, pricing)

    assert tc.cache_data_available is False
    assert tc.upstream_input_cost == pytest.approx(0.07, abs=1e-6)  # 500K * 0.14


# ---------------------------------------------------------------------------
# compute_turn_cost — helper spend
# ---------------------------------------------------------------------------


def test_compute_turn_cost_helper_spend() -> None:
    """Extractor/curator/embedding prompt+completion tokens are priced."""
    pricing = PricingModel(
        provider="test",
        input_full=1.00,
        input_cache_hit=0.10,
        input_cache_miss=1.00,
        output=2.00,
        helper_input=0.15,
        helper_output=0.60,
    )
    turn = {
        "turn": 1,
        "cache_hit_tokens": 1_000_000,
        "cache_miss_tokens": 0,
        "prompt_tokens_actual": 1_000_000,
        "output_tokens": 0,
        "extractor_prompt_tokens": 500_000,
        "extractor_completion_tokens": 100_000,
        "curator_prompt_tokens": 200_000,
        "curator_completion_tokens": 50_000,
    }
    tc = compute_turn_cost(turn, pricing)

    # helper: (500K*0.15 + 100K*0.60 + 200K*0.15 + 50K*0.60) / 1M
    # = (75_000 + 60_000 + 30_000 + 30_000) / 1M = 0.195
    assert tc.helper_cost == pytest.approx(0.195, abs=1e-6)


def test_compute_turn_cost_helper_defaults_to_full_rate() -> None:
    """When helper_input/output are zero/unset, fall back to full rates."""
    # Inline model with helper rates unset, so this stays decoupled from
    # whichever provider defaults set helper rates.
    pricing = PricingModel(
        provider="no-helper-rates",
        input_full=0.27,
        input_cache_hit=0.014,
        input_cache_miss=0.27,
        output=1.10,
    )  # helper_input=0, helper_output=0
    turn = {
        "turn": 1,
        "input_tokens": 100,
        "output_tokens": 0,
        "extractor_prompt_tokens": 1_000_000,
        "extractor_completion_tokens": 100_000,
        "embedding_prompt_tokens": 500_000,
    }
    tc = compute_turn_cost(turn, pricing)

    # helper uses input_full (0.27) for prompt, output (1.10) for completion
    # Extractor: 1M * 0.27/M + 100K * 1.10/M = 0.27 + 0.11 = 0.38
    # Embedding: 500K * 0.27/M = 0.135
    assert tc.helper_cost == pytest.approx(0.515, abs=1e-6)


# ---------------------------------------------------------------------------
# compute_turn_cost — zero-token edge cases
# ---------------------------------------------------------------------------


def test_compute_turn_cost_zero_tokens() -> None:
    """Zero-token turns produce zero cost."""
    pricing = PRICING_DEFAULTS["deepseek-v4-flash"]
    turn = {"turn": 1, "input_tokens": 0, "output_tokens": 0}
    tc = compute_turn_cost(turn, pricing)

    assert tc.effective_cost_usd == 0.0
    assert tc.upstream_input_cost == 0.0
    assert tc.upstream_output_cost == 0.0
    assert tc.cache_data_available is False


# ---------------------------------------------------------------------------
# compute_arm_cost — aggregation
# ---------------------------------------------------------------------------


def test_compute_arm_cost_aggregates_turns() -> None:
    """compute_arm_cost sums costs and tracks cache availability."""
    pricing = PRICING_DEFAULTS["deepseek-v4-flash"]
    turns = [
        {
            "turn": 1,
            "cache_hit_tokens": 500_000,
            "cache_miss_tokens": 100_000,
            "prompt_tokens_actual": 600_000,
            "output_tokens": 50_000,
        },
        {
            "turn": 2,
            "input_tokens": 400_000,
            "output_tokens": 30_000,
            # no cache data for turn 2 -> cache_data_available becomes False
        },
    ]
    ac = compute_arm_cost(turns, pricing)

    # OR semantics: turn 1 reports cache activity, so the arm has cache telemetry
    # even though turn 2 (no cache keys) does not. A single no-cache turn must not
    # poison the arm (the cold-start turn is unavoidably a miss).
    assert ac.cache_data_available is True
    # turn 1: 500K*0.0028 + 100K*0.14 = 0.0014 + 0.014 = 0.0154 input
    #         + 50K*0.28/M = 0.014 output
    # turn 2: 400K*0.14 = 0.056 input + 30K*0.28/M = 0.0084 output
    assert ac.upstream_input_cost == pytest.approx(0.0714, abs=1e-6)
    assert ac.upstream_output_cost == pytest.approx(0.0224, abs=1e-6)
    assert ac.total_effective_cost_usd == pytest.approx(0.0938, abs=1e-6)


def test_compute_arm_cost_all_cache_available() -> None:
    """When all turns have cache data, cache_data_available is True."""
    pricing = PRICING_DEFAULTS["deepseek-v4-flash"]
    turns = [
        {"turn": 1, "cache_hit_tokens": 100, "cache_miss_tokens": 10, "prompt_tokens_actual": 110, "output_tokens": 50},
        {"turn": 2, "cache_hit_tokens": 100, "cache_miss_tokens": 10, "prompt_tokens_actual": 110, "output_tokens": 50},
    ]
    ac = compute_arm_cost(turns, pricing)
    assert ac.cache_data_available is True


# ---------------------------------------------------------------------------
# --pricing-file override
# ---------------------------------------------------------------------------


def test_pricing_file_override() -> None:
    """A JSON pricing file can supply custom rates to PricingModel."""
    data = {
        "provider": "custom",
        "input_full": 0.50,
        "input_cache_hit": 0.05,
        "input_cache_miss": 0.50,
        "output": 1.00,
        "comment": "custom test pricing",
    }
    pricing = PricingModel(**data)
    assert pricing.provider == "custom"
    assert pricing.input_full == 0.50
    assert pricing.input_cache_hit == 0.05
    assert pricing.input_cache_write is None  # not in JSON


def test_pricing_file_malformed_field() -> None:
    """A missing required field fails with TypeError (loud failure)."""
    with pytest.raises(TypeError):
        PricingModel(provider="bad", input_full=1.0)  # missing required fields
