"""Token-estimator validation suite for CORR-07."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from statistics import median
from time import perf_counter

from archolith_bench.core.metrics import estimate_messages_tokens, estimate_tokens


@dataclass(frozen=True)
class TokenEstimatorSample:
    """Representative text fixture for estimator validation."""

    name: str
    content_type: str
    text: str


@dataclass(frozen=True)
class TokenEstimatorMeasurement:
    """Accuracy and latency result for one sample."""

    sample: TokenEstimatorSample
    heuristic_tokens: int
    estimator_tokens: int
    exact_tokens: int | None
    heuristic_error_pct: float | None
    estimator_latency_p50_ms: float
    estimator_latency_p95_ms: float
    estimator_latency_p99_ms: float
    runs: int


def _legacy_char_divide_estimate(text: str) -> int:
    return max(1, len(text) // 4)


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = int(round((len(ordered) - 1) * percentile))
    return ordered[index]


def _exact_tokens(text: str) -> int | None:
    try:
        import tiktoken
    except ImportError:
        return None
    return len(tiktoken.get_encoding("cl100k_base").encode(text))


def measure_sample(sample: TokenEstimatorSample, *, runs: int = 100) -> TokenEstimatorMeasurement:
    """Measure estimator accuracy and latency for a sample."""
    timings: list[float] = []
    estimator_tokens = 0
    for _ in range(runs):
        started = perf_counter()
        estimator_tokens = estimate_tokens(sample.text)
        timings.append((perf_counter() - started) * 1000)

    exact = _exact_tokens(sample.text)
    heuristic = _legacy_char_divide_estimate(sample.text)
    heuristic_error_pct = None
    if exact:
        heuristic_error_pct = ((heuristic - exact) / exact) * 100

    return TokenEstimatorMeasurement(
        sample=sample,
        heuristic_tokens=heuristic,
        estimator_tokens=estimator_tokens,
        exact_tokens=exact,
        heuristic_error_pct=heuristic_error_pct,
        estimator_latency_p50_ms=median(timings),
        estimator_latency_p95_ms=_percentile(timings, 0.95),
        estimator_latency_p99_ms=_percentile(timings, 0.99),
        runs=runs,
    )


def load_corpus_samples(corpora_dir: Path) -> list[TokenEstimatorSample]:
    """Load text corpora from a directory, classifying by filename suffix."""
    samples: list[TokenEstimatorSample] = []
    for path in sorted(corpora_dir.glob("*.txt")):
        content_type = path.stem.split("-")[0] if "-" in path.stem else "text"
        samples.append(
            TokenEstimatorSample(
                name=path.stem,
                content_type=content_type,
                text=path.read_text(encoding="utf-8"),
            )
        )
    return samples


def measure_samples(samples: list[TokenEstimatorSample], *, runs: int = 100) -> list[TokenEstimatorMeasurement]:
    """Measure all samples with the same run count."""
    return [measure_sample(sample, runs=runs) for sample in samples]


def compare_message_shapes(single_text: str, many_messages: list[dict]) -> dict[str, int]:
    """Compare single-message and many-message OpenAI content token estimates."""
    return {
        "single_message_tokens": estimate_tokens(single_text),
        "many_message_tokens": estimate_messages_tokens(many_messages),
    }


def write_markdown_report(
    measurements: list[TokenEstimatorMeasurement],
    output_path: Path,
    *,
    message_shape_tokens: dict[str, int] | None = None,
) -> None:
    """Write a markdown report for the token-estimator suite."""
    lines = [
        "# Token Estimator Validation",
        "",
        "CORR-07 validation for `archolith-bench` token estimation. This suite measures the old "
        "`len(text) // 4` heuristic against the benchmark estimator, which uses `cl100k_base` when "
        "`tiktoken` is available and keeps the heuristic only as an optional-dependency fallback.",
        "",
        "## Accuracy And Latency",
        "",
        "| Corpus | Type | Runs | Heuristic | Estimator | Exact | Heuristic Error | p50 ms | p95 ms | p99 ms |",
        "|--------|------|------|-----------|-----------|-------|-----------------|--------|--------|--------|",
    ]
    for result in measurements:
        exact = str(result.exact_tokens) if result.exact_tokens is not None else "n/a"
        error = "n/a"
        if result.heuristic_error_pct is not None:
            error = f"{result.heuristic_error_pct:+.1f}%"
        lines.append(
            f"| {result.sample.name} | {result.sample.content_type} | {result.runs} | "
            f"{result.heuristic_tokens} | {result.estimator_tokens} | {exact} | {error} | "
            f"{result.estimator_latency_p50_ms:.3f} | {result.estimator_latency_p95_ms:.3f} | "
            f"{result.estimator_latency_p99_ms:.3f} |"
        )

    if message_shape_tokens:
        lines.extend(
            [
                "",
                "## Message Shape",
                "",
                f"- Single large message: {message_shape_tokens['single_message_tokens']} tokens",
                f"- Many small messages: {message_shape_tokens['many_message_tokens']} tokens",
            ]
        )

    lines.extend(
        [
            "",
            "## Decision",
            "",
            "`archolith-bench` should use `tiktoken` `cl100k_base` when present. The char-count fallback "
            "is retained only for environments without the optional tokenizer. No `archolith-context` "
            "production estimator change is made by this validation.",
            "",
        ]
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
