from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import replace
from types import SimpleNamespace

import pytest

import archolith_bench.dependency_evidence_spacy as adapter

from archolith_bench.dependency_evidence_spacy import (
    CandidateLocator,
    CandidateSpan,
    DiscoveryOutcome,
    ParsedCue,
    ParsedDocument,
    ParsedEdge,
    ParsedSpan,
    ParsedToken,
    ParserMetadata,
    canonical_evidence_json,
    emit_dependency_evidence,
    discover_candidates_with_spacy,
    parse_with_spacy,
)


SOURCE = "Aster has 4 lanterns."
HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_C = "c" * 64
EXPECTED_KEYS = {
    "candidate_hash",
    "clause_span",
    "cues",
    "edges",
    "evidence_sha256",
    "evidence_version",
    "markers",
    "model_hash",
    "parser_id",
    "parser_version",
    "pipeline_hash",
    "schema_version",
    "source_hash",
    "source_length",
    "tokens",
}
EXPECTED_FINGERPRINT = "119cc89a658ffd99b3c9cc00bab99a172a3e5c0678b5acb90b2f7c8b9754ba6b"


def _span(start: int, end: int, token_start: int | None = None, token_end: int | None = None) -> ParsedSpan:
    return ParsedSpan(start, end, token_start, token_end)


def _document() -> ParsedDocument:
    tokens = (
        ParsedToken(0, _span(0, 5, 0, 1), 1, "nsubj", "PRON", "aster"),
        ParsedToken(1, _span(6, 9, 1, 2), -1, "ROOT", "VERB", "have"),
        ParsedToken(2, _span(10, 11, 2, 3), 3, "nummod", "NUM", "4"),
        ParsedToken(3, _span(12, 20, 3, 4), 1, "obj", "NOUN", "lantern"),
        ParsedToken(4, _span(20, 21, 4, 5), 1, "punct", "PUNCT", "."),
    )
    return ParsedDocument(
        source=SOURCE,
        clause_span=_span(0, 21, 0, 5),
        tokens=tokens,
        edges=(
            ParsedEdge(1, 0, "nsubj"),
            ParsedEdge(3, 2, "nummod"),
            ParsedEdge(1, 3, "obj"),
            ParsedEdge(1, 4, "punct"),
        ),
        cues=ParsedCue(
            subject=_span(0, 5, 0, 1),
            predicate=_span(6, 9, 1, 2),
            numeric_value=_span(10, 11, 2, 3),
            unit=None,
            target=_span(12, 20, 3, 4),
            modifiers=(),
            scope=None,
            clause_root_token=1,
        ),
        markers=(),
        metadata=ParserMetadata("fixture-parser", "0.1.0", HASH_A, HASH_B),
    )


def test_emission_is_deterministic_and_source_free() -> None:
    candidate = CandidateLocator(0, len(SOURCE), candidate_hash=HASH_C)
    first = emit_dependency_evidence(_document(), candidate)
    second = emit_dependency_evidence(_document(), candidate)

    assert first.status == second.status == "emitted"
    assert first.fingerprint == second.fingerprint
    assert first.evidence == second.evidence
    assert first.evidence is not None
    assert first.evidence["source_hash"] == hashlib.sha256(SOURCE.encode()).hexdigest()
    assert first.evidence["candidate_hash"] == HASH_C
    assert SOURCE not in json.dumps(first.evidence)
    assert canonical_evidence_json(first.evidence) == canonical_evidence_json(second.evidence)


def test_frozen_transport_keys_and_fingerprint_guard_schema_parity() -> None:
    result = emit_dependency_evidence(_document(), CandidateLocator(0, len(SOURCE), candidate_hash=HASH_C))

    assert result.status == "emitted"
    assert result.evidence is not None
    assert set(result.evidence) == EXPECTED_KEYS
    assert result.fingerprint == EXPECTED_FINGERPRINT
    assert result.evidence["evidence_sha256"] == EXPECTED_FINGERPRINT


