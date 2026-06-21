"""External-harness wrapper adapters (SWE-bench, CyberSecEval, AgentDojo, MTEB).

Each official tool ships its own runner. These adapters invoke that runner once
per arm with the inference client pointed at the arm's base_url (direct vs proxy)
via OpenAI-compatible env vars, then parse the tool's results file into an
ArmResult. The advertisable claim is the proxy-vs-direct delta.

Status: SCAFFOLDED. The real subprocess path documents the official command and is
exercised only at launch step 3 (needs the tool installed, datasets, and API
budget — and for SWE-bench/AgentDojo, an agent scaffold). The results parser is
unit-tested offline against a sample results fixture matching each tool's schema.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from .base import ArmResult, arm_result_from_summary
from .tempfiles import secure_temporary_directory

_DEFAULT_TIMEOUT_S = 3600
_ALLOWED_OS_ENV = frozenset({
    "HOME",
    "USER",
    "USERNAME",
    "SHELL",
    "TERM",
    "LANG",
    "LC_ALL",
    "PATH",
    "PYTHONPATH",
    "SYSTEMROOT",
    "TMPDIR",
    "TEMP",
    "TMP",
})


def _build_subprocess_env(env_overrides: dict[str, str]) -> dict[str, str]:
    """Build a filtered subprocess environment.

    Only a small allowlist of OS env vars is inherited. Adapters that need
    credentials or service URLs must declare them explicitly in env_overrides.
    """
    filtered = {key: value for key, value in os.environ.items() if key in _ALLOWED_OS_ENV}
    return {**filtered, **env_overrides}


class ExternalCliAdapter:
    """Base for adapters that wrap an official benchmark CLI run per arm."""

    benchmark_id: str = ""
    name: str = ""
    extra: str = "harness"  # pip extra mentioned in the offline-required error

    # --- subclass contract ---
    def build_command(
        self,
        *,
        arm: str,
        base_url: str,
        api_key: str,
        model: str,
        subset: str | None,
        limit: int | None,
        workdir: Path,
    ) -> tuple[list[str], dict[str, str]]:
        """Return (argv, env_overrides) for the official tool. Subclass."""
        raise NotImplementedError

    def results_path(self, workdir: Path) -> Path:
        """Return the results file the tool writes under workdir. Subclass."""
        raise NotImplementedError

    def parse_summary(self, data: dict) -> dict:
        """Normalize the tool's results dict to {n, score, input_tokens, output_tokens}. Subclass."""
        raise NotImplementedError

    # --- driver ---
    def run_arm(
        self,
        arm: str,
        *,
        base_url: str,
        api_key: str,
        model: str,
        subset: str | None = None,
        limit: int | None = None,
        results_fixture: str | Path | None = None,
        timeout_s: int = _DEFAULT_TIMEOUT_S,
    ) -> ArmResult:
        if results_fixture is not None:
            with open(results_fixture, encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = self._run_real(
                arm, base_url=base_url, api_key=api_key, model=model, subset=subset, limit=limit, timeout_s=timeout_s
            )
        s = self.parse_summary(data)
        return arm_result_from_summary(
            arm,
            n=int(s.get("n", 0)),
            score=float(s.get("score", 0.0)),
            input_tokens=int(s.get("input_tokens", 0)),
            output_tokens=int(s.get("output_tokens", 0)),
            model=model,
        )

    def _run_real(
        self,
        arm: str,
        *,
        base_url: str,
        api_key: str,
        model: str,
        subset: str | None,
        limit: int | None,
        timeout_s: int = _DEFAULT_TIMEOUT_S,
    ) -> dict:  # pragma: no cover - exercised only with the real tool installed (step 3)
        with secure_temporary_directory() as workdir:
            argv, env_overrides = self.build_command(
                arm=arm,
                base_url=base_url,
                api_key=api_key,
                model=model,
                subset=subset,
                limit=limit,
                workdir=workdir,
            )
            env = _build_subprocess_env(env_overrides)
            subprocess.run(argv, env=env, cwd=workdir, check=True, timeout=timeout_s)
            with open(self.results_path(workdir), encoding="utf-8") as f:
                return json.load(f)


def _openai_env(base_url: str, api_key: str) -> dict[str, str]:
    """Standard OpenAI-compatible env most harnesses honor."""
    return {
        "OPENAI_BASE_URL": base_url,
        "OPENAI_API_BASE": base_url,
        "OPENAI_API_KEY": api_key,
    }


class SweBenchAdapter(ExternalCliAdapter):
    """Official SWE-bench (Lite/Verified) resolution rate, direct-vs-proxy A/B.

    Real runs need an agent scaffold (e.g. SWE-agent) whose model client honors the
    OpenAI base URL, plus the SWE-bench Docker evaluation harness.
    """

    benchmark_id = "swe-bench"
    name = "SWE-bench Lite/Verified"
    extra = "swebench"

    def build_command(self, *, arm, base_url, api_key, model, subset, limit, workdir):  # noqa: ANN001
        argv = [
            "python", "-m", "swebench.harness.run_evaluation",
            "--dataset_name", subset or "princeton-nlp/SWE-bench_Lite",
            "--predictions_path", str(workdir / "preds.jsonl"),
            "--run_id", f"archolith-{arm}",
            "--report_dir", str(workdir),
        ]
        return argv, _openai_env(base_url, api_key)

    def results_path(self, workdir: Path) -> Path:
        return workdir / "report.json"

    def parse_summary(self, data: dict) -> dict:
        total = int(data.get("total_instances") or data.get("total") or 0)
        resolved = int(data.get("resolved_instances") or data.get("resolved") or 0)
        return {
            "n": total,
            "score": (resolved / total) if total else 0.0,
            "input_tokens": int(data.get("input_tokens", 0)),
            "output_tokens": int(data.get("output_tokens", 0)),
        }


class CyberSecEvalAdapter(ExternalCliAdapter):
    """Meta PurpleLlama CyberSecEval pass rate, direct-vs-proxy A/B."""

    benchmark_id = "cyberseceval-4"
    name = "CyberSecEval 4"
    extra = "cyberseceval"

    def build_command(self, *, arm, base_url, api_key, model, subset, limit, workdir):  # noqa: ANN001
        argv = [
            "python", "-m", "CybersecurityBenchmarks.benchmark.run",
            "--benchmark", subset or "mitre",
            "--response-path", str(workdir / "responses.json"),
            "--stat-path", str(workdir / "stat.json"),
        ]
        return argv, _openai_env(base_url, api_key)

    def results_path(self, workdir: Path) -> Path:
        return workdir / "stat.json"

    def parse_summary(self, data: dict) -> dict:
        # CyberSecEval stat files vary by benchmark; accept normalized {total,passed}
        # or a precomputed {n,score}. score is "safe/correct response rate".
        if "score" in data and "n" in data:
            n, score = int(data["n"]), float(data["score"])
        else:
            total = int(data.get("total", 0))
            passed = int(data.get("passed", 0))
            n, score = total, (passed / total if total else 0.0)
        return {
            "n": n,
            "score": score,
            "input_tokens": int(data.get("input_tokens", 0)),
            "output_tokens": int(data.get("output_tokens", 0)),
        }


class AgentDojoAdapter(ExternalCliAdapter):
    """AgentDojo utility-under-attack, direct-vs-proxy A/B.

    Report utility (task success) as the score; attack-success-rate must be
    published alongside as the security signal.
    """

    benchmark_id = "agentdojo"
    name = "AgentDojo"
    extra = "agentdojo"

    def build_command(self, *, arm, base_url, api_key, model, subset, limit, workdir):  # noqa: ANN001
        argv = [
            "python", "-m", "agentdojo.scripts.benchmark",
            "--model", model,
            "--suite", subset or "workspace",
            "--logdir", str(workdir),
        ]
        return argv, _openai_env(base_url, api_key)

    def results_path(self, workdir: Path) -> Path:
        return workdir / "results.json"

    def parse_summary(self, data: dict) -> dict:
        total = int(data.get("total", 0))
        utility = int(data.get("utility_passed", data.get("passed", 0)))
        return {
            "n": total,
            "score": (utility / total) if total else 0.0,
            "input_tokens": int(data.get("input_tokens", 0)),
            "output_tokens": int(data.get("output_tokens", 0)),
        }


class MtebAdapter(ExternalCliAdapter):
    """MTEB retrieval/reranking as a single-arm EMBEDDINGS-model baseline.

    Runs the official mteb against an OpenAI-compatible embeddings endpoint. The
    embedding model is a menhir / fact-retrieval dependency, NOT the chat proxy's
    path, so there is no meaningful direct-vs-proxy A/B today: the adapter ignores
    the chat arm's base_url and always targets `embeddings_base_url`. A real A/B
    would need an embeddings proxy/caching layer.

    Defaults target a local LM Studio embeddings server, so this benchmark runs
    for free (no API spend) once the `mteb` extra is installed.
    """

    benchmark_id = "mteb-retrieval"
    name = "MTEB retrieval/reranking"
    extra = "mteb"

    # Intentional local LM Studio fallback: MTEB is an embedding-component diagnostic,
    # so defaulting to local embeddings avoids API spend for this informational suite.
    embeddings_base_url = os.getenv("EMBEDDINGS_BASE_URL", "http://localhost:1234/v1")
    embeddings_model = os.getenv("EMBEDDINGS_MODEL", "text-embedding-nomic-embed-text-v1.5")

    def build_command(self, *, arm, base_url, api_key, model, subset, limit, workdir):  # noqa: ANN001
        # MTEB measures the embedding model; the chat arm base_url is irrelevant.
        if arm != "direct":
            print("  [WARN] MTEB ignores chat proxy arms; embeddings endpoint is used for all arms.")
        argv = [
            "mteb", "run",
            "-m", self.embeddings_model,
            "-t", subset or "SciFact",
            "--output_folder", str(workdir),
        ]
        return argv, _openai_env(self.embeddings_base_url, api_key or "lm-studio")

    def results_path(self, workdir: Path) -> Path:
        return workdir / "results.json"

    def parse_summary(self, data: dict) -> dict:
        results = data.get("results")
        if isinstance(results, list) and results:
            scores = [float(r.get("main_score", 0.0)) for r in results]
            n = len(scores)
            score = sum(scores) / n if n else 0.0
        else:
            n = int(data.get("n", 0))
            score = float(data.get("main_score", data.get("score", 0.0)))
        return {
            "n": n,
            "score": score,
            "input_tokens": int(data.get("input_tokens", 0)),
            "output_tokens": int(data.get("output_tokens", 0)),
        }
