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
    HarnessBenchmarkAdapter,
    Task,
    TaskResult,
    ab_result_to_dict,
    arm_result_from_summary,
    run_ab,
    run_external_ab,
    write_harness_evidence,
)
from .bigcodebench import BigCodeBenchHardAdapter
from .external import (
    AgentDojoAdapter,
    CyberSecEvalAdapter,
    ExternalCliAdapter,
    MtebAdapter,
    SweBenchAdapter,
)
from .longbench_v2 import LongBenchV2Adapter

# Registry of available real-harness adapters, keyed by benchmark_id (the one roof).
# In-process adapters run via run_ab; ExternalCliAdapter subclasses run via run_external_ab.
ADAPTERS: dict[str, object] = {
    a.benchmark_id: a
    for a in (
        LongBenchV2Adapter(),
        BigCodeBenchHardAdapter(),
        SweBenchAdapter(),
        CyberSecEvalAdapter(),
        AgentDojoAdapter(),
        MtebAdapter(),
    )
}


def get_adapter(benchmark_id: str):
    """Return a registered adapter by benchmark_id, or raise with the known set."""
    try:
        return ADAPTERS[benchmark_id]
    except KeyError as e:
        raise KeyError(
            f"unknown benchmark_id: {benchmark_id!r} (available: {sorted(ADAPTERS)})"
        ) from e


def is_external(adapter: object) -> bool:
    """True if the adapter wraps an external CLI (run via run_external_ab)."""
    return isinstance(adapter, ExternalCliAdapter)


__all__ = [
    "ABResult",
    "ADAPTERS",
    "AgentDojoAdapter",
    "ArmResult",
    "BigCodeBenchHardAdapter",
    "CyberSecEvalAdapter",
    "ExternalBenchmarkAdapter",
    "ExternalCliAdapter",
    "HarnessBenchmarkAdapter",
    "LongBenchV2Adapter",
    "MtebAdapter",
    "SweBenchAdapter",
    "Task",
    "TaskResult",
    "ab_result_to_dict",
    "arm_result_from_summary",
    "get_adapter",
    "is_external",
    "run_ab",
    "run_external_ab",
    "write_harness_evidence",
]