def test_malformed_graph_and_span_inputs_abstain_without_raising() -> None:
    evidence = _document()
    overlapping = replace(evidence.tokens[1], span=_span(4, 9, 1, 2))
    bad_tokens = (evidence.tokens[0], overlapping, *evidence.tokens[2:])
    candidate = CandidateLocator(0, len(SOURCE), candidate_hash=HASH_C)
    result = emit_dependency_evidence(replace(evidence, tokens=bad_tokens), candidate)
    assert result.status == "abstained"
    assert result.reason == "token_spans_overlap_or_out_of_order"

    bad_edges = replace(evidence.edges[0], label="wrong")
    result = emit_dependency_evidence(
        replace(evidence, edges=(bad_edges, *evidence.edges[1:])), candidate
    )
    assert result.status == "abstained"
    assert result.reason == "edge_token_mismatch"

    bad_cue = replace(evidence.cues, numeric_value=_span(10, 11, 3, 4))
    result = emit_dependency_evidence(replace(evidence, cues=bad_cue), candidate)
    assert result.status == "abstained"
    assert result.reason == "numeric_value_token_alignment_invalid"


def test_integer_transport_fields_reject_bool_and_float_values() -> None:
    evidence = _document()
    candidate = CandidateLocator(0, len(SOURCE), candidate_hash=HASH_C)

    bad_token_index = replace(evidence.tokens[0], token_index=True)
    result = emit_dependency_evidence(replace(evidence, tokens=(bad_token_index, *evidence.tokens[1:])), candidate)
    assert result.reason == "token_indices_invalid"

    bad_head = replace(evidence.tokens[0], head_index=1.0)
    result = emit_dependency_evidence(replace(evidence, tokens=(bad_head, *evidence.tokens[1:])), candidate)
    assert result.reason == "token_head_index_invalid"

    bad_edge = replace(evidence.edges[0], head_index=True)
    result = emit_dependency_evidence(replace(evidence, edges=(bad_edge, *evidence.edges[1:])), candidate)
    assert result.reason == "edge_index_invalid"

    bad_root = replace(evidence.cues, clause_root_token=1.0)
    result = emit_dependency_evidence(replace(evidence, cues=bad_root), candidate)
    assert result.reason == "clause_root_token_invalid"

    result = emit_dependency_evidence(_document(), CandidateLocator(0, len(SOURCE), HASH_C, ordinal=False))
    assert result.reason == "candidate_ordinal_invalid"


def test_candidate_bounds_and_metadata_are_fail_closed() -> None:
    result = emit_dependency_evidence(_document(), CandidateLocator(0, 0, candidate_hash=HASH_C))
    assert result.status == "abstained"
    assert result.reason == "candidate_bounds_invalid"

    invalid_hash = emit_dependency_evidence(_document(), CandidateLocator(0, len(SOURCE), candidate_hash="bad"))
    assert invalid_hash.status == "abstained"
    assert invalid_hash.reason == "candidate_hash_invalid"

    malformed = replace(_document(), metadata=ParserMetadata("fixture-parser", "0.1.0", "bad", HASH_B))
    result = emit_dependency_evidence(malformed, CandidateLocator(0, len(SOURCE), candidate_hash=HASH_C))
    assert result.status == "abstained"
    assert result.reason == "model_hash_invalid"

    forged_metadata = replace(_document(), metadata=ParserMetadata("Aster has 4", "0.1.0", HASH_A, HASH_B))
    result = emit_dependency_evidence(forged_metadata, CandidateLocator(0, len(SOURCE), HASH_C))
    assert result.status == "abstained"
    assert result.reason == "parser_id_invalid"


def test_spacy_absence_or_bad_configuration_returns_typed_outcome() -> None:
    unavailable = parse_with_spacy(SOURCE)
    assert unavailable.status == "unavailable"
    assert unavailable.reason == "model_not_configured"

    error = parse_with_spacy(SOURCE, model_name="fixture-model", config=[])
    assert error.status == "error"
    assert error.reason == "parser_config_invalid"

    missing = parse_with_spacy(SOURCE, model_name="__bench_missing_dependency_model__", config={})
    assert missing.status == "unavailable"
    assert missing.reason in {"spacy_not_installed", "spacy_model_unavailable"}


