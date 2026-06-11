"""Metric dataclasses for the archolith-bench proxy suite."""

from __future__ import annotations

from dataclasses import dataclass, field


def estimate_tokens(text: str | None) -> int:
    """Estimate token count from text using a simple heuristic."""
    if not text:
        return 1
    return max(1, len(text) // 4)


def estimate_messages_tokens(messages: list[dict]) -> int:
    """Estimate total token count from a list of message dicts."""
    total = 0
    for m in messages:
        c = m.get("content", "")
        if isinstance(c, str):
            total += estimate_tokens(c)
        elif isinstance(c, list):
            for part in c:
                total += estimate_tokens(part.get("text", ""))
    return max(1, total)


# ---------------------------------------------------------------------------
# Pricing model — cache-aware effective cost
# ---------------------------------------------------------------------------


@dataclass
class PricingModel:
    """Per-provider pricing rates per 1M tokens.

    All rates in USD per 1M tokens.  Rates are static (dated in `comment`)
    — no live pricing lookups.

    `input_cache_write` is optional because Anthropic charges MORE than the
    full input rate for cache writes (write-vs-read asymmetry).
    """

    provider: str
    input_full: float
    input_cache_hit: float
    input_cache_miss: float
    output: float
    helper_input: float = 0.0
    helper_output: float = 0.0
    input_cache_write: float | None = None
    comment: str = ""


PRICING_DEFAULTS: dict[str, PricingModel] = {
    "deepseek": PricingModel(
        provider="deepseek",
        input_full=0.27,
        input_cache_hit=0.014,
        input_cache_miss=0.27,
        output=1.10,
        comment="Rates as of 2026-06: deepseek-chat",
    ),
    "openai": PricingModel(
        provider="openai",
        input_full=2.50,
        input_cache_hit=1.25,
        input_cache_miss=2.50,
        output=10.00,
        comment="Rates as of 2026-06: gpt-4o",
    ),
    "anthropic": PricingModel(
        provider="anthropic",
        input_full=3.00,
        input_cache_hit=0.30,
        input_cache_miss=3.00,
        output=15.00,
        input_cache_write=3.75,
        comment="Rates as of 2026-06: claude-sonnet-4-20250514",
    ),
}


@dataclass
class TurnCost:
    """Cache-weighted effective cost for a single turn."""

    turn: int
    effective_cost_usd: float
    cache_data_available: bool
    upstream_input_cost: float
    upstream_output_cost: float
    helper_cost: float = 0.0


@dataclass
class ArmCost:
    """Cache-weighted effective cost aggregated across turns."""

    total_effective_cost_usd: float
    cache_data_available: bool
    upstream_input_cost: float
    upstream_output_cost: float
    helper_cost: float = 0.0


_PER_M = 1_000_000.0


def compute_turn_cost(trace_turn: dict, pricing: PricingModel) -> TurnCost:
    """Compute cache-weighted effective cost for a single trace turn.

    Uses cache_hit_tokens / cache_miss_tokens when available; falls back to
    full-rate pricing on prompt_tokens_actual (or input_tokens) when the
    provider does not report cache data.
    """
    cache_hit = trace_turn.get("cache_hit_tokens", 0)
    cache_miss = trace_turn.get("cache_miss_tokens", 0)
    prompt_actual = trace_turn.get(
        "prompt_tokens_actual", trace_turn.get("input_tokens", 0)
    )
    output = trace_turn.get("output_tokens", 0)

    if cache_hit + cache_miss > 0:
        residual = max(0, prompt_actual - cache_hit - cache_miss)
        upstream_input = (
            cache_hit * pricing.input_cache_hit
            + cache_miss * pricing.input_cache_miss
            + residual * pricing.input_full
        ) / _PER_M
        cache_available = True
    else:
        upstream_input = prompt_actual * pricing.input_full / _PER_M
        cache_available = False

    upstream_output = output * pricing.output / _PER_M

    helper = _compute_helper_spend(trace_turn, pricing)

    return TurnCost(
        turn=trace_turn.get("turn_number", trace_turn.get("turn", 0)),
        effective_cost_usd=round(upstream_input + upstream_output + helper, 6),
        cache_data_available=cache_available,
        upstream_input_cost=round(upstream_input, 6),
        upstream_output_cost=round(upstream_output, 6),
        helper_cost=round(helper, 6),
    )


def compute_arm_cost(turns: list[dict], pricing: PricingModel) -> ArmCost:
    """Aggregate effective cost across trace turns for one experiment arm."""
    total_input = 0.0
    total_output = 0.0
    total_helper = 0.0
    cache_available = True

    for t in turns:
        tc = compute_turn_cost(t, pricing)
        total_input += tc.upstream_input_cost
        total_output += tc.upstream_output_cost
        total_helper += tc.helper_cost
        if not tc.cache_data_available:
            cache_available = False

    return ArmCost(
        total_effective_cost_usd=round(total_input + total_output + total_helper, 6),
        cache_data_available=cache_available,
        upstream_input_cost=round(total_input, 6),
        upstream_output_cost=round(total_output, 6),
        helper_cost=round(total_helper, 6),
    )


def _compute_helper_spend(trace_turn: dict, pricing: PricingModel) -> float:
    """Sum helper-LLM token costs (extractor / curator / embedding).

    Helper fields are expected to be present only when the archolith-context
    telemetry plan has landed.  Until then this returns 0.0.
    """
    hi = pricing.helper_input if pricing.helper_input else pricing.input_full
    ho = pricing.helper_output if pricing.helper_output else pricing.output
    total = 0.0
    for prefix in ("extractor", "curator", "embedding"):
        h_in = trace_turn.get(f"{prefix}_prompt_tokens", 0)
        h_out = trace_turn.get(f"{prefix}_completion_tokens", 0)
        total += h_in * hi / _PER_M
        total += h_out * ho / _PER_M
    return total


# ---------------------------------------------------------------------------
# Continuity metrics
# ---------------------------------------------------------------------------


@dataclass
class ContinuityMetrics:
    repeat_file_reads: int = 0
    repeat_diagnostics: int = 0
    decision_retention: float = 0.0
    verification_continuity: float = 0.0
    turn_one_orientation_score: float = 0.0
    snippet_hit_rate: float = 0.0