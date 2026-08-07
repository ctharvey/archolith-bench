from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path


FIXTURE = Path(__file__).parents[1] / "fixtures" / "dependency_evidence_bridge_ops_v1.json"
RELATION_TYPES = {"balance", "duration", "frequency", "measurement", "quantity", "schedule_time", "state"}
ROLES = {"current_total", "delta", "one_off_event", "standing_expiry", "history", "subset", "modality", "attribution"}
COARSE_ROLES = {"current_total", "delta", "event", "history", "subset", "modality", "attribution"}
NUM_RE = re.compile(r"(?<![A-Za-z0-9_-])(?:[0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)(?![A-Za-z0-9_-])")
EXPECTED_CASES_SHA256 = "bde118508cf55c94bbd10fc88fbc625a0f465859a545f3ca79deb391a25ba57b"


def _load() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _source_key(episode_id: str, start: int, end: int, ordinal: int) -> str:
    raw = b"".join(str(x).strip().encode("utf-8", "replace") + bytes([0]) for x in (episode_id, start, end, ordinal))
    return hashlib.sha256(raw).hexdigest()


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def test_fixture_shape_and_frozen_enums() -> None:
    data = _load()
    assert data["schema_version"] == "dependency-evidence-bridge-ops-v1"
    assert data["fixture_version"] == "1.0.0"
    assert set(data["relation_types"]) == RELATION_TYPES
    cases = data["cases"]
    assert len(cases) == 48
    assert len({case["case_id"] for case in cases}) == 48
    assert Counter(case["split"] for case in cases) == {"train": 24, "holdout": 24}
    assert Counter(case["topology"] for case in cases) == {"direct": 16, "distractor": 16, "multiclause": 16}
    for split in ("train", "holdout"):
        assert Counter(case["topology"] for case in cases if case["split"] == split) == {
            "direct": 8,
            "distractor": 8,
            "multiclause": 8,
        }
    assert all(case["relation_type"] in RELATION_TYPES for case in cases)
    assert all(case["role_gold"] in COARSE_ROLES for case in cases)
    assert all(case["role_variant"] in {None, "one_off_event", "standing_expiry"} for case in cases)
    fine = Counter(case["role_variant"] or case["role_gold"] for case in cases)
    assert fine == {role: 6 for role in ROLES}
    assert data["fine_role_counts"] == {role: 6 for role in ROLES}
    assert data["metadata"]["denominators"] == {
        "cases": 48,
        "claim_spans": 48,
        "dependency_paths": 48,
        "gold_edge_count": 144,
        "role_labels": 48,
        "operation_labels": 48,
        "relation_payloads": 48,
        "target_scope_payloads": 48,
        "value_payloads": 48,
    }


def test_train_holdout_are_disjoint_and_non_benchmark() -> None:
    data = _load()
    cases = data["cases"]
    train = [case for case in cases if case["split"] == "train"]
    holdout = [case for case in cases if case["split"] == "holdout"]
    assert {case["target_literal"] for case in train}.isdisjoint(case["target_literal"] for case in holdout)
    train_numbers = {n.group() for case in train for n in NUM_RE.finditer(case["text"])}
    holdout_numbers = {n.group() for case in holdout for n in NUM_RE.finditer(case["text"])}
    assert train_numbers.isdisjoint(holdout_numbers)
    forbidden = re.compile(r"(?i)(?:lme|longmemeval|benchmark|frozen[-_ ]?78)")
    assert not any(forbidden.search(case["text"]) for case in cases)

    names_targets = sorted({case["target_literal"] for case in cases} | {part for case in cases for part in re.findall(r"\b(?:virels|qorels)[0-9]+\b", case["text"])})
    names_targets += sorted({name for case in cases for name in re.findall(r"\b[A-Z][a-z]+\b", case["text"])})
    def normalize(case: dict) -> str:
        text = case["text"]
        for literal in sorted(names_targets, key=len, reverse=True):
            text = text.replace(literal, "<ENTITY>")
        return NUM_RE.sub("<NUM>", text)

    assert {normalize(case) for case in train}.isdisjoint(normalize(case) for case in holdout)


def test_spans_hashes_source_keys_and_dependency_paths() -> None:
    data = _load()
    episodes: set[str] = set()
    source_keys: set[str] = set()
    for case in data["cases"]:
        text = case["text"]
        claim = case["claim_span"]
        quantity = case["quantity_span"]
        start, end = claim["start_char"], claim["end_char"]
        qstart, qend = quantity["start_char"], quantity["end_char"]
        assert 0 <= start < end <= len(text)
        assert case["source_sha256"] == _sha(text)
        assert text[start:end] == claim["text"]
        assert claim["sha256"] == _sha(claim["text"])
        assert start <= qstart < qend <= end
        assert text[qstart:qend] == quantity["text"]
        assert quantity["sha256"] == _sha(quantity["text"])
        assert quantity["text"].replace(",", "").isdigit()
        assert case["source_key"] == _source_key(case["episode_id"], start, end, case["claim_ordinal"])
        assert case["claim_ordinal"] == 0
        assert case["episode_id"] not in episodes
        assert case["source_key"] not in source_keys
        episodes.add(case["episode_id"])
        source_keys.add(case["source_key"])
        path = case["gold_dependency_path"]
        nodes = path["node_char_offsets"]
        assert set(nodes) == {"subject", "predicate", "numeric", "target"}
        assert all(start <= offset < end for offset in nodes.values())
        literals = path["node_literals"]
        assert set(literals) == {"subject", "predicate", "numeric", "target"}
        assert all(text[offset : offset + len(literals[name])] == literals[name] for name, offset in nodes.items())
        assert all(claim["text"].count(literals[name]) == 1 for name in nodes)
        assert len(path["edges"]) == 3
        assert {edge["dependency_label"] for edge in path["edges"]} == {"nsubj", "nummod", "dobj"}
        assert {(edge["head_char"], edge["dependent_char"], edge["dependency_label"]) for edge in path["edges"]} == {
            (nodes["predicate"], nodes["subject"], "nsubj"),
            (nodes["target"], nodes["numeric"], "nummod"),
            (nodes["predicate"], nodes["target"], "dobj"),
        }
        assert all(edge["head_char"] != edge["dependent_char"] for edge in path["edges"])

    menhir_root = Path(os.environ.get("MENHIR_ROOT", Path(__file__).parents[2] / "menhir"))
    if (menhir_root / "src").is_dir():
        try:
            sys.path.insert(0, str(menhir_root / "src"))
            from menhir.domain.typed_assertion import build_source_key
        except Exception:  # pragma: no cover - optional sibling checkout
            build_source_key = None
        if build_source_key is not None:
            assert all(
                case["source_key"]
                == build_source_key(
                    case["episode_id"],
                    case["claim_span"]["start_char"],
                    case["claim_span"]["end_char"],
                    case["claim_ordinal"],
                )
                for case in data["cases"]
            )


