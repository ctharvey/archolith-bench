"""R3 rung E bench — session-replay ladder for the retrieval exhaustion policy.

Unlike the currentness ladder (static belief items), exhaustion is session-local, so the
fixture is a SESSION TRACE: an ordered list of turns, each retrieving some memory ids and
optionally producing a progress event (test passed, failure changed, patch accepted, ...).
The runner replays the trace, maintaining per-item retrievals_since_progress (reset for all
items at the end of a turn that made progress), and applies the menhir exhaustion policy.

Consumes menhir.domain.exhaustion (the real policy, not reimplemented).

Conditions:
    A_no_penalty   baseline: every retrieval is injected into context (the loop poisons).
    E_exhaustion   apply the exhaustion policy: SUPPRESS drops a looping injection.

Metrics:
    loop_injection_rate      loop-trap items injected while in an unproductive loop /
                             total loop-trap retrievals  (LOWER better — the loop poison)
    productive_retention     non-trap retrievals still injected / non-trap retrievals
                             (HIGHER better — must not over-suppress useful memory)
    exempt_retention         exempt-item retrievals still injected / exempt retrievals
                             (must stay 1.0 — exemptions are inviolable)

Win gate: E cuts loop_injection_rate vs A_no_penalty without dropping productive_retention
or exempt_retention below 1.0.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from menhir.domain.exhaustion import (
    ExemptReason,
    ExhaustionDecision,
    RetrievalStats,
    exhaustion_decision,
)

CONDITIONS: tuple[str, ...] = ("A_no_penalty", "E_exhaustion")
BASELINE_CONDITION = "A_no_penalty"
_SUPPRESS_AT = 4  # matches the menhir default; the loop trap is pulled enough to cross it


@dataclass
class SessionItem:
    id: str
    is_loop_trap: bool = False         # unproductive belief that should be suppressed once looping
    exempt_reason: str | None = None   # current_task_goal / active_error_log / ... -> never penalized

    @classmethod
    def from_dict(cls, d: dict) -> "SessionItem":
        return cls(id=str(d["id"]), is_loop_trap=bool(d.get("is_loop_trap", False)), exempt_reason=d.get("exempt_reason"))


@dataclass
class SessionTurn:
    retrieved: list[str] = field(default_factory=list)
    progress: bool = False

    @classmethod
    def from_dict(cls, d: dict) -> "SessionTurn":
        return cls(retrieved=[str(x) for x in d.get("retrieved", [])], progress=bool(d.get("progress", False)))


@dataclass
class SessionFixture:
    name: str
    description: str
    items: list[SessionItem] = field(default_factory=list)
    turns: list[SessionTurn] = field(default_factory=list)

    @property
    def items_by_id(self) -> dict[str, SessionItem]:
        return {i.id: i for i in self.items}

    @classmethod
    def from_dict(cls, d: dict) -> "SessionFixture":
        return cls(
            name=d.get("name", "unnamed"),
            description=d.get("description", ""),
            items=[SessionItem.from_dict(i) for i in d.get("items", [])],
            turns=[SessionTurn.from_dict(t) for t in d.get("turns", [])],
        )

    @classmethod
    def from_file(cls, path: str | Path) -> "SessionFixture":
        with open(path) as h:
            return cls.from_dict(json.load(h))


@dataclass
class ConditionResult:
    condition: str
    metrics: dict[str, float]


def _exempt(reason: str | None) -> ExemptReason | None:
    if not reason:
        return None
    try:
        return ExemptReason(reason)
    except ValueError:
        return None


class ExhaustionSessionRunner:
    """Replay a session trace under each condition and score loop suppression."""

    def __init__(self, fixture: SessionFixture, suppress_at: int = _SUPPRESS_AT) -> None:
        self.fixture = fixture
        self.suppress_at = suppress_at
        self.by_id = fixture.items_by_id

    def _replay(self, condition: str) -> dict[str, float]:
        since_progress: dict[str, int] = {i.id: 0 for i in self.fixture.items}
        total_count: dict[str, int] = {i.id: 0 for i in self.fixture.items}

        loop_trap_retrievals = 0
        loop_injections = 0
        productive_retrievals = 0
        productive_injected = 0
        exempt_retrievals = 0
        exempt_injected = 0

        for turn in self.fixture.turns:
            for rid in turn.retrieved:
                item = self.by_id.get(rid)
                if item is None:
                    continue
                total_count[rid] += 1
                since_progress[rid] += 1
                stats = RetrievalStats(
                    session_retrieval_count=total_count[rid],
                    retrievals_since_progress=since_progress[rid],
                    exempt_reason=_exempt(item.exempt_reason),
                )
                if condition == "A_no_penalty":
                    injected = True
                else:  # E_exhaustion
                    injected = exhaustion_decision(stats, suppress_at=self.suppress_at) is not ExhaustionDecision.SUPPRESS

                if item.exempt_reason:
                    exempt_retrievals += 1
                    exempt_injected += int(injected)
                elif item.is_loop_trap:
                    loop_trap_retrievals += 1
                    # a loop injection = a trap injected while it is in an unproductive loop
                    if injected and since_progress[rid] >= self.suppress_at:
                        loop_injections += 1
                else:
                    productive_retrievals += 1
                    productive_injected += int(injected)

            if turn.progress:
                since_progress = {k: 0 for k in since_progress}

        return {
            "loop_injection_rate": round(loop_injections / loop_trap_retrievals, 4) if loop_trap_retrievals else 0.0,
            "productive_retention": round(productive_injected / productive_retrievals, 4) if productive_retrievals else 1.0,
            "exempt_retention": round(exempt_injected / exempt_retrievals, 4) if exempt_retrievals else 1.0,
        }

    def run(self) -> dict:
        results = {c: ConditionResult(c, self._replay(c)) for c in CONDITIONS}
        gate = evaluate_win_gate(results)
        return {
            "fixture": self.fixture.name,
            "description": self.fixture.description,
            "config": {"suppress_at": self.suppress_at, "n_items": len(self.fixture.items), "n_turns": len(self.fixture.turns), "conditions": list(CONDITIONS)},
            "conditions": {c: {"metrics": r.metrics} for c, r in results.items()},
            "win_gate": gate,
        }


def evaluate_win_gate(results: dict[str, ConditionResult]) -> dict:
    """E graduates if it cuts loop_injection_rate vs A without dropping productive or
    exempt retention below 1.0 (no over-suppression of useful/exempt memory)."""
    if BASELINE_CONDITION not in results or "E_exhaustion" not in results:
        return {"graduates": False, "reason": "missing baseline or E condition"}
    base = results[BASELINE_CONDITION].metrics
    e = results["E_exhaustion"].metrics
    loop_cut = round(base["loop_injection_rate"] - e["loop_injection_rate"], 4)
    graduates = loop_cut > 0 and e["productive_retention"] >= 1.0 and e["exempt_retention"] >= 1.0
    return {
        "graduates": graduates,
        "loop_injection_cut": loop_cut,
        "productive_retention": e["productive_retention"],
        "exempt_retention": e["exempt_retention"],
        "baseline_loop_injection_rate": base["loop_injection_rate"],
        "e_loop_injection_rate": e["loop_injection_rate"],
    }