def _parse_pinned(source: str, numeric_text: str):
    pytest.importorskip("spacy")
    pytest.importorskip("en_core_web_sm")
    numeric_start = source.index(numeric_text)
    candidate_start = source.index("I ")
    candidate_end = source.index(".", numeric_start)
    candidate = CandidateLocator(candidate_start, candidate_end, HASH_C)
    return parse_with_spacy(
        source,
        candidate=candidate,
        numeric_value=ParsedSpan(numeric_start, numeric_start + len(numeric_text)),
        model_name="en_core_web_sm",
        config={},
    ), candidate


def test_pinned_spacy_direct_clause_translates_absolute_offsets_and_is_source_free() -> None:
    source = "Prefix: I have 4 lanterns. Suffix."
    outcome, candidate = _parse_pinned(source, "4")
    assert outcome.status == "parsed"
    assert outcome.document is not None
    document = outcome.document
    assert document.source == source
    assert document.clause_span.start == source.index("I ")
    assert source[document.clause_span.start : document.clause_span.end] == "I have 4 lanterns"
    assert [source[token.span.start : token.span.end] for token in document.tokens] == ["I", "have", "4", "lanterns"]
    assert source[document.cues.numeric_value.start : document.cues.numeric_value.end] == "4"
    assert source[document.cues.target.start : document.cues.target.end] == "lanterns"
    assert source[document.cues.predicate.start : document.cues.predicate.end] == "have"
    assert source[document.cues.subject.start : document.cues.subject.end] == "I"
    assert document.cues.clause_root_token == 1
    assert document.metadata.model_hash == "1932429db727d4bff3deed6b34cfc05df17794f4a52eeb26cf8928f7c1a0fb85"
    emitted = emit_dependency_evidence(document, candidate)
    assert emitted.status == "emitted"
    assert emitted.evidence is not None
    evidence_json = json.dumps(emitted.evidence, sort_keys=True)
    assert source not in evidence_json
    for raw in ("Prefix", "lanterns", "have", "aster"):
        assert raw not in evidence_json
    for forbidden in ("admission", "currentness", "relation", "operation", "identity"):
        assert forbidden not in evidence_json


@pytest.mark.parametrize(
    ("source", "number", "predicate", "subject", "marker"),
    [
        ("I baked 5 loaves.", "5", "baked", "I", "past_morphology"),
        ("I hear Fara has 8 badges.", "8", "has", "Fara", "embedded_clause"),
        ("I have 3 tags and 6 seals.", "3", "have", "I", "additional_numeric"),
    ],
)
def test_pinned_spacy_advisory_cues_cover_event_attribution_and_competing_value(
    source: str, number: str, predicate: str, subject: str, marker: str
) -> None:
    outcome, candidate = _parse_pinned(source, number)
    assert outcome.status == "parsed"
    assert outcome.document is not None
    document = outcome.document
    assert source[document.cues.predicate.start : document.cues.predicate.end] == predicate
    assert source[document.cues.subject.start : document.cues.subject.end] == subject
    assert document.markers and marker in {item.category for item in document.markers}
    if "and" in source:
        marker_tokens = [item for item in document.markers if item.category == "additional_numeric"]
        assert marker_tokens
        assert all(source[item.span.start : item.span.end] == "6" for item in marker_tokens)


def test_pinned_spacy_hashes_are_deterministic_and_version_drift_fails_closed() -> None:
    source = "I have 4 lanterns."
    first, candidate = _parse_pinned(source, "4")
    second, _ = _parse_pinned(source, "4")
    assert first.status == second.status == "parsed"
    assert first.document is not None and second.document is not None
    assert first.document.metadata.pipeline_hash == second.document.metadata.pipeline_hash
    first_emission = emit_dependency_evidence(first.document, candidate)
    second_emission = emit_dependency_evidence(second.document, candidate)
    assert first_emission.fingerprint == second_emission.fingerprint
    drift = parse_with_spacy(
        source,
        candidate=candidate,
        numeric_value=ParsedSpan(7, 8),
        model_name="en_core_web_sm",
        config={"unknown": []},
    )
    assert drift.status == "error"
    assert drift.reason == "parser_config_invalid"


