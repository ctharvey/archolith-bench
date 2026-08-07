"""Integrity and live measurement tests for the cumulative-completion research fixture."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

import pytest

from archolith_bench.scalar_identity_isolated_comparison import analyze_comparison
from archolith_bench.scalar_identity_noisy_panel import load_panel, source_sha256


FIXTURE = Path("fixtures/scalar_identity_cumulative_v1.json")


def _menhir_root() -> Path:
    candidates = [Path.cwd() / "menhir", Path.cwd().parent / "menhir"]
    for candidate in candidates:
        if (candidate / "src" / "menhir" / "services" / "research_scalar_adapter.py").is_file():
            return candidate.resolve()
    pytest.skip("provide a local ../menhir sibling to run deferred scoring")


def test_cumulative_fixture_has_independent_train_holdout_pairs():
    panel = load_panel(FIXTURE)
    assert panel["panel_id"] == "scalar-identity-cumulative-v1"
    assert len(panel["episodes"]) == 24
    assert len(panel["cases"]) == 24
    assert panel["source_sha256"] == source_sha256(panel["episodes"])

    by_split = Counter(case["split"] for case in panel["cases"])
    assert by_split == {"train": 12, "holdout": 12}
    pairs: dict[str, set[str]] = defaultdict(set)
    for case in panel["cases"]:
        pairs[case["pair_id"]].add(case["slice"])
    assert len(pairs) == 12
    assert all(slices == {"clean", "noisy"} for slices in pairs.values())
    assert sum(case["split"] == "train" for case in panel["cases"] if case["slice"] == "clean") == 6
    assert sum(case["split"] == "holdout" for case in panel["cases"] if case["slice"] == "clean") == 6

    train = [case for case in panel["cases"] if case["split"] == "train"]
    holdout = [case for case in panel["cases"] if case["split"] == "holdout"]
    assert {case["candidate"]["attribute"] for case in train}.isdisjoint(
        {case["candidate"]["attribute"] for case in holdout}
    )
    assert {case["candidate"]["value"] for case in train}.isdisjoint(
        {case["candidate"]["value"] for case in holdout}
    )
    train_text = {episode["content"] for episode in panel["episodes"] if episode["uuid"].endswith("train-clean")}
    holdout_text = {episode["content"] for episode in panel["episodes"] if episode["uuid"].endswith("holdout-clean")}
    assert train_text.isdisjoint(holdout_text)


def test_cumulative_fixture_expected_labels_cover_positive_and_adversarial_gates():
    panel = load_panel(FIXTURE)
    positives = [case for case in panel["cases"] if case["expected"]["paired_invariant"]]
    adversarial = [case for case in panel["cases"] if not case["expected"]["paired_invariant"]]
    assert len(positives) == 12
    assert len(adversarial) == 12
    for case in positives:
        expected = case["expected"]
        assert case["candidate"]["operation"] == "absolute"
        assert expected["parse_status"] == "admitted"
        assert expected["composition_status"] == "composed"
        assert expected["relation_type"] == "quantity"
        assert expected["target"] == case["candidate"]["attribute"]
        assert expected["operation"] == "absolute"
        assert expected["value"] == case["candidate"]["value"]
        assert expected["false_current"] is False
    for case in adversarial:
        expected = case["expected"]
        if expected["parse_status"] == "rejected":
            assert expected["composition_status"] is None
            assert expected["composition_reason"] is None
        else:
            assert expected["composition_status"] == "abstained"
        assert expected["relation_type"] is None
        assert expected["target"] is None
        assert expected["operation"] is None
        assert expected["value"] is None
        assert expected["false_current"] is True
    perturbations = {case["perturbation_id"] for case in panel["cases"]}
    assert {
        "positive-completed", "positive-finished", "positive-closed",
        "adversarial-simple-past", "adversarial-negation", "adversarial-modality-future",
        "adversarial-history-tail", "adversarial-coordination", "adversarial-subset-empty",
    } == perturbations


def test_cumulative_fixture_is_source_free_and_non_benchmark():
    payload = FIXTURE.read_text(encoding="utf-8")
    encoded = json.loads(payload)
    assert encoded["non_lme"] is True
    lowered = payload.lower()
    assert "longmemeval" not in lowered
    assert '"lme-' not in lowered


def test_cumulative_panel_scores_live_cumulative_rule():
    report = analyze_comparison(FIXTURE, menhir_root=_menhir_root())
    aggregate = report["aggregate"]
    assert aggregate["baseline"]["slices"]["clean"]["correct"] == 12
    assert aggregate["baseline"]["slices"]["clean"]["composed"] == 6
    assert aggregate["baseline"]["slices"]["noisy"]["correct"] == 6
    assert aggregate["baseline"]["slices"]["noisy"]["composed"] == 0
    isolated = report["aggregate"]["isolated"]
    assert isolated["slices"]["clean"]["correct"] == 12
    assert isolated["slices"]["noisy"]["correct"] == 12
    assert isolated["slices"]["clean"]["composed"] == 6
    assert isolated["slices"]["noisy"]["composed"] == 6
    assert aggregate["composition_gains"] == {"clean": 0, "noisy": 6, "total": 6}
    assert aggregate["identity_mismatches"] == {
        "total": 6,
        "case_ids": [
            "completed-audits-train-noisy",
            "finished-reviews-train-noisy",
            "closed-tickets-train-noisy",
            "completed-surveys-holdout-noisy",
            "finished-forms-holdout-noisy",
            "closed-merges-holdout-noisy",
        ],
    }
    assert aggregate["false_current_state_errors"] == {"baseline": 0, "isolated": 0}
