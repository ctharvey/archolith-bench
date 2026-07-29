"""Tests for the persistent LongMemEval ingestion regression fixture."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "longmemeval" / "menhir_suburbs_extraction_regression.json"


def _load_script(name: str, relative_path: str):
    path = ROOT / relative_path
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
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


def test_ingest_parser_accepts_namespace_window() -> None:
    args = ingest._parse_args(
        ["--namespace-window", "2", "--manifest-item-limit", "2"]
    )
    assert args.namespace_window == 2
    assert args.manifest_item_limit == 2

    with pytest.raises(SystemExit):
        ingest._parse_args(["--namespace-window", "0"])
    with pytest.raises(SystemExit):
        ingest._parse_args(["--manifest-item-limit", "0"])


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
    assert 'FIXTURE_SHA256="${FIXTURE_SHA256//$\'\\r\'/}"' in script
    assert '"consolidation_audit_enabled": ${LME_CONSOLIDATION_AUDIT_ENABLED}' in script
    assert '"recall_audit_enabled": ${LME_RECALL_AUDIT_ENABLED}' in script
    assert 'LME_KU_INGEST_CONCURRENCY:-2' in script
    assert 'LME_KU_CHECKPOINT_ITEMS:-0' in script
    assert 'while [ ! -f "${CHECKPOINT_CONTINUE}" ]' in script
    assert '"ingest_concurrency": ${LME_INGEST_CONCURRENCY}' in script
    assert '"checkpoint_items": ${LME_KU_CHECKPOINT_ITEMS}' in script
    assert (
        'MENHIR_PERSONAL_MEMORY_SCALAR_VIEW_AUTHORITY_ENABLED="${LME_SCALAR_VIEW_AUTHORITY_ENABLED}"'
        in script
    )
    assert '--preflight-only' in script


def test_build_graph_wires_same_namespace_window_into_menhir_workers() -> None:
    script = (ROOT / "scripts" / "longmemeval" / "build_graph.sh").read_text(encoding="utf-8")

    assert 'export MENHIR_INGEST_CONCURRENCY="${LME_INGEST_CONCURRENCY}"' in script
    assert '--namespace-window "${LME_INGEST_CONCURRENCY}"' in script
    assert '--manifest-item-limit "${LME_INGEST_STOP_AFTER_ITEMS}"' in script
    assert '"ingest_target_items": ${INGEST_TARGET}' in script
    assert '"ingest_concurrency": ${LME_INGEST_CONCURRENCY}' in script


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


def test_item_turn_generation_preserves_namespace_session_order() -> None:
    class FakeAdapter:
        def sessions(self, item):
            return [item["turns"]]

    adapter = FakeAdapter()
    first = {
        "turns": [
            {"role": "user", "content": "a1"},
            {"role": "assistant", "content": "a2"},
            {"role": "user", "content": "a3"},
        ],
    }
    scheduled = [
        (turn.content, turn.session_id)
        for turn in ingest._iter_item_turns(adapter, first, "ns-a", "none")
    ]

    assert scheduled == [
        ("a1", "ns-a-s0"),
        ("a2", "ns-a-s0"),
        ("a3", "ns-a-s0"),
    ]


def test_drain_many_waits_for_global_queue_and_every_namespace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    queue_depths = iter([1, 0, 0])
    states = {
        "ns-a": iter(
            [
                {"pending": 1, "ready": 0, "enriching": 0, "failed": 0, "total": 1},
                {"pending": 0, "ready": 1, "enriching": 0, "failed": 0, "total": 1},
                {"pending": 0, "ready": 1, "enriching": 0, "failed": 0, "total": 1},
            ]
        ),
        "ns-b": iter(
            [
                {"pending": 0, "ready": 0, "enriching": 1, "failed": 0, "total": 1},
                {"pending": 0, "ready": 1, "enriching": 0, "failed": 0, "total": 1},
                {"pending": 0, "ready": 1, "enriching": 0, "failed": 0, "total": 1},
            ]
        ),
    }

    monkeypatch.setattr(ingest, "_queue_depth", lambda admin, url: next(queue_depths))
    monkeypatch.setattr(ingest, "_ns_state_counts", lambda namespace: next(states[namespace]))
    monkeypatch.setattr(ingest.time, "sleep", lambda seconds: None)

    drained = ingest._drain_many(
        ["ns-a", "ns-b"],
        object(),
        "http://menhir",
        poll_s=0,
        timeout_s=1,
    )

    assert drained["ns-a"]["ready"] == 1
    assert drained["ns-b"]["ready"] == 1
    assert drained["ns-a"]["timed_out"] is False
    assert drained["ns-b"]["timed_out"] is False


def test_namespace_state_counts_include_cost_and_retry_signals(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        ingest,
        "_cypher",
        lambda query: [["0", "20", "0", "0", "270", "24", "20"]],
    )

    assert ingest._ns_state_counts("ns-a") == {
        "pending": 0,
        "ready": 20,
        "enriching": 0,
        "failed": 0,
        "llm_tasks": 270,
        "processing_attempts": 24,
        "total": 20,
    }


def test_reset_namespace_force_deletes_graph_and_purges_turn_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend_calls: list[tuple[str, dict]] = []

    class FakeResponse:
        def raise_for_status(self):
            return None

    class FakeAdmin:
        def __init__(self):
            self.posts: list[dict] = []

        def post(self, url, **kwargs):
            self.posts.append({"url": url, **kwargs})
            return FakeResponse()

    def fake_backend(admin, url, operation, body):
        backend_calls.append((operation, body))
        return {"namespace": body["namespace"], "deleted": 250}

    monkeypatch.setattr(ingest, "_backend", fake_backend)
    admin = FakeAdmin()

    ingest._reset_namespace(admin, "http://menhir/", "ns-a")

    assert backend_calls == [
        ("delete_namespace", {"namespace": "ns-a", "force": True}),
    ]
    assert admin.posts == [
        {
            "url": "http://menhir/api/phase3/reset",
            "params": {"namespace": "ns-a"},
            "timeout": 300.0,
        }
    ]


def test_ingest_window_refills_only_after_that_namespace_is_terminal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = [
        ingest.WindowItem(item={}, question_id="a", namespace="ns-a"),
        ingest.WindowItem(item={}, question_id="b", namespace="ns-b"),
    ]
    turns = [
        iter([
            ingest.IngestTurn("user", "a1", None, "ns-a-s0"),
            ingest.IngestTurn("user", "a2", None, "ns-a-s0"),
        ]),
        iter([
            ingest.IngestTurn("user", "b1", None, "ns-b-s0"),
            ingest.IngestTurn("user", "b2", None, "ns-b-s0"),
        ]),
    ]
    submitted: list[str] = []
    lifecycle = {
        "episode-1": iter(["PENDING", "READY"]),
        "episode-2": iter(["READY"]),
        "episode-3": iter(["READY"]),
        "episode-4": iter(["READY"]),
    }

    def fake_ingest_turn(client, namespace, role, content, **kwargs):
        submitted.append(content)
        return f"episode-{len(submitted)}"

    def fake_processing(admin, url, episode_uuid):
        return {"processing_state": next(lifecycle[episode_uuid])}

    monkeypatch.setattr(ingest, "_ingest_turn", fake_ingest_turn)
    monkeypatch.setattr(ingest, "_episode_processing", fake_processing)

    requeued = ingest._ingest_window(
        window,
        turns,
        object(),
        object(),
        "http://menhir",
        timeout_s=1,
        poll_s=0,
    )

    # b2 may refill while a1 is still pending, but a2 cannot be submitted until a1 is READY.
    assert submitted == ["a1", "b1", "b2", "a2"]
    assert requeued == {"ns-a": 0, "ns-b": 0}


def test_ingest_window_retries_failure_before_advancing_namespace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = [ingest.WindowItem(item={}, question_id="a", namespace="ns-a")]
    turns = [iter([
        ingest.IngestTurn("user", "a1", None, "ns-a-s0"),
        ingest.IngestTurn("user", "a2", None, "ns-a-s0"),
    ])]
    submitted: list[str] = []
    operations: list[str] = []
    lifecycle = {
        "episode-1": iter(["FAILED", "READY"]),
        "episode-2": iter(["READY"]),
    }

    def fake_ingest_turn(client, namespace, role, content, **kwargs):
        submitted.append(content)
        return f"episode-{len(submitted)}"

    def fake_processing(admin, url, episode_uuid):
        return {"processing_state": next(lifecycle[episode_uuid])}

    def fake_backend(admin, url, operation, body):
        operations.append(operation)
        return True

    monkeypatch.setattr(ingest, "_ingest_turn", fake_ingest_turn)
    monkeypatch.setattr(ingest, "_episode_processing", fake_processing)
    monkeypatch.setattr(ingest, "_backend", fake_backend)

    requeued = ingest._ingest_window(
        window,
        turns,
        object(),
        object(),
        "http://menhir",
        timeout_s=1,
        poll_s=0,
    )

    assert submitted == ["a1", "a2"]
    assert operations == ["force_reset_failed_episode", "enqueue_pending_episode"]
    assert requeued == {"ns-a": 1}


def test_manifest_checkpoint_is_atomic(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    rows = [{"question_id": "one"}]

    ingest._write_manifest(manifest_path, rows)

    assert manifest_path.read_text(encoding="utf-8") == '[\n  {\n    "question_id": "one"\n  }\n]'
    assert not manifest_path.with_suffix(".json.tmp").exists()


def test_scalar_window_refuses_residual_failed_episodes() -> None:
    drained = {
        "ns-a": {"failed": 0},
        "ns-b": {"failed": 1},
    }

    with pytest.raises(RuntimeError, match="ns-b=1"):
        ingest._require_no_failed_episodes(drained)


def test_main_submits_a_namespace_window_round_robin_and_manifests_after_drain(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    items = [
        {
            "question_id": "a",
            "question": "Question A?",
            "answer": "A",
            "question_type": "knowledge-update",
            "sessions": [[
                {"role": "user", "content": "a1"},
                {"role": "assistant", "content": "a2"},
                {"role": "user", "content": "a3"},
            ]],
        },
        {
            "question_id": "b",
            "question": "Question B?",
            "answer": "B",
            "question_type": "knowledge-update",
            "sessions": [[
                {"role": "user", "content": "b1"},
                {"role": "assistant", "content": "b2"},
            ]],
        },
        {
            "question_id": "c",
            "question": "Question C?",
            "answer": "C",
            "question_type": "knowledge-update",
            "sessions": [[
                {"role": "user", "content": "c1"},
            ]],
        },
    ]
    submitted: list[tuple[str, str]] = []
    reset: list[str] = []
    drain_calls: list[list[str]] = []

    class FakeAdapter:
        def load_items(self, **kwargs):
            return items

        def sessions(self, item):
            return item["sessions"]

        def question(self, item):
            return item["question"]

    class FakeClient:
        pass

    def fake_ingest_turn(client, namespace, role, content, **kwargs):
        submitted.append((namespace, content))
        return f"episode-{len(submitted)}"

    def fake_backend(admin, url, operation, body):
        assert operation == "fetch_episode_processing"
        return {"processing_state": "READY", "episode_uuid": body["episode_uuid"]}

    def fake_drain_many(namespaces, admin, url, **kwargs):
        drain_calls.append(namespaces)
        return {
            namespace: {
                "pending": 0,
                "ready": 2,
                "enriching": 0,
                "failed": 0,
                "llm_tasks": 10,
                "processing_attempts": 2,
                "total": 2,
                "timed_out": False,
            }
            for namespace in namespaces
        }

    monkeypatch.setattr(ingest, "LongMemEvalMemoryAdapter", FakeAdapter)
    monkeypatch.setattr(ingest, "HttpMenhirClient", lambda url: FakeClient())
    monkeypatch.setattr(ingest.httpx, "Client", lambda **kwargs: object())
    monkeypatch.setattr(ingest, "_ingest_turn", fake_ingest_turn)
    monkeypatch.setattr(ingest, "_backend", fake_backend)
    monkeypatch.setattr(ingest, "_drain_many", fake_drain_many)
    monkeypatch.setattr(
        ingest,
        "_reset_namespace",
        lambda admin, url, namespace: reset.append(namespace),
    )

    manifest_path = tmp_path / "manifest.json"
    result = ingest.main(
        [
            "--limit",
            "3",
            "--manifest-item-limit",
            "2",
            "--namespace-window",
            "2",
            "--segmentation",
            "none",
            "--manifest",
            str(manifest_path),
        ]
    )

    assert result == 0
    assert reset == ["lme-a", "lme-b"]
    assert submitted == [
        ("lme-a", "a1"),
        ("lme-b", "b1"),
        ("lme-a", "a2"),
        ("lme-b", "b2"),
        ("lme-a", "a3"),
    ]
    assert drain_calls == [["lme-a", "lme-b"]]
    manifest = ingest.json.loads(manifest_path.read_text(encoding="utf-8"))
    assert [row["question_id"] for row in manifest] == ["a", "b"]
    assert all(row["namespace_window"] == 2 for row in manifest)
    assert all(row["enrichment_llm_tasks"] == 10 for row in manifest)


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