def _fake_adapter_runtime(monkeypatch, fake_nlp):
    class FakeModel:
        __version__ = adapter.PINNED_MODEL_VERSION

        @staticmethod
        def load(**_kwargs):
            return fake_nlp

    fake_spacy = SimpleNamespace(__version__=adapter.PINNED_SPACY_VERSION)
    monkeypatch.setitem(sys.modules, "spacy", fake_spacy)
    monkeypatch.setattr(adapter.importlib, "import_module", lambda _name: FakeModel)
    monkeypatch.setattr(adapter, "_verify_model_artifact", lambda: (True, "model_artifact_verified"))


def test_pinned_adapter_bounds_source_and_token_count_without_model_work(monkeypatch) -> None:
    source = "I have 4 lanterns."
    oversized = parse_with_spacy(
        "x" * (adapter.MAX_SOURCE_LENGTH + 1),
        model_name=adapter.PINNED_MODEL_NAME,
        config={},
    )
    assert oversized.status == "error"
    assert oversized.reason == "source_length_invalid"

    class FakeDoc:
        def __len__(self):
            return adapter.MAX_TOKENS + 1

        def __iter__(self):
            raise AssertionError("oversized document must be rejected before iteration")

    class FakeNLP:
        meta = {"version": adapter.PINNED_MODEL_VERSION}
        pipe_names = ["tagger", "parser"]
        config = SimpleNamespace(to_dict=lambda: {})

        @staticmethod
        def __call__(_text):
            return FakeDoc()

    fake_nlp = FakeNLP()
    _fake_adapter_runtime(monkeypatch, fake_nlp)
    candidate = CandidateLocator(0, len(source) - 1, HASH_C)
    result = parse_with_spacy(
        source,
        candidate,
        ParsedSpan(7, 8),
        model_name=adapter.PINNED_MODEL_NAME,
        config={},
    )
    assert result.status == "error"
    assert result.reason == "token_bound_exceeded"


def test_pinned_adapter_reports_marker_bound_with_fake_bounded_doc(monkeypatch) -> None:
    words = ["have", "4", *(["1"] * 129)]
    source = " ".join(words)

    class FakeToken:
        def __init__(self, index: int, start: int, text: str, root):
            self.i = index
            self.idx = start
            self.text = text
            self.dep_ = "ROOT" if index == 0 else "nummod"
            self.pos_ = "VERB" if index == 0 else "NUM"
            self.tag_ = "VB" if index == 0 else "CD"
            self.lemma_ = text
            self.morph = SimpleNamespace(get=lambda _name: [])
            self.head = self if index == 0 else root
            self.children = ()

    class FakeDoc:
        def __init__(self):
            starts = []
            cursor = 0
            for word in words:
                starts.append(cursor)
                cursor += len(word) + 1
            self.tokens = [FakeToken(index, starts[index], word, None) for index, word in enumerate(words)]
            self.tokens[0].head = self.tokens[0]
            for token in self.tokens[1:]:
                token.head = self.tokens[0]

        def __len__(self):
            return len(self.tokens)

        def __iter__(self):
            return iter(self.tokens)

    class FakeNLP:
        meta = {"version": adapter.PINNED_MODEL_VERSION}
        pipe_names = ["tagger", "parser"]
        config = SimpleNamespace(to_dict=lambda: {})

        @staticmethod
        def __call__(_text):
            return FakeDoc()

    fake_nlp = FakeNLP()
    _fake_adapter_runtime(monkeypatch, fake_nlp)
    candidate = CandidateLocator(0, len(source), HASH_C)
    result = parse_with_spacy(
        source,
        candidate,
        ParsedSpan(5, 6),
        model_name=adapter.PINNED_MODEL_NAME,
        config={},
    )
    assert result.status == "error"
    assert result.reason == "marker_bound_exceeded"


