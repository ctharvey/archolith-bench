"""Metric dataclasses for the archolith-bench proxy suite."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TokenMetrics:
    direct_input: int = 0
    arm_input: int = 0
    rewritten_tokens: int = 0
    savings_ratio: float = 0.0
    extraction_cost: int = 0
    net_savings: int = 0


@dataclass
class ContinuityMetrics:
    repeat_file_reads: int = 0
    repeat_diagnostics: int = 0
    decision_retention: float = 0.0
    verification_continuity: float = 0.0
    turn_one_orientation_score: float = 0.0
    snippet_hit_rate: float = 0.0


@dataclass
class QualityPerfMetrics:
    fact_recall_accuracy: float = 0.0
    response_similarity: float = 0.0
    assembly_latency_ms: float = 0.0
    total_latency_ms: float = 0.0


@dataclass
class TurnResult:
    turn: int
    user_msg_preview: str = ""
    user_msg: str = ""
    direct: dict = field(default_factory=dict)
    proxy: dict = field(default_factory=dict)
    trace: dict = field(default_factory=dict)
    token_metrics: TokenMetrics = field(default_factory=TokenMetrics)
    continuity: ContinuityMetrics = field(default_factory=ContinuityMetrics)


@dataclass
class ScenarioResult:
    scenario: str = ""
    description: str = ""
    model: str = ""
    budget: int | None = None
    arm: str = ""
    turns_run: int = 0
    turns_total: int = 0
    aborted: bool = False
    abort_reason: str = ""
    timestamp: str = ""
    summary: dict = field(default_factory=dict)
    quality: dict = field(default_factory=dict)
    continuity: ContinuityMetrics = field(default_factory=ContinuityMetrics)
    turns: list[TurnResult] = field(default_factory=list)
    fact_probes: list[dict] = field(default_factory=list)