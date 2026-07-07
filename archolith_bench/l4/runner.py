"""L4 benchmark runner — does surfacing institutional artifacts change the brief? (bench-first)

Commit 5 of the L4 artifact loop. For each task it builds a ColdStartBrief under two
conditions and scores it deterministically:

    without_l4   ordinary memory only (no institutional artifacts) — the pre-L4 world
    with_l4      the full corpus, institutional artifacts included

The headline the plan predicts: the TRUSTED Failure artifact flips
`failed_approach_surfaced` and `first_action_quality` from 0 to 1. The other metrics
guard the invariants while it does so — TRUSTED brief items must carry evidence, and a
superseded artifact must read historical, never as a current fact.

No live agent and no LLM: the brief IS the agent's recall, scored as a proxy for "did
the agent avoid the known dead end". Pure-Python, deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .brief import ColdStartBriefV0, build_brief
from .memory_oracle import MemoryOracle
from .models import Artifact, ArtifactFixture

CONDITIONS = ("without_l4", "with_l4")

METRIC_KEYS = (
    "failed_approach_surfaced",
    "evidence_present",
    "stale_or_conflict_flagged",
    "decision_accuracy_per_token",
    "first_action_quality",
)


@dataclass
class L4Task:
    id: str
    text: str
    anchors: list[str] = field(default_factory=list)
    gold_failure: str | None = None
    gold_decision: str | None = None
    gold_historical: str | None = None
    baseline_ids: list[str] = field(default_factory=list)  # artifacts visible without the L4 loop

    @classmethod
    def from_dict(cls, data: dict) -> "L4Task":
        return cls(
            id=str(data["id"]),
            text=str(data.get("text", "")),
            anchors=[str(a) for a in data.get("anchors", [])],
            gold_failure=data.get("gold_failure"),
            gold_decision=data.get("gold_decision"),
            gold_historical=data.get("gold_historical"),
            baseline_ids=[str(i) for i in data.get("baseline_ids", [])],
        )

    @property
    def gold_relevant(self) -> set[str]:
        return {i for i in (self.gold_failure, self.gold_decision, self.gold_historical) if i}


def _ids(items) -> set[str]:
    return {i.artifact_id for i in items}


def score_brief(brief: ColdStartBriefV0, task: L4Task) -> dict:
    """Score a brief against a task's gold set. Every metric is in [0, 1] except the
    per-token ratio, which is non-negative and rises as relevant facts are surfaced cheaply."""
    failed = _ids(brief.failed_approaches)
    fact_ids = _ids(brief.facts())
    stale_ids = _ids(brief.stale_or_contradicted)

    failed_approach_surfaced = 1.0 if (task.gold_failure and task.gold_failure in failed) else 0.0

    # invariant audit: every FACT-bucket (TRUSTED, current) item must carry evidence,
    # and no CANDIDATE/historical id may have leaked into a fact bucket.
    trusted_items = brief.facts()
    evidence_present = 1.0 if all(it.evidence_refs for it in trusted_items) else 0.0

    # the superseded gold must be flagged historical and must NOT appear as a current fact.
    if task.gold_historical:
        flagged = task.gold_historical in stale_ids and task.gold_historical not in fact_ids
        stale_or_conflict_flagged = 1.0 if flagged else 0.0
    else:
        stale_or_conflict_flagged = 1.0  # nothing to flag — vacuously clean

    surfaced_relevant = len(task.gold_relevant & (fact_ids | stale_ids | _ids(brief.hypotheses)))
    tokens = brief.token_count()
    decision_accuracy_per_token = round(surfaced_relevant / tokens, 4) if tokens else 0.0

    rec = brief.recommended_first_action or ""
    references_corrective = bool(task.gold_decision) and task.gold_decision in rec
    first_action_quality = 1.0 if references_corrective else 0.0

    return {
        "failed_approach_surfaced": failed_approach_surfaced,
        "evidence_present": evidence_present,
        "stale_or_conflict_flagged": stale_or_conflict_flagged,
        "decision_accuracy_per_token": decision_accuracy_per_token,
        "first_action_quality": first_action_quality,
    }


def _corpus_for(condition: str, artifacts: list[Artifact], task: L4Task) -> list[Artifact]:
    if condition == "with_l4":
        return artifacts
    # without_l4: only the ordinary memories the agent had before institutional capture.
    baseline = set(task.baseline_ids)
    return [a for a in artifacts if a.id in baseline]


def run_task(artifacts: list[Artifact], task: L4Task) -> dict:
    conditions: dict[str, dict] = {}
    for cond in CONDITIONS:
        brief = build_brief(
            task=task.text,
            anchors=task.anchors,
            oracle=MemoryOracle(_corpus_for(cond, artifacts, task)),
        )
        conditions[cond] = {
            "metrics": score_brief(brief, task),
            "token_count": brief.token_count(),
            "brief": brief.to_dict(),
        }
    return {"task": task.id, "text": task.text, "conditions": conditions}


def run_l4_benchmark(fixture: ArtifactFixture) -> dict:
    tasks = [L4Task.from_dict(t) for t in fixture.tasks]
    return {
        "fixture": fixture.name,
        "tasks": [run_task(fixture.artifacts, t) for t in tasks],
    }
