from __future__ import annotations

from pathlib import Path

from archolith_bench.ci import orchestrator
from archolith_bench.ci.budget_proxy import BudgetState


class _ExitedProcess:
    returncode = 1

    def poll(self) -> int:
        return self.returncode


def test_dry_run_needs_no_key_or_proxy(tmp_path: Path, monkeypatch) -> None:
    """The dry path must not create a proxy or talk to Menhir."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    def fail_proxy(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("dry-run must not start BudgetProxy")

    monkeypatch.setattr(orchestrator, "BudgetProxy", fail_proxy)
    repo_root = Path(__file__).parents[1]
    result = orchestrator.run_bench_for_pr(
        orchestrator.OrchestratorConfig(
            pr_number=91,
            head_sha="deadbeef",
            repo_root=str(repo_root),
            runs_dir=str(tmp_path),
            dry_run=True,
        )
    )

    assert not result.killed
    assert (tmp_path / "91" / "results.json").exists()
    assert not (tmp_path / "91" / "budget.json").exists()


def test_health_rejects_an_early_exiting_process() -> None:
    assert not orchestrator._wait_for_health(_ExitedProcess(), 65534, timeout_s=0.01)


def test_menhir_environment_strips_parent_credentials(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "real-key")
    monkeypatch.setenv("GITHUB_TOKEN", "github-secret")
    config = orchestrator.OrchestratorConfig(pr_number=17, head_sha="abc", runs_dir=str(tmp_path))

    env = orchestrator._build_menhir_env(config, "http://127.0.0.1:8765")

    assert env["OPENAI_API_KEY"] == "bench-proxy-holds-the-real-key"
    assert "GITHUB_TOKEN" not in env
    assert env["HOME"].endswith("fake-home")
    assert env["NEO4J_USER"] == "neo4j"
    assert "NEO4J_USERNAME" not in env
    assert env["MENHIR_BENCHMARK_MODE"] == "1"
    assert "BENCH_MODE" not in env


def test_call_reservation_prevents_concurrent_cap_overrun(tmp_path: Path) -> None:
    state = BudgetState(
        api_key="test",
        upstream="http://example.test",
        trace_file=tmp_path / "traces.jsonl",
        budget_file=tmp_path / "budget.json",
        max_calls=1,
        max_usd=5.0,
        max_seconds=60.0,
    )
    try:
        assert state.try_begin_call() is None
        assert state.try_begin_call() == "LLM call cap exceeded (1 / 1)"
        assert state.calls == 1
    finally:
        state.close()