def test_role_operation_admission_and_phase_a_contract() -> None:
    data = _load()
    cases = data["cases"]
    for case in cases:
        fine = case["role_variant"] or case["role_gold"]
        op = case["operation_gold"]
        if fine == "current_total":
            assert (op, case["admit_gold"], case["abstention_reason"], case["phase_a_expectation"]) == ("absolute", True, None, "supported")
            assert case["temporal_state"] == "present"
            assert case["phase_a_reason"] is None
        elif fine == "delta":
            assert (op, case["admit_gold"], case["abstention_reason"], case["phase_a_expectation"], case["phase_a_reason"]) == ("delta", True, None, "unsupported_abstain", "operation_unsupported")
            if case["value"]["sign"] < 0:
                assert any(word in case["claim_span"]["text"] for word in ("sold", "removed"))
            else:
                assert any(word in case["claim_span"]["text"] for word in ("added", "acquired", "gained", "secured"))
        elif fine == "one_off_event":
            assert (case["role_gold"], op, case["admit_gold"], case["abstention_reason"], case["phase_a_expectation"]) == ("event", None, False, "non_holding_event", "negative")
            assert case["phase_a_reason"] == "non_holding_event"
        elif fine == "standing_expiry":
            assert (case["role_gold"], op, case["admit_gold"], case["abstention_reason"], case["phase_a_expectation"], case["phase_a_reason"]) == ("event", "expire", True, None, "unsupported_abstain", "operation_unsupported")
            assert case["totality"] == "entire"
            assert "no longer" in case["claim_span"]["text"]
        elif fine == "history":
            assert (op, case["admit_gold"], case["abstention_reason"], case["phase_a_expectation"]) == ("absolute", False, "past_only", "negative")
            assert case["phase_a_reason"] == "past_only"
        elif fine == "subset":
            if case["case_id"].endswith("-03"):
                assert (op, case["admit_gold"], case["abstention_reason"], case["grounding"], case["phase_a_expectation"], case["phase_a_reason"]) == ("delta", True, None, "subset_explicit_delta", "unsupported_abstain", "operation_unsupported")
            else:
                assert (op, case["admit_gold"], case["abstention_reason"], case["grounding"], case["phase_a_expectation"]) == ("absolute", False, "subset_non_authoritative", "subset_non_authoritative", "negative")
                assert case["phase_a_reason"] == "subset_non_authoritative"
        elif fine == "modality":
            assert (op, case["admit_gold"], case["abstention_reason"], case["phase_a_expectation"]) == (None, False, "modal", "negative")
            assert case["phase_a_reason"] == "modal"
        elif fine == "attribution":
            assert (op, case["admit_gold"], case["abstention_reason"], case["phase_a_expectation"]) == (None, False, "attributed_source", "negative")
            assert case["phase_a_reason"] == "attributed_source"
    assert Counter(case["phase_a_expectation"] for case in cases) == {"supported": 6, "unsupported_abstain": 14, "negative": 28}
    assert sum(case["admit_gold"] for case in cases) == 20
    assert data["metadata"]["phase_a_supported"] == 6
    assert data["metadata"]["phase_a_unsupported"] == 14
    assert data["metadata"]["phase_a_true_negatives"] == 28


def test_modifier_and_subset_gold_templates_are_direct_and_unambiguous() -> None:
    data = _load()
    cases = {case["case_id"]: case for case in data["cases"]}
    assert "expect to" not in cases["holdout-modality-02"]["claim_span"]["text"]
    assert cases["holdout-modality-02"]["gold_dependency_path"]["node_literals"]["predicate"] == "retain"
    assert "from my set" in cases["holdout-subset-03"]["claim_span"]["text"]
    assert "to my set" not in cases["holdout-subset-03"]["claim_span"]["text"]
    assert cases["holdout-subset-03"]["value"]["sign"] == -1
    assert cases["holdout-attribution-01"]["claim_span"]["text"].startswith("Jexa owns")


def test_fixture_sha_is_canonical_and_byte_stable() -> None:
    data = _load()
    canonical = json.dumps(data["cases"], sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    assert hashlib.sha256(canonical.encode()).hexdigest() == EXPECTED_CASES_SHA256
    assert data["metadata"]["fixture_sha256"] == EXPECTED_CASES_SHA256
    assert data["metadata"]["hash_basis"] == "sha256(canonical_json(cases))"