def test_pinned_adapter_rejects_artifact_provenance_drift(monkeypatch) -> None:
    class FakeDistribution:
        version = adapter.PINNED_MODEL_VERSION

        def __init__(self, payload):
            self.payload = payload

        def read_text(self, _name):
            return self.payload

    valid = json.dumps(
        {
            "url": adapter.PINNED_MODEL_URL,
            "archive_info": {
                "hash": f"sha256={adapter.PINNED_MODEL_HASH}",
                "hashes": {"sha256": adapter.PINNED_MODEL_HASH},
            },
        }
    )
    monkeypatch.setitem(
        sys.modules,
        "spacy",
        SimpleNamespace(__version__=adapter.PINNED_SPACY_VERSION),
    )
    monkeypatch.setattr(adapter, "distribution", lambda _name: FakeDistribution(valid.replace(adapter.PINNED_MODEL_URL, "https://example.invalid/model.whl")))
    source = "I have 4 lanterns."
    result = parse_with_spacy(
        source,
        CandidateLocator(0, len(source) - 1, HASH_C),
        ParsedSpan(7, 8),
        model_name=adapter.PINNED_MODEL_NAME,
        config={},
    )
    assert result.status == "unavailable"
    assert result.reason == "model_artifact_identity_mismatch"


def test_pinned_adapter_model_import_failure_is_typed_unavailable(monkeypatch) -> None:
    class FailingModel:
        __version__ = adapter.PINNED_MODEL_VERSION

        @staticmethod
        def load(**_kwargs):
            raise ImportError("model dependency unavailable")

    monkeypatch.setitem(sys.modules, "spacy", SimpleNamespace(__version__=adapter.PINNED_SPACY_VERSION))
    monkeypatch.setattr(adapter.importlib, "import_module", lambda _name: FailingModel)
    monkeypatch.setattr(adapter, "_verify_model_artifact", lambda: (True, "model_artifact_verified"))
    source = "I have 4 lanterns."
    result = parse_with_spacy(
        source,
        CandidateLocator(0, len(source) - 1, HASH_C),
        ParsedSpan(7, 8),
        model_name=adapter.PINNED_MODEL_NAME,
        config={},
    )
    assert result.status == "unavailable"
    assert result.reason == "spacy_model_unavailable"


@pytest.mark.parametrize(
    ("kind", "expected"),
    [("spacy", "spacy_version_mismatch"), ("model", "model_version_mismatch"), ("component", "spacy_parser_component_missing")],
)
def test_pinned_adapter_rejects_runtime_version_or_component_drift(monkeypatch, kind: str, expected: str) -> None:
    source = "I have 4 lanterns."
    candidate = CandidateLocator(0, len(source) - 1, HASH_C)
    if kind == "spacy":
        monkeypatch.setitem(sys.modules, "spacy", SimpleNamespace(__version__="3.8.13"))
    elif kind == "model":
        class DriftedModel:
            __version__ = "3.8.1"

        monkeypatch.setitem(
            sys.modules,
            "spacy",
            SimpleNamespace(__version__=adapter.PINNED_SPACY_VERSION),
        )
        monkeypatch.setattr(adapter, "_verify_model_artifact", lambda: (True, "model_artifact_verified"))
        monkeypatch.setattr(adapter.importlib, "import_module", lambda _name: DriftedModel)
    else:
        fake_nlp = SimpleNamespace(
            meta={"version": adapter.PINNED_MODEL_VERSION},
            pipe_names=["tagger"],
            config=SimpleNamespace(to_dict=lambda: {}),
        )
        _fake_adapter_runtime(monkeypatch, fake_nlp)
    result = parse_with_spacy(
        source,
        candidate,
        ParsedSpan(7, 8),
        model_name=adapter.PINNED_MODEL_NAME,
        config={},
    )
    assert result.status == ("error" if kind == "component" else "unavailable")
    assert result.reason == expected


def _discover(source: str) -> DiscoveryOutcome:
    pytest.importorskip("spacy")
    pytest.importorskip("en_core_web_sm")
    return discover_candidates_with_spacy(source)


def test_gold_free_discovery_direct_simple_offsets_only() -> None:
    source = "I have 4 lanterns."
    outcome = _discover(source)
    assert outcome.status == "discovered"
    assert outcome.reason == "candidates_discovered"
    assert len(outcome.candidates) == 1
    candidate = outcome.candidates[0]
    assert isinstance(candidate, CandidateSpan)
    assert (candidate.clause_start, candidate.clause_end) == (0, len(source))
    assert source[candidate.numeric_start : candidate.numeric_end] == "4"
    assert source[candidate.subject_start : candidate.subject_end] == "I"
    assert source[candidate.predicate_start : candidate.predicate_end] == "have"
    assert source[candidate.target_start : candidate.target_end] == "lanterns"
    assert source not in repr(outcome)


