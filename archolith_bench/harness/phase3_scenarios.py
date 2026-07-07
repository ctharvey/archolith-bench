"""Declarative Phase 3 scenario suite — expands the benchmark beyond the fixed 4-case flow.

`menhir_phase3.run_phase3` is the RICH CORE scenario (idempotence, watermark debounce, re-dirty,
recall) and stays the launch gate. This module adds SCRIPTED scenarios for consumer behaviors the
core flow does not stress, still using the same frozen-producer / user-turn model:

    ambiguous correction     two current Views == 25 -> a bare correction touches NEITHER (abstain)
    currency-worded SUM      "50 dollars and 75 dollars" folds to the same bike_spend = 125 family
    count vs spend           "2 bikes for $125" -> count and SUM do NOT merge (reducer is identity)
    negative correction      "Not 25 anymore, it is 20" -> binds ONLY via the connective rule
    multi-namespace re-run   identical fixtures in two namespaces capture INDEPENDENTLY

A scenario is data: ordered `phases` (each = posts, then one consolidation) plus typed
`assertions` over the accumulated View snapshots. `gate=True` scenarios count toward the suite
verdict; `gate=False` scenarios are CHARACTERIZATION (they document menhir's current behavior on
genuinely-uncertain paths, e.g. whether one sentence yields both a count and a sum) and never
fail the verdict. Multi-namespace scenarios (`namespaces>1`) run the phases independently in N
namespaces and add a cross-namespace independence check.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .menhir_client import Phase3MenhirClient
from .menhir_phase3 import (
    _find_value_in_snapshots,
    _match_view,
    _to_float,
    _view_key,
)

# ---------------------------------------------------------------------------- scenario model


@dataclass(frozen=True)
class Post:
    """One user turn to capture as evidence within a phase."""

    case_id: str
    prompt: str
    reason: str


@dataclass(frozen=True)
class Assertion:
    """A typed check over the accumulated View snapshots.

    kind:
      view_value       - some snapshot has a matching View whose value == value (committed on any pass)
      untouched_value  - the FINAL matching View value == value (e.g. an abstained correction left it)
      superseded       - FINAL matching View value == value AND `prior` is in its superseded history
                         with expired_at set (a correction applied)
      distinct_views   - FINAL snapshot has a matching current View for each (needles, value) in
                         `pairs`, and the matched Views have DISTINCT counter keys (no merge)
      no_view          - no FINAL current View matches `needles` (nothing was written)
    """

    kind: str
    label: str
    needles: tuple[str, ...] = ()
    value: float | None = None
    prior: float | None = None
    pairs: tuple[tuple[tuple[str, ...], float], ...] = ()


@dataclass(frozen=True)
class Scenario:
    """A scripted Phase 3 consumer scenario."""

    scenario_id: str
    description: str
    phases: tuple[tuple[Post, ...], ...]
    assertions: tuple[Assertion, ...]
    gate: bool = True
    namespaces: int = 1


@dataclass
class AssertionResult:
    label: str
    kind: str
    passed: bool
    detail: str = ""


@dataclass
class ScenarioResult:
    scenario_id: str
    description: str
    gate: bool
    passed: bool
    assertions: list[AssertionResult]
    namespaces_used: list[str]
    notes: str = ""


# ---------------------------------------------------------------------------- assertion evaluation


def _eval_assertion(a: Assertion, snapshots: list[dict[str, Any]]) -> AssertionResult:
    final = snapshots[-1] if snapshots else {"views": []}

    if a.kind == "view_value":
        view = _find_value_in_snapshots(snapshots, list(a.needles), a.value)
        return AssertionResult(a.label, a.kind, view is not None,
                               "" if view is not None else f"no View committed value {a.value} across passes")

    if a.kind == "untouched_value":
        view = _match_view(final, list(a.needles))
        val = _to_float(view.get("value")) if view else None
        ok = view is not None and val == a.value
        return AssertionResult(a.label, a.kind, ok,
                               "" if ok else f"final value {val} != untouched-expected {a.value}")

    if a.kind == "superseded":
        view = _match_view(final, list(a.needles))
        cur = _to_float(view.get("value")) if view else None
        superseded = view.get("superseded", []) if view else []
        prior_ok = any(
            _to_float(h.get("value")) == a.prior and h.get("expired_at") for h in superseded
        )
        ok = view is not None and cur == a.value and prior_ok
        if ok:
            detail = ""
        elif view is None:
            detail = "no matching View"
        elif cur != a.value:
            detail = f"current {cur} != {a.value} (not superseded)"
        else:
            detail = f"prior {a.prior} not retained as superseded-with-expired_at"
        return AssertionResult(a.label, a.kind, ok, detail)

    if a.kind == "distinct_views":
        matched_keys: list[tuple[str, str]] = []
        missing: list[float] = []
        for needles, value in a.pairs:
            found = None
            for view in final.get("views", []):
                hay = f"{view.get('subject', '')} {view.get('counter', '')}".lower()
                if any(n.lower() in hay for n in needles) and _to_float(view.get("value")) == value:
                    found = view
                    break
            if found is None:
                missing.append(value)
            else:
                matched_keys.append(_view_key(found))
        distinct = len(set(matched_keys)) == len(matched_keys)
        ok = not missing and distinct and len(matched_keys) == len(a.pairs)
        if ok:
            detail = ""
        elif missing:
            detail = f"values not found as distinct Views: {missing}"
        else:
            detail = f"Views merged (non-distinct keys): {matched_keys}"
        return AssertionResult(a.label, a.kind, ok, detail)

    if a.kind == "no_view":
        stray = _match_view(final, list(a.needles))
        ok = stray is None
        return AssertionResult(a.label, a.kind, ok,
                               "" if ok else f"unexpected View {_view_key(stray)}")

    return AssertionResult(a.label, a.kind, False, f"unknown assertion kind {a.kind!r}")


# ---------------------------------------------------------------------------- runner


def _run_phases_in_namespace(
    client: Phase3MenhirClient, scenario: Scenario, namespace: str, *, k: int
) -> list[dict[str, Any]]:
    """Reset, then for each phase post its evidence (namespace-scoped turn_key) and consolidate.

    Returns the accumulated View snapshots (one per phase, after its consolidation).
    """
    client.reset_phase3(namespace)
    snapshots: list[dict[str, Any]] = []
    for phase in scenario.phases:
        for post in phase:
            client.post_turn_evidence(
                namespace, post.prompt, triage_reason=[post.reason],
                turn_key=f"{namespace}:{post.case_id}",
            )
        client.run_phase3(namespace, k=k)
        snapshots.append(client.fetch_views(namespace))
    return snapshots


def run_scenario(
    client: Phase3MenhirClient,
    scenario: Scenario,
    *,
    base_namespace: str,
    k: int = 3,
    cleanup: bool = True,
) -> ScenarioResult:
    """Run one scripted scenario (single- or multi-namespace) and evaluate its assertions."""
    notes = ""
    if scenario.namespaces <= 1:
        ns = f"{base_namespace}-{scenario.scenario_id}"
        namespaces_used = [ns]
        snapshots = _run_phases_in_namespace(client, scenario, ns, k=k)
        results = [_eval_assertion(a, snapshots) for a in scenario.assertions]
        if cleanup:
            client.reset_phase3(ns)
    else:
        # Multi-namespace: run the SAME phases independently in N namespaces, assert each passes,
        # then cross-check independence (each namespace's current-View count is self-contained).
        namespaces_used = [f"{base_namespace}-{scenario.scenario_id}-{i}" for i in range(scenario.namespaces)]
        per_ns_snapshots = [_run_phases_in_namespace(client, scenario, ns, k=k) for ns in namespaces_used]
        results = []
        for i, snaps in enumerate(per_ns_snapshots):
            for a in scenario.assertions:
                r = _eval_assertion(a, snaps)
                r.label = f"[{namespaces_used[i]}] {r.label}"
                results.append(r)
        # Independence: every namespace independently produced its own Views (non-empty, equal
        # counts), i.e. no cross-namespace leakage or shared state.
        counts = [len(s[-1].get("views", [])) for s in per_ns_snapshots]
        independent = all(c == counts[0] and c > 0 for c in counts)
        results.append(AssertionResult(
            "namespaces captured independently", "independence", independent,
            "" if independent else f"per-namespace View counts differ or empty: {counts}",
        ))
        notes = f"per-namespace current-View counts: {counts}"
        if cleanup:
            for ns in namespaces_used:
                client.reset_phase3(ns)

    passed = all(r.passed for r in results)
    return ScenarioResult(
        scenario_id=scenario.scenario_id,
        description=scenario.description,
        gate=scenario.gate,
        passed=passed,
        assertions=results,
        namespaces_used=namespaces_used,
        notes=notes,
    )


def run_scenario_suite(
    client: Phase3MenhirClient,
    *,
    scenarios: list[Scenario] | None = None,
    base_namespace: str,
    k: int = 3,
    cleanup: bool = True,
) -> list[ScenarioResult]:
    """Run every scenario and return per-scenario results (gate scenarios drive the suite verdict)."""
    scenarios = scenarios if scenarios is not None else default_scenarios()
    return [run_scenario(client, s, base_namespace=base_namespace, k=k, cleanup=cleanup)
            for s in scenarios]


def suite_verdict(results: list[ScenarioResult]) -> bool:
    """The suite passes iff every GATE scenario passed (characterization scenarios never gate)."""
    return all(r.passed for r in results if r.gate)


def scenario_result_to_dict(r: ScenarioResult) -> dict[str, Any]:
    return asdict(r)


# ---------------------------------------------------------------------------- fixture families

_MOVIES = ("movie", "watch")
_BOOKS = ("book", "read")
_BIKE = ("bike",)


def default_scenarios() -> list[Scenario]:
    """The expanded fixture families (consumer stress cases beyond the core flow)."""
    return [
        # 1. Ambiguous correction: two current Views == 25 on different subjects; a bare
        #    "20, not 25" cannot pick a unique target, so it must touch NEITHER (F2 abstain).
        Scenario(
            scenario_id="ambiguous-correction",
            description="two Views == 25 -> bare correction abstains, touches neither",
            phases=(
                (
                    Post("amb-movies", "I have 25 movies on my watch list.", "stated_measure"),
                    Post("amb-books", "I read 25 books this year.", "stated_measure"),
                ),
                (Post("amb-corr", "Actually it is 20, not 25.", "correction"),),
            ),
            assertions=(
                Assertion("view_value", "movies committed 25", _MOVIES, 25.0),
                Assertion("view_value", "books committed 25", _BOOKS, 25.0),
                Assertion("untouched_value", "movies still 25 after ambiguous correction", _MOVIES, 25.0),
                Assertion("untouched_value", "books still 25 after ambiguous correction", _BOOKS, 25.0),
            ),
            gate=True,
        ),
        # 2. Currency-worded SUM: worded dollars fold to the same bike_spend = 125 family.
        Scenario(
            scenario_id="currency-worded-sum",
            description="'50 dollars and 75 dollars' folds to bike_spend = 125",
            phases=((Post("cur-bike", "I spent 50 dollars and 75 dollars on bikes.", "fold_sum"),),),
            assertions=(Assertion("view_value", "bike spend folds to 125", _BIKE, 125.0),),
            gate=True,
        ),
        # 3. Count vs spend, same noun: one sentence carries both a COUNT (2) and a SUM (125);
        #    reducer is part of View identity so they must NOT merge. Whether menhir extracts BOTH
        #    from one sentence is uncertain, so this is CHARACTERIZATION (documents current behavior).
        Scenario(
            scenario_id="count-vs-spend",
            description="'2 bikes for $125' -> count(2) and spend(125) do not merge",
            phases=((Post("cvs-bike", "I bought 2 bikes for $125 total.", "fold_sum"),),),
            assertions=(
                Assertion("distinct_views", "count 2 and spend 125 are distinct Views", pairs=(
                    (_BIKE, 2.0), (_BIKE, 125.0),
                )),
            ),
            gate=False,
        ),
        # 4. Negative correction: "Not 25 anymore, it is 20" binds only if the connective rule
        #    recognizes this phrasing. Whether it does is exactly what we are measuring, so this is
        #    CHARACTERIZATION, not a gate.
        Scenario(
            scenario_id="negative-correction",
            description="'Not 25 anymore, it is 20' supersedes only via the connective rule",
            phases=(
                (Post("neg-movies", "I have 25 movies on my watch list.", "stated_measure"),),
                (Post("neg-corr", "Not 25 anymore, it is 20.", "correction"),),
            ),
            assertions=(
                Assertion("superseded", "movies 25 -> 20 (if connective recognized)", _MOVIES, 20.0, 25.0),
            ),
            gate=False,
        ),
        # 5. Multi-namespace re-run: identical fixtures in two namespaces capture independently
        #    (the namespace-scoped turn_key regression, exercised across silos).
        Scenario(
            scenario_id="multi-namespace",
            description="identical fixtures in two namespaces capture independently",
            phases=((Post("mns-movies", "I have 25 movies on my watch list.", "stated_measure"),),),
            assertions=(Assertion("view_value", "movies committed 25", _MOVIES, 25.0),),
            gate=True,
            namespaces=2,
        ),
    ]
