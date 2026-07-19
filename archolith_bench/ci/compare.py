"""Gate logic: compare current bench results vs a pinned baseline.

Baseline file format (``benchmarks/longmemeval-baseline.json``):
    {
      "baseline_version": "2026-07-19-v1",
      "baseline_commit": "abc1234",
      "stratified_slice_hash": "sha256:...",
      "results": {
        "overall": 0.230,
        "by_type": {
          "single-session": 0.350,
          "multi-session": 0.180,
          ...
        },
        "per_question": [
          {"id": "Q-001", "type": "single-session", "score": 1.0},
          ...
        ]
      }
    }

Gate rules:
- PASS: overall delta >= -0.02 (i.e. no more than 2% absolute regression)
        AND no single type delta < -0.10 (no silent type-specific regression)
- WARN: overall PASS but any single type delta < -0.10
- FAIL: overall delta < -0.02
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

OVERALL_PASS_THRESHOLD = -0.02  # -2% absolute
TYPE_WARN_THRESHOLD = -0.10     # -10% absolute on a single type
TYPE_FAIL_THRESHOLD = -0.20     # -20% absolute — used for severity, not gate


class GateResult(str, Enum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"


@dataclass
class TypeDelta:
    type: str
    baseline: float
    current: float
    delta: float
    status: str  # ▲ / ▼ / ─


@dataclass
class QuestionDelta:
    id: str
    type: str
    baseline_passed: bool
    current_passed: bool
    direction: str  # "regression" | "improvement" | "unchanged"


@dataclass
class Baseline:
    baseline_version: str
    baseline_commit: str
    stratified_slice_hash: str
    overall: float
    by_type: dict[str, float]
    per_question: dict[str, dict]  # id -> {type, score}


@dataclass
class Comparison:
    overall_baseline: float
    overall_current: float
    overall_delta: float
    overall_pct_delta: float
    type_deltas: list[TypeDelta] = field(default_factory=list)
    question_deltas: list[QuestionDelta] = field(default_factory=list)
    regressions: list[QuestionDelta] = field(default_factory=list)
    improvements: list[QuestionDelta] = field(default_factory=list)
    gate: GateResult = GateResult.PASS
    gate_reason: str = ""


def load_baseline(path: str | Path) -> Baseline:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    results = raw.get("results", {})
    per_q = {q["id"]: q for q in results.get("per_question", [])}
    return Baseline(
        baseline_version=raw.get("baseline_version", "unknown"),
        baseline_commit=raw.get("baseline_commit", "unknown"),
        stratified_slice_hash=raw.get("stratified_slice_hash", ""),
        overall=float(results.get("overall", 0.0)),
        by_type={k: float(v) for k, v in results.get("by_type", {}).items()},
        per_question=per_q,
    )


def compare_results(
    baseline: Baseline,
    current_overall: float,
    current_by_type: dict[str, float],
    current_per_question: dict[str, dict] | None = None,
) -> Comparison:
    """Compare current run vs baseline and decide the gate."""
    overall_delta = current_overall - baseline.overall
    overall_pct = (overall_delta / baseline.overall * 100) if baseline.overall > 0 else 0.0

    type_deltas: list[TypeDelta] = []
    for q_type, base_score in sorted(baseline.by_type.items()):
        cur = current_by_type.get(q_type, 0.0)
        d = cur - base_score
        arrow = "▲" if d > 0 else ("▼" if d < 0 else "─")
        type_deltas.append(TypeDelta(type=q_type, baseline=base_score, current=cur, delta=d, status=arrow))

    q_deltas: list[QuestionDelta] = []
    if current_per_question:
        for q_id, cur_q in current_per_question.items():
            base_q = baseline.per_question.get(q_id)
            if not base_q:
                continue
            base_passed = bool(base_q.get("score", 0) >= 0.5)
            cur_passed = bool(cur_q.get("score", 0) >= 0.5)
            if cur_passed and not base_passed:
                direction = "improvement"
            elif not cur_passed and base_passed:
                direction = "regression"
            else:
                direction = "unchanged"
            qd = QuestionDelta(
                id=q_id,
                type=base_q.get("type", "unknown"),
                baseline_passed=base_passed,
                current_passed=cur_passed,
                direction=direction,
            )
            q_deltas.append(qd)

    regressions = [q for q in q_deltas if q.direction == "regression"]
    improvements = [q for q in q_deltas if q.direction == "improvement"]

    # Gate decision
    if overall_delta < OVERALL_PASS_THRESHOLD:
        gate = GateResult.FAIL
        reason = f"overall delta {overall_delta:+.3f} below threshold {OVERALL_PASS_THRESHOLD:+.3f}"
    elif any(td.delta < TYPE_WARN_THRESHOLD for td in type_deltas):
        worst = min(type_deltas, key=lambda td: td.delta)
        gate = GateResult.WARN
        reason = f"overall PASS but type '{worst.type}' regressed {worst.delta:+.3f} (below {TYPE_WARN_THRESHOLD:+.3f})"
    else:
        gate = GateResult.PASS
        reason = f"overall delta {overall_delta:+.3f} within threshold"

    return Comparison(
        overall_baseline=baseline.overall,
        overall_current=current_overall,
        overall_delta=overall_delta,
        overall_pct_delta=overall_pct,
        type_deltas=type_deltas,
        question_deltas=q_deltas,
        regressions=regressions,
        improvements=improvements,
        gate=gate,
        gate_reason=reason,
    )