def test_discovery_allows_independent_coordination_with_own_subject() -> None:
    source = "I have 3 tags, and I keep 6 seals."
    outcome = _discover(source)
    assert outcome.status == "discovered"
    assert [source[item.numeric_start : item.numeric_end] for item in outcome.candidates] == ["3", "6"]
    assert source[outcome.candidates[0].clause_start : outcome.candidates[0].clause_end].startswith("I have")
    second = outcome.candidates[1]
    assert source[second.subject_start : second.subject_end] == "I"
    assert source[second.predicate_start : second.predicate_end] == "keep"
    assert source[second.clause_start : second.clause_end].startswith("I keep")


def test_discovery_rejects_embedded_attribution_predicate() -> None:
    outcome = _discover("I hear Fara has 8 badges.")
    assert outcome.status == "discovered"
    assert outcome.candidates == ()


@pytest.mark.parametrize(
    "source",
    [
        "Yesterday, I do not have 4 lanterns.",
        "I have 3 tags and 6 seals.",
    ],
)
def test_root_clause_preserves_meaning_bearing_context_and_competing_values(source: str) -> None:
    first = _discover(source)
    second = _discover(source)
    assert first == second
    assert first.status == "discovered"
    assert len(first.candidates) >= 1
    assert len({item.clause_start for item in first.candidates}) == 1
    assert first.candidates[0].clause_start == 0
    assert first.candidates[0].clause_end == len(source)
    if "6 seals" in source:
        assert [source[item.numeric_start : item.numeric_end] for item in first.candidates] == ["3", "6"]


def test_discovery_has_typed_unavailable_error_and_no_text_results() -> None:
    assert discover_candidates_with_spacy(None).reason == "source_type_invalid"
    assert discover_candidates_with_spacy("").reason == "source_length_invalid"
    assert discover_candidates_with_spacy("I have 4 lanterns.", model_name="__missing_model__").status == "unavailable"
    assert discover_candidates_with_spacy("I have 4 lanterns.", model_name="__missing_model__").reason == "spacy_model_unavailable"
    assert discover_candidates_with_spacy("I have 4 lanterns.", config=[]).reason == "parser_config_invalid"
    assert discover_candidates_with_spacy("I have 4 lanterns.", model_name="__missing_model__").candidates == ()


def test_discovery_candidate_bound_allows_64_and_fails_on_65(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeDoc:
        def __init__(self, count: int):
            self.tokens = []
            for index in range(count):
                base = index * 10
                predicate = SimpleNamespace(i=base + 1, idx=base + 1, text="has", pos_="VERB", dep_="ROOT")
                subject = SimpleNamespace(i=base, idx=base, text="I", pos_="PRON", dep_="nsubj", head=predicate)
                target = SimpleNamespace(i=base + 3, idx=base + 3, text="tags", pos_="NOUN", dep_="obj", head=predicate)
                numeric = SimpleNamespace(i=base + 2, idx=base + 2, text="4", pos_="NUM", dep_="nummod", head=target)
                predicate.head = predicate
                predicate.children = (subject,)
                predicate.sent = SimpleNamespace(start_char=0, end_char=10_000)
                self.tokens.extend((subject, predicate, numeric, target))

        def __iter__(self):
            return iter(self.tokens)

        def __len__(self):
            return len(self.tokens)

    class FakeNlp:
        def __init__(self, count: int):
            self.count = count

        def __call__(self, _source: str) -> FakeDoc:
            return FakeDoc(self.count)

    monkeypatch.setattr(adapter, "_load_pinned_spacy", lambda **_: ("ready", "model_loaded", FakeNlp(64), "a" * 64))
    source = "x" * 10_000
    sixty_four = discover_candidates_with_spacy(source)
    assert sixty_four.status == "discovered"
    assert len(sixty_four.candidates) == 64
    monkeypatch.setattr(adapter, "_load_pinned_spacy", lambda **_: ("ready", "model_loaded", FakeNlp(65), "a" * 64))
    sixty_five = discover_candidates_with_spacy(source)
    assert sixty_five.status == "error"
    assert sixty_five.reason == "candidate_bound_exceeded"
