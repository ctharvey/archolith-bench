"""Tests for the persistent LongMemEval ingestion regression fixture."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "longmemeval" / "menhir_suburbs_extraction_regression.json"


def _load_script(name: str, relative_path: str):
    path = ROOT / relative_path
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ingest = _load_script("lme_ingest_fixture_test", "scripts/longmemeval/lib/ingest.py")
verify = _load_script(
    "lme_verify_suburbs_fixture_test",
    "scripts/longmemeval/lib/verify_suburbs_fixture.py",
)


def test_ingest_defaults_resolve_from_repository_root() -> None:
    assert ingest.BENCH_ROOT == ROOT
    assert Path(ingest.DEFAULT_MANIFEST) == ROOT / "results" / "lme-ingest" / "manifest.json"


def test_ingest_parser_accepts_fixture_and_namespace_prefix() -> None:
    args = ingest._parse_args(
        [
            "--fixture",
            str(FIXTURE),
            "--namespace-prefix",
            "fixture-",
            "--limit",
            "1",
        ]
    )
    assert args.fixture == str(FIXTURE)
    assert args.namespace_prefix == "fixture-"
    assert args.limit == 1


def test_ingest_parser_accepts_scalar_consolidation_controls() -> None:
    args = ingest._parse_args(
        [
            "--consolidate-scalar",
            "--consolidation-k",
            "3",
            "--consolidation-call-budget",
            "40",
        ]
    )
    assert args.consolidate_scalar is True
    assert args.consolidation_k == 3
    assert args.consolidation_call_budget == 40


def test_current_scalar_buildout_wrapper_is_fail_closed() -> None:
    script = (
        ROOT / "scripts" / "longmemeval" / "run_knowledge_update_buildout.sh"
    ).read_text(encoding="utf-8")

    assert 'LME_KU_RUN_ID is required' in script
    assert "LME_KU_ARM must be exactly 'baseline' or 'candidate'" in script
    assert 'export LME_REQUIRE_FRESH="1"' in script
    assert 'export LME_SCALAR_STATE_ENABLED="1"' in script
    assert 'export LME_REQUIRE_TURN_EVIDENCE="1"' in script
    assert 'LME_KU_ALLOW_DIRTY' in script
    assert 'status --porcelain --untracked-files=no' in script
    assert '"fixture_sha256": "${FIXTURE_SHA256}"' in script
    assert '"consolidation_audit_enabled": ${LME_CONSOLIDATION_AUDIT_ENABLED}' in script
    assert '"recall_audit_enabled": ${LME_RECALL_AUDIT_ENABLED}' in script
    assert (
        'MENHIR_PERSONAL_MEMORY_SCALAR_VIEW_AUTHORITY_ENABLED="${LME_SCALAR_VIEW_AUTHORITY_ENABLED}"'
        in script
    )
    assert '--preflight-only' in script


def test_fixture_path_is_forwarded_to_adapter() -> None:
    calls: list[dict] = []

    class FakeAdapter:
        def load_items(self, **kwargs):
            calls.append(kwargs)
            return [{"question_id": "one"}]

    items = ingest._load_items(FakeAdapter(), limit=1, fixture_path=str(FIXTURE))
    assert items == [{"question_id": "one"}]
    assert calls == [{"limit": 1, "fixture_path": str(FIXTURE)}]


def test_empty_fixture_is_rejected() -> None:
    class EmptyAdapter:
        def load_items(self, **kwargs):
            return []

    with pytest.raises(ValueError, match="fixture is empty"):
        ingest._load_items(EmptyAdapter(), limit=1, fixture_path=str(FIXTURE))


def test_namespace_prefix_is_explicit_and_nonempty() -> None:
    assert ingest._namespace("830ce83f", "fresh-") == "fresh-830ce83f"
    with pytest.raises(ValueError, match="must not be empty"):
        ingest._namespace("830ce83f", "  ")


def test_suburbs_fixture_contract_preserves_failure_shape() -> None:
    contract = verify._load_contract(FIXTURE)
    assert contract["question_id"] == "830ce83f-suburbs-fix-v1"
    assert contract["namespace"] == "lme-830ce83f-suburbs-fix-v1"
    assert contract["turns"] == 14
    assert contract["current_object_contains"] == "suburb"
    assert contract["stale_object"] == "Chicago"
    assert contract["required_menhir_commit"].startswith("c949dfa")


def test_graph_verification_checks_current_and_stale_edges(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    contract = verify._load_contract(FIXTURE)
    observed_queries: list[str] = []
    values = iter([1, 1, 1, 0, 1])

    def fake_count(container: str, password: str, query: str) -> int:
        assert container == "fixture-neo4j"
        assert password == "not-printed"
        observed_queries.append(query)
        return next(values)

    monkeypatch.setattr(verify, "_cypher_count", fake_count)
    counts = verify._graph_counts(contract, "fixture-neo4j", "not-printed")

    assert counts == {
        "suburb_entities": 1,
        "current_suburb_edges": 1,
        "expired_stale_edges": 1,
        "current_stale_edges": 0,
        "target_episodes": 1,
    }
    joined = "\n".join(observed_queries)
    assert "edge.invalid_at IS NULL" in joined
    assert "edge.invalid_at IS NOT NULL OR edge.expired_at IS NOT NULL" in joined
