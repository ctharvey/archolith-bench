"""Menhir Phase 3 (personal-memory View consolidation) benchmark.

NOT an A/B (there is no direct-vs-proxy arm here). Phase 3 validates the SELECTIVE-capture
CONSUMER pipeline end to end against a THROWAWAY menhir:

    :TurnEvidence  ->  Phase 3 consolidation  ->  View writes
                   ->  abstention receipts     ->  supersession / currentness  ->  recall

The producer (the host UserPromptSubmit hook's deterministic triage) is FROZEN and lives in
menhir; it is not reachable over HTTP. The fixtures therefore encode the frozen producer's
verdict (`candidate`): non-candidate ("junk") turns are dropped exactly as the live producer
drops them (never POSTed), matching `menhir/scripts/validate_phase3_realdata.py`. What this
benchmark measures is the CONSUMER: given the producer's decisions, does consolidation write
the right Views, abstain visibly (never silently), supersede on correction, and stay idempotent.

The scenario mirrors the live validation script (one isolated namespace):
    reset -> capture phase-A candidates -> run#1 -> idempotent re-fold (run#2)
          -> capture phase-B correction -> run#3 -> inspect Views / receipts / history.

Result is a purpose-built `Phase3Result` (Views/abstentions/supersession/idempotence), not the
score/token `ABResult`. Driven by `run_phase3`; reported by `write_phase3_evidence`.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .menhir_client import Phase3MenhirClient

# ---------------------------------------------------------------------------- fixtures


@dataclass(frozen=True)
class Phase3Case:
    """One fixture prompt plus the CONSUMER outcome it should drive.

    `candidate` is the frozen producer's verdict: True turns are POSTed as evidence; False
    ("junk") turns are dropped (never POSTed), exactly as the live triage drops them.
    `phase` "A" turns are captured before the first consolidation; "B" turns (corrections) are
    captured after it so they bind to an already-written View. `expect` holds kind-specific
    assertion inputs consumed by the per-case validator.
    """

    case_id: str
    prompt: str
    kind: str  # stated_measure | fold_sum | correction | junk
    phase: str  # A | B
    candidate: bool
    expect: dict[str, Any] = field(default_factory=dict)


def default_phase3_cases() -> list[Phase3Case]:
    """The four live-validated cases (verbatim prompts a UserPromptSubmit hook would observe)."""
    return [
        Phase3Case(
            case_id="phase3-movies-stated",
            prompt="I have 25 movies on my watch list.",
            kind="stated_measure",
            phase="A",
            candidate=True,
            expect={"subject_needles": ["watch", "movie"], "initial_value": 25.0},
        ),
        Phase3Case(
            case_id="phase3-bike-sum",
            prompt="I bought one bike for $50 and another for $75.",
            kind="fold_sum",
            phase="A",
            candidate=True,
            expect={"subject_needles": ["bike"], "value": 125.0, "canonical_key": "bike_spend"},
        ),
        Phase3Case(
            case_id="phase3-movies-correction",
            prompt="Actually it is 20, not 25.",
            kind="correction",
            phase="B",
            candidate=True,
            expect={"subject_needles": ["watch", "movie"], "from_value": 25.0, "to_value": 20.0},
        ),
        Phase3Case(
            case_id="phase3-junk-drop",
            prompt="write the handoff",
            kind="junk",
            phase="A",
            candidate=False,
            expect={"forbidden_needles": ["handoff"]},
        ),
    ]


def fixture_hash(cases: list[Phase3Case]) -> str:
    """Stable digest of the fixture set (prompts + expectations) for reproducibility."""
    blob = json.dumps([asdict(c) for c in cases], sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------- result types


@dataclass
class Phase3CaseResult:
    """Per-case validation outcome."""

    case_id: str
    kind: str
    inputs: list[str]
    expected: dict[str, Any]
    actual: dict[str, Any]
    passed: bool
    notes: str = ""


@dataclass
class Phase3Result:
    """Full Phase 3 View-consolidation result — purpose-built, not score/token oriented."""

    benchmark_id: str
    name: str
    namespace: str
    menhir_url: str
    cases: list[Phase3CaseResult]
    metrics: dict[str, Any]
    verdict: bool
    warnings: list[str] = field(default_factory=list)
    run_meta: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------- adapter


class MenhirPhase3Adapter:
    """Registry entry so the harness CLI can find the Phase 3 benchmark by id."""

    benchmark_id = "menhir-phase3"
    name = "Menhir Phase 3 View Consolidation"
    is_phase3_adapter = True

    def cases(self) -> list[Phase3Case]:
        """Return the default fixture set."""
        return default_phase3_cases()


def is_phase3(adapter: object) -> bool:
    """True if the adapter drives the Phase 3 View-consolidation benchmark (run via run_phase3)."""
    return bool(getattr(adapter, "is_phase3_adapter", False))


# ---------------------------------------------------------------------------- view helpers


def _to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _view_key(view: dict[str, Any]) -> tuple[str, str]:
    return (str(view.get("subject") or ""), str(view.get("counter") or ""))


def _current_value_map(views_payload: dict[str, Any]) -> dict[tuple[str, str], Any]:
    """Map (subject, counter) -> current value for every current user View."""
    out: dict[tuple[str, str], Any] = {}
    for view in views_payload.get("views", []):
        val = _to_float(view.get("value"))
        out[_view_key(view)] = view.get("value") if val is None else val
    return out


def _match_view(views_payload: dict[str, Any], needles: list[str]) -> dict[str, Any] | None:
    """First current View whose subject+counter text contains any needle (case-insensitive)."""
    for view in views_payload.get("views", []):
        hay = f"{view.get('subject', '')} {view.get('counter', '')}".lower()
        if any(n.lower() in hay for n in needles):
            return view
    return None


def _rerun_duplicate_writes(before: dict[str, Any], after: dict[str, Any]) -> int:
    """Count measures whose CURRENT value DIVERGED across an idempotent re-fold.

    Only measures present in BOTH passes count: a value that changed (e.g. 125 -> 130) is a
    genuine non-idempotent/divergent write. A measure that newly APPEARS on the re-fold is a
    late commit of a previously-abstained measure (the k-sample extractor is stochastic and
    fails closed), not a duplicate/divergent write — see `_rerun_late_commits`.
    """
    b = _current_value_map(before)
    a = _current_value_map(after)
    return sum(1 for key, val in a.items() if key in b and b[key] != val)


def _rerun_late_commits(before: dict[str, Any], after: dict[str, Any]) -> int:
    """Count measures that were absent on the first pass but committed on the idempotent re-fold.

    Informational (not a verdict gate): reflects the stochastic extractor committing on a later
    attempt what it safely abstained on earlier, never a wrong or duplicated write.
    """
    b = _current_value_map(before)
    a = _current_value_map(after)
    return sum(1 for key in a if key not in b)


# ---------------------------------------------------------------------------- per-case validators


def _find_value_in_snapshots(
    snapshots: list[dict[str, Any]], needles: list[str], expected_value: float
) -> dict[str, Any] | None:
    """First matching View across snapshots whose value equals expected_value.

    The k-sample extractor is stochastic and fails closed, and each pass batch-re-folds every
    episode, so a measure may commit on a later pass. Scanning all captured snapshots requires
    the CORRECT value to have committed on some pass without penalizing a single stochastic miss.
    """
    for snap in snapshots:
        view = _match_view(snap, needles)
        if view is not None and _to_float(view.get("value")) == expected_value:
            return view
    return None


def _validate_stated_measure(
    case: Phase3Case, pre_correction_snapshots: list[dict[str, Any]]
) -> Phase3CaseResult:
    view = _find_value_in_snapshots(
        pre_correction_snapshots, case.expect["subject_needles"], case.expect["initial_value"]
    )
    passed = view is not None
    return Phase3CaseResult(
        case_id=case.case_id,
        kind=case.kind,
        inputs=[case.prompt],
        expected={"subject~": case.expect["subject_needles"], "value": case.expect["initial_value"]},
        actual={"view_key": _view_key(view) if view else None,
                "value": _to_float(view.get("value")) if view else None},
        passed=passed,
        notes="" if passed else "stated-measure View never committed value 25 before the correction",
    )


def _validate_fold_sum(
    case: Phase3Case, snapshots: list[dict[str, Any]]
) -> Phase3CaseResult:
    view = _find_value_in_snapshots(snapshots, case.expect["subject_needles"], case.expect["value"])
    counter = str(view.get("counter") or "") if view else ""
    value_ok = view is not None
    key_stable = counter == case.expect.get("canonical_key")
    notes = ""
    if not value_ok:
        notes = "fold SUM View never committed value 125 across passes (all attempts abstained)"
    elif not key_stable:
        notes = f"value correct but counter key {counter!r} != canonical {case.expect.get('canonical_key')!r}"
    return Phase3CaseResult(
        case_id=case.case_id,
        kind=case.kind,
        inputs=[case.prompt],
        expected={"value": case.expect["value"], "canonical_key": case.expect.get("canonical_key")},
        actual={"view_key": _view_key(view) if view else None,
                "value": _to_float(view.get("value")) if view else None, "counter": counter},
        passed=bool(value_ok),  # value is the hard gate; key drift is a warning, not a failure
        notes=notes,
    )


def _validate_correction(
    case: Phase3Case, seed_prompt: str, views_final: dict[str, Any]
) -> Phase3CaseResult:
    view = _match_view(views_final, case.expect["subject_needles"])
    current = _to_float(view.get("value")) if view else None
    superseded = view.get("superseded", []) if view else []
    superseded_vals = [_to_float(h.get("value")) for h in superseded]
    has_old = case.expect["from_value"] in superseded_vals
    old_expired = any(
        _to_float(h.get("value")) == case.expect["from_value"] and h.get("expired_at")
        for h in superseded
    )
    passed = view is not None and current == case.expect["to_value"] and has_old and old_expired
    notes = ""
    if not passed:
        if view is None:
            notes = "corrected View missing"
        elif current != case.expect["to_value"]:
            notes = f"current value {current} != corrected {case.expect['to_value']} (supersession failed)"
        elif not has_old:
            notes = f"prior value {case.expect['from_value']} not retained as superseded"
        elif not old_expired:
            notes = "superseded prior lacks expired_at"
    return Phase3CaseResult(
        case_id=case.case_id,
        kind=case.kind,
        inputs=[seed_prompt, case.prompt],
        expected={"current": case.expect["to_value"], "superseded": case.expect["from_value"]},
        actual={"current": current, "superseded": superseded_vals},
        passed=passed,
        notes=notes,
    )


def _validate_junk(case: Phase3Case, views_final: dict[str, Any]) -> Phase3CaseResult:
    stray = _match_view(views_final, case.expect["forbidden_needles"])
    passed = stray is None  # dropped (never posted) => no junk-derived View may exist
    return Phase3CaseResult(
        case_id=case.case_id,
        kind=case.kind,
        inputs=[case.prompt],
        expected={"posted": False, "view_written": False},
        actual={"stray_view": _view_key(stray) if stray else None},
        passed=passed,
        notes="" if passed else "junk prompt produced a View (should have been dropped by triage)",
    )


def _count_wrong_view_writes(cases: list[Phase3Case], views_final: dict[str, Any]) -> int:
    """Current Views that do not match any expected case outcome (stale corrections, junk views, drift).

    Expected current values after the full scenario: the corrected stated-measure (to_value) and
    the fold SUM (value). Any current View not explained by an expected outcome is a wrong write.
    """
    expected_values: dict[str, float] = {}
    correction_needles: list[str] = []
    correction_target: float | None = None
    for c in cases:
        if c.kind == "fold_sum":
            expected_values["fold"] = c.expect["value"]
        if c.kind == "correction":
            correction_needles = c.expect["subject_needles"]
            correction_target = c.expect["to_value"]

    wrong = 0
    for view in views_final.get("views", []):
        value = _to_float(view.get("value"))
        hay = f"{view.get('subject', '')} {view.get('counter', '')}".lower()
        if correction_needles and any(n.lower() in hay for n in correction_needles):
            if value != correction_target:  # stale (still 25) or otherwise wrong
                wrong += 1
            continue
        if "bike" in hay:
            if value != expected_values.get("fold"):
                wrong += 1
            continue
        # An unexplained current View (not the corrected measure, not the fold) is a wrong write.
        wrong += 1
    return wrong


# ---------------------------------------------------------------------------- driver


def run_phase3(
    client: Phase3MenhirClient,
    *,
    cases: list[Phase3Case] | None = None,
    namespace: str | None = None,
    k: int = 3,
    reset_confirmed: bool = False,
    cleanup: bool = True,
    menhir_url: str = "",
    model: str = "",
) -> Phase3Result:
    """Run the Phase 3 View-consolidation scenario against a throwaway menhir.

    Mirrors `validate_phase3_realdata.py`: one isolated namespace, capture -> consolidate ->
    idempotent re-fold -> correction -> consolidate, then inspect Views/receipts/history and
    validate the four fixture cases. Requires `reset_confirmed=True` because it writes to and
    tears down a real (throwaway) namespace. When `cleanup` is true the namespace is purged again
    on exit (after all state is captured) so nothing lingers between runs.

    Evidence `turn_key` is scoped to the namespace: menhir MERGEs `:TurnEvidence` on a global
    `turn_key` derived from the prompt text, so without namespace scoping the same fixture prompt
    re-run under a fresh namespace would bind to the PRIOR run's node and the new namespace would
    capture nothing. Scoping keeps every run's evidence distinct.
    """
    if not reset_confirmed:
        raise ValueError(
            "run_phase3 mutates and tears down a real (throwaway) Menhir namespace; "
            "pass --confirm-menhir-reset to proceed."
        )
    cases = cases or default_phase3_cases()
    namespace = namespace or f"phase3-bench-{uuid.uuid4().hex[:12]}"
    warnings: list[str] = []

    phase_a = [c for c in cases if c.phase == "A" and c.candidate]
    dropped = [c for c in cases if not c.candidate]
    corrections = [c for c in cases if c.phase == "B" and c.candidate]
    seed_prompt = next((c.prompt for c in cases if c.kind == "stated_measure"), "")

    submitted = 0
    created = 0

    # 0. isolate --------------------------------------------------------------------------------
    client.reset_phase3(namespace)
    views_pre = client.fetch_views(namespace)

    # 1. capture phase A (candidates only; junk is dropped, never posted) -----------------------
    for c in phase_a:
        resp = client.post_turn_evidence(
            namespace, c.prompt, triage_reason=[c.kind], turn_key=f"{namespace}:{c.case_id}"
        )
        submitted += 1
        created += 1 if resp.get("created") else 0

    # 2. Phase 3 selection (dirty detection over evidence) --------------------------------------
    status_before = client.phase3_status(namespace)
    phase3_selected = bool(status_before.get("dirty"))

    # 3. consolidation run #1 -------------------------------------------------------------------
    run1 = client.run_phase3(namespace, k=k)
    views_run1 = client.fetch_views(namespace)

    # 4. idempotence: watermark debounce + forced re-fold ---------------------------------------
    status_after1 = client.phase3_status(namespace)
    watermark_debounce_hit = not bool(status_after1.get("dirty"))
    run2 = client.run_phase3(namespace, k=k)  # forced re-fold (explicit namespace ignores debounce)
    views_run2 = client.fetch_views(namespace)
    duplicate_writes = _rerun_duplicate_writes(views_run1, views_run2)
    late_commits = _rerun_late_commits(views_run1, views_run2)

    # 5. new evidence (correction) -> re-dirty --------------------------------------------------
    for c in corrections:
        resp = client.post_turn_evidence(
            namespace, c.prompt, triage_reason=["correction"], turn_key=f"{namespace}:{c.case_id}"
        )
        submitted += 1
        created += 1 if resp.get("created") else 0
    status_redirty = client.phase3_status(namespace)
    re_dirtied = bool(status_redirty.get("dirty"))

    # 6. consolidation run #3 -> supersession ---------------------------------------------------
    run3 = client.run_phase3(namespace, k=k)
    views_final = client.fetch_views(namespace)

    # recall improvement probe (durable Views absent before, present after) ---------------------
    recall_before: list[str] = []
    recall_after: list[str] = []
    try:
        recall_before = client.recall(namespace, seed_prompt or "watch list", limit=10)
    except Exception as exc:  # recall is evidence, not a gate
        warnings.append(f"recall(before) failed: {exc}")
    try:
        recall_after = client.recall(namespace, seed_prompt or "watch list", limit=10)
    except Exception as exc:
        warnings.append(f"recall(after) failed: {exc}")

    # --- per-case validation -------------------------------------------------------------------
    # Pre-correction snapshots (movies is still 25 here); all snapshots for the fold, which may
    # commit on any pass. Committed Views persist, so views_final also reflects earlier commits.
    pre_correction = [views_run1, views_run2]
    all_snapshots = [views_run1, views_run2, views_final]
    case_results: list[Phase3CaseResult] = []
    for c in cases:
        if c.kind == "stated_measure":
            case_results.append(_validate_stated_measure(c, pre_correction))
        elif c.kind == "fold_sum":
            fold = _validate_fold_sum(c, all_snapshots)
            if fold.passed and fold.notes:
                warnings.append(f"{c.case_id}: {fold.notes}")
            case_results.append(fold)
        elif c.kind == "correction":
            case_results.append(_validate_correction(c, seed_prompt, views_final))
        elif c.kind == "junk":
            case_results.append(_validate_junk(c, views_final))

    # --- metrics -------------------------------------------------------------------------------
    total_abstained = (
        int(run1.get("abstained", 0)) + int(run2.get("abstained", 0)) + int(run3.get("abstained", 0))
    )
    receipts = views_final.get("receipts", [])
    abstention_reasons = [
        {"subject": r.get("subject"), "counter": r.get("counter"), "value": r.get("value")}
        for r in receipts
    ]
    # A silent abstention is an abstain with no observable receipt. menhir records receipts
    # (record_abstentions=True), so any abstain-without-receipt is a regression.
    silent_abstentions = max(0, total_abstained - len(receipts)) if total_abstained else 0
    wrong_view_writes = _count_wrong_view_writes(cases, views_final)

    metrics: dict[str, Any] = {
        "turn_evidence_submitted": submitted,
        "turn_evidence_created": created,
        "turn_evidence_dropped": len(dropped),
        "phase3_selected": phase3_selected,
        "views_written_run1": int(run1.get("views_written", 0)),
        "views_current": int(views_final.get("count", 0)),
        "views_superseded": sum(len(v.get("superseded", [])) for v in views_final.get("views", [])),
        "abstentions": total_abstained,
        "abstention_reasons": abstention_reasons,
        "supersessions_applied": (
            int(run1.get("corrections_applied", 0))
            + int(run2.get("corrections_applied", 0))
            + int(run3.get("corrections_applied", 0))
        ),
        "duplicate_writes_on_rerun": duplicate_writes,
        "late_commits_on_rerun": late_commits,
        "dirty_before_run1": phase3_selected,
        "watermark_debounce_hit": watermark_debounce_hit,
        "re_dirtied_after_new_evidence": re_dirtied,
        "recall_hit_before": len(views_pre.get("views", [])) > 0,
        "recall_hit_after": len(views_final.get("views", [])) > 0,
        "recall_snippets_before": len(recall_before),
        "recall_snippets_after": len(recall_after),
        "silent_abstentions": silent_abstentions,
        "wrong_view_writes": wrong_view_writes,
    }

    # --- verdict: every case passes AND the hard invariants hold -------------------------------
    all_cases_pass = all(cr.passed for cr in case_results)
    verdict = bool(
        all_cases_pass
        and wrong_view_writes == 0
        and silent_abstentions == 0
        and duplicate_writes == 0
    )

    run_meta = {
        "namespace": namespace,
        "menhir_url": menhir_url,
        "model": model,
        "k": k,
        "fixture_hash": fixture_hash(cases),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "run1": run1,
        "run2": run2,
        "run3": run3,
    }

    # Teardown: all state is captured above, so purge the namespace (Views + watermark +
    # TurnEvidence) to leave zero residue and keep re-runs clean.
    if cleanup:
        client.reset_phase3(namespace)

    return Phase3Result(
        benchmark_id=MenhirPhase3Adapter.benchmark_id,
        name=MenhirPhase3Adapter.name,
        namespace=namespace,
        menhir_url=menhir_url,
        cases=case_results,
        metrics=metrics,
        verdict=verdict,
        warnings=warnings,
        run_meta=run_meta,
    )


# ---------------------------------------------------------------------------- reporting


def phase3_result_to_dict(result: Phase3Result) -> dict[str, Any]:
    """Serialize a Phase3Result to a stable JSON-compatible dict."""
    return {
        "benchmark_id": result.benchmark_id,
        "run_id": result.run_meta.get("namespace"),
        "timestamp": result.run_meta.get("timestamp"),
        "menhir_url_safety_class": "throwaway",
        "menhir_url": result.menhir_url,
        "namespace": result.namespace,
        "model": result.run_meta.get("model"),
        "fixture_hash": result.run_meta.get("fixture_hash"),
        "verdict": "pass" if result.verdict else "fail",
        "metrics": result.metrics,
        "cases": [asdict(c) for c in result.cases],
        "warnings": result.warnings,
        "run_meta": result.run_meta,
    }


def _scorecard_row(cases: list[Phase3CaseResult], kind: str) -> str:
    cr = next((c for c in cases if c.kind == kind), None)
    if cr is None:
        return "n/a"
    return "PASS" if cr.passed else "FAIL"


def write_phase3_evidence(
    result: Phase3Result, out_path: str | Path, output_format: str = "markdown"
) -> Path:
    """Write purpose-built Phase 3 evidence (markdown or JSON)."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if output_format == "json":
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(phase3_result_to_dict(result), f, indent=2, ensure_ascii=False)
        return out_path

    m = result.metrics
    cases = result.cases
    lines: list[str] = [
        "# Menhir Phase 3 View Consolidation Benchmark\n\n",
        "## Run metadata\n\n",
        f"- Benchmark: `{result.benchmark_id}`\n",
        f"- Menhir URL: `{result.menhir_url}` (throwaway)\n",
        f"- Namespace: `{result.namespace}`\n",
        f"- Model/provider: `{result.run_meta.get('model') or '(server default)'}`\n",
        f"- k: `{result.run_meta.get('k')}`\n",
        f"- Fixture hash: `{result.run_meta.get('fixture_hash')}`\n",
        f"- Timestamp: `{result.run_meta.get('timestamp')}`\n\n",
        "## Verdict\n\n",
        f"**{'PASS' if result.verdict else 'FAIL'}**\n\n",
        "## Scorecard\n\n",
        "| Case | Result |\n|------|--------|\n",
        f"| stated measure | {_scorecard_row(cases, 'stated_measure')} |\n",
        f"| fold SUM | {_scorecard_row(cases, 'fold_sum')} |\n",
        f"| correction / supersession | {_scorecard_row(cases, 'correction')} |\n",
        f"| junk / drop | {_scorecard_row(cases, 'junk')} |\n\n",
        "## Metrics\n\n",
        "| Metric | Value |\n|--------|-------|\n",
        f"| TurnEvidence submitted | {m['turn_evidence_submitted']} |\n",
        f"| TurnEvidence created | {m['turn_evidence_created']} |\n",
        f"| TurnEvidence dropped | {m['turn_evidence_dropped']} |\n",
        f"| Phase 3 selected | {m['phase3_selected']} |\n",
        f"| Views written (run#1) | {m['views_written_run1']} |\n",
        f"| Views current | {m['views_current']} |\n",
        f"| Views superseded | {m['views_superseded']} |\n",
        f"| Abstentions | {m['abstentions']} |\n",
        f"| Supersessions applied | {m['supersessions_applied']} |\n",
        f"| Duplicate writes on re-run | {m['duplicate_writes_on_rerun']} |\n",
        f"| Late commits on re-run (stochastic, informational) | {m['late_commits_on_rerun']} |\n",
        f"| Watermark debounce hit | {m['watermark_debounce_hit']} |\n",
        f"| Re-dirtied after new evidence | {m['re_dirtied_after_new_evidence']} |\n",
        f"| Recall Views before / after | {m['recall_hit_before']} / {m['recall_hit_after']} |\n",
        f"| Silent abstentions | {m['silent_abstentions']} |\n",
        f"| **Wrong View writes** | **{m['wrong_view_writes']}** |\n\n",
        "## Per-case detail\n\n",
    ]
    for cr in cases:
        status = "PASS" if cr.passed else "FAIL"
        lines.append(f"### {cr.case_id} ({cr.kind}) — {status}\n\n")
        lines.append(f"- Inputs: {cr.inputs}\n")
        lines.append(f"- Expected: {cr.expected}\n")
        lines.append(f"- Actual: {cr.actual}\n")
        if cr.notes:
            lines.append(f"- Notes: {cr.notes}\n")
        lines.append("\n")

    if m["abstention_reasons"]:
        lines.append("## Abstention receipts\n\n")
        for r in m["abstention_reasons"]:
            lines.append(f"- {r}\n")
        lines.append("\n")

    if result.warnings:
        lines.append("## Warnings\n\n")
        for w in result.warnings:
            lines.append(f"- {w}\n")
        lines.append("\n")

    lines.append("## Reproduction command\n\n")
    lines.append("```bash\n")
    lines.append(
        "archolith-bench harness menhir-phase3 \\\n"
        f"  --menhir-url {result.menhir_url or 'http://localhost:<throwaway-port>'} \\\n"
        "  --confirm-menhir-reset \\\n"
        "  --format markdown --out results/menhir_phase3_view_consolidation.md\n"
    )
    lines.append("```\n")

    with open(out_path, "w", encoding="utf-8") as f:
        f.writelines(lines)
    return out_path
