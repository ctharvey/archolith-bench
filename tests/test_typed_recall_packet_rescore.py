from __future__ import annotations

import pytest

from scripts.longmemeval.analysis.run_typed_recall_packet_rescore import (
    DEFAULT_PROVIDER_BASE_URL,
    PACKET_VERSION,
    QUERY_FILTERED_PACKET_VERSION,
    QueryFilteredTypedPacketClient,
    TypedRecallPacketClient,
    build_comparison,
    require_complete_model_evidence,
)

from archolith_bench.harness import ABResult, ArmResult, TaskResult


class _Response:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self.payload


class _Http:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.urls: list[str] = []
        self.posts: list[tuple[str, dict]] = []

    def get(self, url: str, *, headers: dict[str, str]) -> _Response:
        self.urls.append(url)
        assert headers == {}
        return _Response(self.payload)

    def post(self, url: str, *, headers: dict[str, str], json: dict) -> _Response:
        self.urls.append(url)
        self.posts.append((url, json))
        assert headers == {}
        return _Response(self.payload)


def _payload(**overrides: object) -> dict:
    payload = {
        "contract": "bench-inspection/v1",
        "namespace": "lme-demo",
        "question": "What is current?",
        "graph_available": True,
        "live_graph": {
            "recall_packet": {
                "version": PACKET_VERSION,
                "production_recall_changed": False,
                "text": f"MEMORY PACKET {PACKET_VERSION}\n[AUTHORITATIVE CURRENT STATE]\n- x = 2",
            }
        },
    }
    payload.update(overrides)
    return payload


def test_client_returns_exact_packet_as_one_context_document() -> None:
    client = TypedRecallPacketClient("http://recall-lab", source_run_id="canonical/run")
    fake = _Http(_payload())
    client._client = fake

    recalled = client.recall("lme-demo", "What is current?", limit=99)

    assert recalled == [
        f"MEMORY PACKET {PACKET_VERSION}\n[AUTHORITATIVE CURRENT STATE]\n- x = 2"
    ]
    assert fake.urls == [
        "http://recall-lab/explorer/api/recall-lab/bench-runs/canonical%2Frun/tasks/lme-demo"
    ]


def test_query_filtered_client_posts_query_and_budget() -> None:
    text = f"MEMORY PACKET {QUERY_FILTERED_PACKET_VERSION}\n[GENERAL CONTENT]\n- x"
    payload = {
        "contract": QUERY_FILTERED_PACKET_VERSION,
        "namespace": "lme-demo",
        "packet": {
            "version": QUERY_FILTERED_PACKET_VERSION,
            "production_recall_changed": False,
            "text": text,
        },
    }
    client = QueryFilteredTypedPacketClient(
        "http://recall-lab",
        source_run_id="canonical/run",
        max_chars=4321,
        max_general=4,
    )
    fake = _Http(payload)
    client._client = fake

    assert client.recall("lme-demo", "What is current?", limit=7) == [text]
    assert fake.posts == [
        (
            "http://recall-lab/explorer/api/recall-lab/bench-runs/"
            "canonical%2Frun/tasks/lme-demo/recall-packet",
            {
                "query": "What is current?",
                "limit": 7,
                "max_chars": 4321,
                "max_general": 4,
            },
        )
    ]


def test_query_filtered_client_refuses_contract_drift() -> None:
    client = QueryFilteredTypedPacketClient("http://recall-lab")
    client._client = _Http({"contract": "wrong", "namespace": "lme-demo"})
    with pytest.raises(RuntimeError, match="unexpected query-filtered contract"):
        client.recall("lme-demo", "What is current?")


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (_payload(contract="wrong"), "unexpected Recall Lab contract"),
        (_payload(graph_available=False), "live graph is unavailable"),
        (_payload(question="Different"), "fixture/API question mismatch"),
        (
            _payload(
                live_graph={
                    "recall_packet": {
                        "version": "different",
                        "production_recall_changed": False,
                        "text": "anything",
                    }
                }
            ),
            "unexpected packet version",
        ),
    ],
)
def test_client_refuses_projection_drift(payload: dict, message: str) -> None:
    client = TypedRecallPacketClient("http://recall-lab")
    client._client = _Http(payload)

    with pytest.raises(RuntimeError, match=message):
        client.recall("lme-demo", "What is current?")


