"""External benchmark harness — real official benchmarks run as direct-vs-proxy A/B.

Archolith is middleware, not a model, so these adapters never claim a standalone
benchmark score. They run the official dataset + scorer twice (client base_url =
direct, then = proxy) and report the delta the proxy/filter produces: official
score preserved + tokens/cost reduced.

All benchmarks live under one roof here behind ExternalBenchmarkAdapter.
"""

from __future__ import annotations

from .base import (
    ABResult,
    ArmResult,
    ExternalBenchmarkAdapter,
    Task,
    TaskResult,
    ab_result_to_dict,
    run_ab,
    write_harness_evidence,
)
from .longbench_v2 import LongBenchV2Adapter

# Registry of available real-harness adapters, keyed by benchmark_id (the one roof).
# New official-benchmark adapters register here once implemented.
ADAPTERS: dict[str, ExternalBenchmarkAdapter] = {
    LongBenchV2Adapter.benchmark_id: LongBenchV2Adapter(),
}


def get_adapter(benchmark_id: str) -> ExternalBenchmarkAdapter:
    """Return a registered adapter by benchmark_id, or raise with the known set."""
    try:
        return ADAPTERS[benchmark_id]
    except KeyError as e:
        raise KeyError(
            f"unknown benchmark_id: {benchmark_id!r} (available: {sorted(ADAPTERS)})"
        ) from e


__all__ = [
    "ABResult",
    "ADAPTERS",
    "ArmResult",
    "ExternalBenchmarkAdapter",
    "LongBenchV2Adapter",
    "Task",
    "TaskResult",
    "ab_result_to_dict",
    "get_adapter",
    "run_ab",
    "write_harness_evidence",
]
