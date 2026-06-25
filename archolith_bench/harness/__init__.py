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
from .longmemeval import LongMemEvalAdapter, LongMemEvalMemoryAdapter
from .checkpoint import MemoryCheckpoint, checkpoint_path_for
from .memory_ab import (
    DEFAULT_MEMORY_ARMS,
    NO_MEMORY,
    MemoryQAAdapter,
    MenhirClient,
    assert_not_production,
    run_memory_ab,
)
from .menhir_client import HttpMenhirClient, StubMenhirClient
from .scoring import LLMJudgeScorer

# Registry of available real-harness adapters, keyed by benchmark_id (the one roof).
# In-process: run_ab. ExternalCliAdapter: run_external_ab. MemoryQAAdapter: run_memory_ab.
ADAPTERS: dict[str, object] = {
    a.benchmark_id: a
    for a in (
        LongBenchV2Adapter(),
        BigCodeBenchHardAdapter(),
        LongMemEvalAdapter(),
        LongMemEvalMemoryAdapter(),
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


def is_memory(adapter: object) -> bool:
    """True if the adapter is an ingest-then-recall memory benchmark (run via run_memory_ab)."""
    return hasattr(adapter, "sessions") and hasattr(adapter, "load_items")


__all__ = [
    "ABResult",
    "ADAPTERS",
    "AgentDojoAdapter",
    "ArmResult",
    "BigCodeBenchHardAdapter",
    "CyberSecEvalAdapter",
    "DEFAULT_MEMORY_ARMS",
    "ExternalBenchmarkAdapter",
    "ExternalCliAdapter",
    "HarnessBenchmarkAdapter",
    "HttpMenhirClient",
    "LLMJudgeScorer",
    "LongBenchV2Adapter",
    "LongMemEvalAdapter",
    "LongMemEvalMemoryAdapter",
    "MemoryCheckpoint",
    "MemoryQAAdapter",
    "MenhirClient",
    "MtebAdapter",
    "checkpoint_path_for",
    "NO_MEMORY",
    "StubMenhirClient",
    "SweBenchAdapter",
    "Task",
    "TaskResult",
    "ab_result_to_dict",
    "arm_result_from_summary",
    "assert_not_production",
    "get_adapter",
    "is_external",
    "is_memory",
    "run_ab",
    "run_external_ab",
    "run_memory_ab",
    "write_harness_evidence",
]