def _row(correct: bool, *, answer_in: int, judge_in: int) -> dict:
    return {
        "correct": correct,
        "input_tokens": answer_in,
        "output_tokens": 2,
        "scorer_input_tokens": judge_in,
        "scorer_output_tokens": 1,
    }


def test_build_comparison_reports_transitions_and_all_token_classes() -> None:
    baseline = {
        "recovered": _row(False, answer_in=10, judge_in=20),
        "regressed": _row(True, answer_in=11, judge_in=21),
        "pass": _row(True, answer_in=12, judge_in=22),
        "fail": _row(False, answer_in=13, judge_in=23),
        "baseline-only": _row(True, answer_in=99, judge_in=99),
    }
    candidate = {
        "recovered": _row(True, answer_in=30, judge_in=40),
        "regressed": _row(False, answer_in=31, judge_in=41),
        "pass": _row(True, answer_in=32, judge_in=42),
        "fail": _row(False, answer_in=33, judge_in=43),
        "candidate-only": _row(True, answer_in=99, judge_in=99),
    }

    comparison = build_comparison(baseline, candidate)

    assert comparison["n"] == 4
    assert comparison["baseline"]["correct"] == 2
    assert comparison["candidate"]["correct"] == 2
    assert comparison["score_delta"] == 0
    assert comparison["transitions"] == {
        "recovered": ["recovered"],
        "regressed": ["regressed"],
        "stayed_pass": ["pass"],
        "stayed_fail": ["fail"],
    }
    assert comparison["baseline"]["tokens"] == {
        "answer_input": 46,
        "answer_output": 8,
        "judge_input": 86,
        "judge_output": 4,
        "total": 144,
    }
    assert comparison["missing_from_candidate"] == ["baseline-only"]
    assert comparison["missing_from_baseline"] == ["candidate-only"]


def _ab_result(*results: TaskResult) -> ABResult:
    arm = ArmResult(
        arm="menhir_recall",
        n=len(results),
        score=1.0,
        input_tokens=sum(result.input_tokens for result in results),
        output_tokens=sum(result.output_tokens for result in results),
        cost_usd=0.0,
        results=list(results),
    )
    return ABResult(
        benchmark_id="demo",
        name="demo",
        model="gpt-4o-mini",
        subset="knowledge-update",
        arms={arm.arm: arm},
        deltas={},
    )


def _model_result(response: str = "answer") -> TaskResult:
    return TaskResult(
        task_id="demo",
        response_text=response,
        input_tokens=10,
        output_tokens=2,
        latency_ms=1.0,
        correct=True,
        scorer_input_tokens=20,
        scorer_output_tokens=1,
    )


def test_complete_model_evidence_accepts_answer_and_judge_usage() -> None:
    require_complete_model_evidence(_ab_result(_model_result()), expected_items=1)


def test_provider_default_is_openai_not_the_generic_bench_upstream() -> None:
    assert DEFAULT_PROVIDER_BASE_URL == "https://api.openai.com/v1"


@pytest.mark.parametrize(
    "result",
    [
        _model_result("[ERROR 401]: invalid key"),
        TaskResult(
            task_id="demo",
            response_text="answer",
            input_tokens=0,
            output_tokens=0,
            latency_ms=1.0,
            correct=False,
            scorer_input_tokens=0,
            scorer_output_tokens=0,
        ),
    ],
)
def test_complete_model_evidence_rejects_failed_calls(result: TaskResult) -> None:
    with pytest.raises(RuntimeError, match="refusing to write a quality comparison"):
        require_complete_model_evidence(_ab_result(result), expected_items=1)
