"""Industry benchmark registry for launch-readiness coverage.

This module does not run third-party harnesses directly. It records which
trusted external benchmark each Archolith product should be measured against,
what local coverage exists today, and which command or artifact gates launch
copy. Keeping this executable lets docs, CLI output, and tests share one source
of truth instead of copying benchmark names by hand.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class IndustryBenchmark:
    benchmark_id: str
    name: str
    product: str
    suite: str
    authority: str
    benchmark_type: str
    status: str
    source_url: str
    paper_url: str
    rationale: str
    local_coverage: str
    launch_gate: str
    run_command: str
    evidence_path: str


INDUSTRY_BENCHMARKS: tuple[IndustryBenchmark, ...] = (
    IndustryBenchmark(
        benchmark_id="ruler",
        name="RULER",
        product="archolith-context",
        suite="proxy",
        authority="NVIDIA",
        benchmark_type="long-context synthetic retrieval and aggregation",
        status="implemented-local",
        source_url="https://github.com/NVIDIA/RULER",
        paper_url="https://arxiv.org/abs/2404.06654",
        rationale=(
            "RULER is the closest external methodology for testing whether long-context systems can "
            "retrieve and aggregate facts across very long distractor contexts. That maps directly to "
            "archolith-context continuity, recall preservation, and repeated-read reduction."
        ),
        local_coverage=(
            "`scenarios/ruler_recall.json` is a RULER-STYLE smoke test (seeded-fact recall with late-turn "
            "probes): local, reproducible, useful for regression checks — but NOT an official RULER run and "
            "must not be advertised as a RULER score. Real RULER would be wired as a harness adapter."
        ),
        launch_gate=(
            "Run direct, proxy_only, and proxy_plus_filter on `ruler_recall`; publish recall preservation, "
            "upstream input reduction, and any quality regressions together."
        ),
        run_command=(
            "archolith-bench proxy --scenario scenarios/ruler_recall.json "
            "--arms direct,proxy_only,proxy_plus_filter --budgets 15000"
        ),
        evidence_path="benchmarks/proxy-ruler-recall-YYYY-MM-DD.md",
    ),
    IndustryBenchmark(
        benchmark_id="longbench-v2",
        name="LongBench v2",
        product="archolith-context",
        suite="proxy",
        authority="THUDM / Tsinghua",
        benchmark_type="realistic long-context multitask and code-repo understanding",
        status="candidate-before-launch",
        source_url="https://github.com/THUDM/LongBench",
        paper_url="https://arxiv.org/abs/2412.15204",
        rationale=(
            "LongBench v2 includes long-document, long-dialogue, structured-data, and code-repository "
            "understanding. It is relevant to the proxy's claim that curated context can preserve useful "
            "state without replaying the whole transcript."
        ),
        local_coverage=(
            "Official adapter implemented (`harness/longbench_v2.py`) — runs the real THUDM/LongBench-v2 "
            "multiple-choice set as a direct-vs-proxy A/B via `harness.run_ab`. Awaiting a tracked paid run; "
            "the result is the delta (accuracy preserved + tokens/cost reduced), not a standalone score."
        ),
        launch_gate=(
            "Run `archolith-bench harness longbench-v2` direct vs proxy on a real subset and publish the "
            "accuracy delta plus input-token and cost reduction as tracked evidence under benchmarks/."
        ),
        run_command=(
            "archolith-bench harness longbench-v2 --arms direct,proxy_only,proxy_plus_filter "
            "--subset single_document_qa --limit 50"
        ),
        evidence_path="benchmarks/proxy-longbench-v2-YYYY-MM-DD.md",
    ),
    IndustryBenchmark(
        benchmark_id="swe-bench",
        name="SWE-bench Lite / Verified",
        product="archolith-context",
        suite="proxy",
        authority="Princeton NLP / Stanford",
        benchmark_type="real GitHub issue resolution",
        status="candidate-before-launch",
        source_url="https://github.com/SWE-bench/SWE-bench",
        paper_url="https://arxiv.org/abs/2310.06770",
        rationale=(
            "SWE-bench is the trusted coding-agent benchmark for real issue resolution. It is relevant "
            "because archolith-context targets agent sessions that must retain repo state, decisions, "
            "and test feedback across multiple turns."
        ),
        local_coverage=(
            "Official adapter scaffolded (`harness/external.py` SweBenchAdapter) — wraps the SWE-bench "
            "evaluation harness per arm (client base_url = direct vs proxy) and parses its report into the "
            "A/B result. Real run needs an agent scaffold (e.g. SWE-agent) + Docker eval; deferred to step 3. "
            "`scenarios/{code_review,debugging,long_agent}.json` remain -style smoke tests, not SWE-bench scores."
        ),
        launch_gate=(
            "Run `archolith-bench harness swe-bench` on a Lite/Verified smoke subset, direct vs proxy, and "
            "report the resolution-rate delta + token/cost. Do not claim SWE-bench performance until this exists."
        ),
        run_command=(
            "archolith-bench harness swe-bench --subset princeton-nlp/SWE-bench_Lite --arms direct,proxy_only"
        ),
        evidence_path="benchmarks/proxy-swe-bench-smoke-YYYY-MM-DD.md",
    ),
    IndustryBenchmark(
        benchmark_id="bigcodebench-hard",
        name="BigCodeBench-Hard",
        product="archolith-context",
        suite="proxy",
        authority="BigCode Project",
        benchmark_type="function-level code generation with complex instructions",
        status="candidate-before-launch",
        source_url="https://github.com/bigcode-project/bigcodebench",
        paper_url="https://arxiv.org/abs/2406.15877",
        rationale=(
            "BigCodeBench-Hard is relevant as a compact, reproducible coding workload when full "
            "SWE-bench runs are too expensive. It is less agentic than SWE-bench, so it should be a "
            "secondary signal for proxy overhead and answer preservation."
        ),
        local_coverage=(
            "Official adapter implemented (`harness/bigcodebench.py`) — runs the real "
            "bigcode/bigcodebench-hard pass@1 (generated code executed in a sandboxed subprocess) as a "
            "direct-vs-proxy A/B via `harness.run_ab`. Awaiting a tracked paid run."
        ),
        launch_gate=(
            "Run `archolith-bench harness bigcodebench-hard` direct vs proxy and report the pass@1 delta "
            "plus token/cost reduction. Cheap proxy-overhead sanity check; report separately from "
            "multi-turn context claims."
        ),
        run_command=(
            "archolith-bench harness bigcodebench-hard --arms direct,proxy_only,proxy_plus_filter --limit 50"
        ),
        evidence_path="benchmarks/proxy-bigcodebench-hard-YYYY-MM-DD.md",
    ),
    IndustryBenchmark(
        benchmark_id="helm-efficiency",
        name="HELM efficiency metrics",
        product="archolith-filter",
        suite="filter",
        authority="Stanford CRFM",
        benchmark_type="holistic model evaluation including efficiency",
        status="implemented-local",
        source_url="https://github.com/stanford-crfm/helm",
        paper_url="https://openreview.net/forum?id=iO4LZibEqW",
        rationale=(
            "HELM is not a tool-output compression benchmark, but its efficiency framing is the trusted "
            "external evaluation lens for reporting token and cost effects alongside quality."
        ),
        local_coverage=(
            "`archolith-bench filter` reports raw tokens, filtered tokens, and savings by real tool-output "
            "category. This is the product-specific implementation of token-efficiency measurement."
        ),
        launch_gate=(
            "Run the filter suite on the launch corpus and publish per-category savings, total savings, "
            "sample count, corpus source, and known no-op categories."
        ),
        run_command="archolith-bench filter --corpora corpora/ --format markdown",
        evidence_path="benchmarks/filter-YYYY-MM-DD.md",
    ),
    IndustryBenchmark(
        benchmark_id="swe-bench-traces-filter",
        name="SWE-bench-style agent traces",
        product="archolith-filter",
        suite="filter",
        authority="Derived workload from SWE-bench-style coding sessions",
        benchmark_type="tool-output compression on coding-agent traces",
        status="candidate-before-launch",
        source_url="https://github.com/SWE-bench/SWE-bench",
        paper_url="https://arxiv.org/abs/2310.06770",
        rationale=(
            "The filter product should be tested on the same kind of logs it will compress: file reads, "
            "test output, search output, diffs, and shell traces from coding-agent issue-resolution runs."
        ),
        local_coverage=(
            "The current `corpora/` directory has real session samples across 8 categories. It should be "
            "expanded with SWE-bench-like agent traces before stronger launch claims."
        ),
        launch_gate=(
            "Add at least one tracked corpus summary showing sample provenance and category balance, then "
            "rerun `archolith-bench filter`."
        ),
        run_command="archolith-bench filter --corpora corpora/ --format markdown",
        evidence_path="benchmarks/filter-swe-style-traces-YYYY-MM-DD.md",
    ),
    IndustryBenchmark(
        benchmark_id="helm-token-accounting",
        name="HELM-style token/cost accounting",
        product="archolith-audit",
        suite="audit",
        authority="Stanford CRFM",
        benchmark_type="efficiency, transparency, and reproducibility reporting",
        status="implemented-local",
        source_url="https://github.com/stanford-crfm/helm",
        paper_url="https://openreview.net/forum?id=iO4LZibEqW",
        rationale=(
            "archolith-audit is not a model-quality benchmark. Its trusted external analogue is HELM's "
            "transparent reporting of efficiency metrics, with reproducible inputs and clear caveats."
        ),
        local_coverage=(
            "`archolith-bench audit` compares before/after MCP audit JSON reports and writes aggregate "
            "token and waste deltas. Current bundled fixtures are examples only."
        ),
        launch_gate=(
            "Use real before/after session logs, not fixtures. Publish server-level deltas and note any "
            "new waste type regressions."
        ),
        run_command=(
            "archolith-bench audit --before <real-before.json> --after <real-after.json> "
            "--format markdown"
        ),
        evidence_path="benchmarks/audit-live-before-after-YYYY-MM-DD.md",
    ),
    IndustryBenchmark(
        benchmark_id="longmemeval",
        name="LongMemEval",
        product="menhir",
        suite="memory",
        authority="Wu et al. (ICLR 2025)",
        benchmark_type="long-term interactive memory QA (extraction, multi-session, temporal, updates, abstention)",
        status="candidate-before-launch",
        source_url="https://github.com/xiaowu0162/LongMemEval",
        paper_url="https://arxiv.org/abs/2410.10813",
        rationale=(
            "This is menhir's CAPABILITY benchmark: can the memory system recall the right facts across a long, "
            "multi-session history? menhir is built on Graphiti (the temporal knowledge-graph engine Zep reports "
            "on LongMemEval/DMR), so this is the apples-to-apples industry standard for the product menhir is — "
            "unlike MTEB, which only measures the embedding sub-component."
        ),
        local_coverage=(
            "Official adapter implemented (`harness/longmemeval.py`, in-process) — runs LongMemEval QA as a "
            "direct (no/curated memory) vs proxy A/B; the proxy assembles relevant memory from the history. "
            "Deterministic normalized-containment scorer offline; the official GPT-4 judge can be added behind a "
            "flag. Awaiting a tracked run. Runs locally with the gemma chat model + local embeddings (cheap)."
        ),
        launch_gate=(
            "Run `archolith-bench harness longmemeval` direct (no memory) vs proxy/menhir and publish the "
            "memory-QA accuracy lift plus token/cost. This is menhir's primary, advertisable capability claim."
        ),
        run_command="archolith-bench harness longmemeval --arms direct,proxy_only,proxy_plus_filter --limit 50",
        evidence_path="benchmarks/longmemeval-YYYY-MM-DD.md",
    ),
    IndustryBenchmark(
        benchmark_id="dmr",
        name="Deep Memory Retrieval (DMR)",
        product="menhir",
        suite="memory",
        authority="MemGPT / Letta; reported by Zep",
        benchmark_type="memory retrieval accuracy over conversational history",
        status="candidate-before-launch",
        source_url="https://github.com/cpacker/MemGPT",
        paper_url="https://arxiv.org/abs/2310.08560",
        rationale=(
            "The second memory benchmark Zep/Graphiti report on, complementing LongMemEval. Registered under one "
            "roof; an adapter is not yet wired."
        ),
        local_coverage=(
            "No adapter yet. Candidate — wire after LongMemEval lands, reusing the same in-process A/B pattern."
        ),
        launch_gate=(
            "Either wire a DMR adapter and report a direct-vs-proxy retrieval-accuracy delta, or keep DMR a "
            "documented future benchmark and lead menhir's memory claim with LongMemEval."
        ),
        run_command="TODO: add a DMR adapter under harness/ (in-process, same pattern as longmemeval)",
        evidence_path="benchmarks/dmr-YYYY-MM-DD.md",
    ),
    IndustryBenchmark(
        benchmark_id="mteb-retrieval",
        name="MTEB retrieval/reranking slices",
        product="menhir",
        suite="memory",
        authority="Embeddings Benchmark / MTEB",
        benchmark_type="embedding retrieval/reranking (COMPONENT diagnostic, not the memory capability)",
        status="candidate-before-launch",
        source_url="https://github.com/embeddings-benchmark/mteb",
        paper_url="https://arxiv.org/abs/2210.07316",
        rationale=(
            "COMPONENT diagnostic only: MTEB measures the embedding model's retrieval quality, not the memory "
            "system end-to-end. Useful for an embedder-selection decision (e.g. free local nomic vs OpenAI "
            "text-embedding-3-small for menhir), NOT a memory capability claim. menhir's capability benchmark is "
            "LongMemEval (and DMR)."
        ),
        local_coverage=(
            "Official adapter (`harness/external.py` MtebAdapter) runs mteb against an OpenAI-compatible "
            "embeddings endpoint, defaulting to a local LM Studio server (text-embedding-nomic-embed-text-v1.5) "
            "— so it runs for FREE, no API spend, once the `mteb` extra is installed. SINGLE-ARM BASELINE: the "
            "embedding model is a menhir / fact-retrieval dependency, not the chat proxy path, so there is no "
            "direct-vs-proxy A/B (a real A/B needs an embeddings proxy/caching layer). Measures the embedding "
            "model menhir depends on, not the proxy."
        ),
        launch_gate=(
            "Run `archolith-bench harness mteb-retrieval` against the embeddings model and publish the MTEB "
            "score as a menhir/embedding-model baseline (not a proxy claim). A proxy A/B requires an "
            "embeddings layer that does not exist yet."
        ),
        run_command="archolith-bench harness mteb-retrieval --subset SciFact --arms direct",
        evidence_path="benchmarks/menhir-retrieval-YYYY-MM-DD.md",
    ),
    IndustryBenchmark(
        benchmark_id="cyberseceval-4",
        name="CyberSecEval 4",
        product="archolith-security",
        suite="security",
        authority="Meta / PurpleLlama",
        benchmark_type="LLM cybersecurity vulnerabilities and defensive capabilities",
        status="candidate-before-launch",
        source_url="https://github.com/meta-llama/PurpleLlama/tree/main/CybersecurityBenchmarks",
        paper_url="https://arxiv.org/abs/2408.01605",
        rationale=(
            "CyberSecEval is the closest external benchmark family for archolith-security's LLM "
            "security posture: prompt injection, insecure code generation, code interpreter risk, "
            "vulnerability exploitation, autonomous offensive operations, and defensive SOC/autopatch tasks."
        ),
        local_coverage=(
            "Official adapter scaffolded (`harness/external.py` CyberSecEvalAdapter) — wraps Meta "
            "PurpleLlama CybersecurityBenchmarks per arm and parses its stat file into the A/B result. "
            "Real run pending (archolith-security-owned, step 3); no score may be claimed yet."
        ),
        launch_gate=(
            "Run `archolith-bench harness cyberseceval-4` on a scoped subset, direct vs proxy, and publish "
            "pass/fail, refusal, and false-refusal caveats before any security benchmark claim."
        ),
        run_command=(
            "archolith-bench harness cyberseceval-4 --subset mitre --arms direct,proxy_only"
        ),
        evidence_path="benchmarks/security-cyberseceval-YYYY-MM-DD.md",
    ),
    IndustryBenchmark(
        benchmark_id="agentdojo",
        name="AgentDojo",
        product="archolith-security",
        suite="security",
        authority="ETH Zurich SPY Lab",
        benchmark_type="prompt injection attacks and defenses for tool-using agents",
        status="candidate-before-launch",
        source_url="https://github.com/ethz-spylab/agentdojo",
        paper_url="https://arxiv.org/abs/2406.13352",
        rationale=(
            "AgentDojo directly matches Archolith's agent/tool threat model: untrusted tool results, "
            "indirect prompt injection, data exfiltration attempts, and over-defense that breaks useful work."
        ),
        local_coverage=(
            "Official adapter scaffolded (`harness/external.py` AgentDojoAdapter) — wraps the AgentDojo "
            "runner per arm and parses utility-under-attack into the A/B result; attack-success-rate is "
            "reported alongside as the security signal. Real run pending (step 3)."
        ),
        launch_gate=(
            "Run `archolith-bench harness agentdojo` direct vs proxy and publish utility delta + "
            "attack-success-rate before claiming hardening against malicious tool output."
        ),
        run_command=(
            "archolith-bench harness agentdojo --subset workspace --arms direct,proxy_only"
        ),
        evidence_path="benchmarks/security-agentdojo-YYYY-MM-DD.md",
    ),
    IndustryBenchmark(
        benchmark_id="owasp-llm-asvs",
        name="OWASP LLM Top 10 + ASVS",
        product="archolith-context",
        suite="security",
        authority="OWASP Foundation",
        benchmark_type="LLM application and API security control verification",
        status="candidate-before-launch",
        source_url="https://owasp.org/www-project-top-10-for-large-language-model-applications/",
        paper_url="https://owasp.org/www-project-application-security-verification-standard/",
        rationale=(
            "The proxy exposes API, admin, trace, live-stream, memory, and plugin surfaces. OWASP LLM Top 10 "
            "covers LLM-specific risks such as prompt injection, data leakage, and excessive agency; ASVS "
            "anchors conventional application controls such as authentication, authorization, input validation, "
            "logging, and secure configuration."
        ),
        local_coverage=(
            "archolith-bench does not run an OWASP security audit. Recent launch audits identified admin/live "
            "stream exposure risks, but those are review findings rather than an automated benchmark."
        ),
        launch_gate=(
            "Complete a scoped OWASP LLM Top 10 + ASVS checklist for public proxy surfaces and track the "
            "findings/remediations before presenting the proxy as launch-safe."
        ),
        run_command=(
            "TODO: add archolith-bench security-checklist or link a tracked OWASP review artifact "
            "for archolith-context"
        ),
        evidence_path="benchmarks/security-owasp-context-YYYY-MM-DD.md",
    ),
)


def list_industry_benchmarks(
    product: str | None = None,
    suite: str | None = None,
    launch_only: bool = False,
) -> list[IndustryBenchmark]:
    """Return benchmark registry entries filtered by product/suite."""
    entries = list(INDUSTRY_BENCHMARKS)
    if product:
        entries = [entry for entry in entries if entry.product == product]
    if suite:
        entries = [entry for entry in entries if entry.suite == suite]
    if launch_only:
        entries = [entry for entry in entries if entry.status in {"implemented-local", "candidate-before-launch"}]
    return entries


def industry_benchmarks_json(
    product: str | None = None,
    suite: str | None = None,
    launch_only: bool = False,
) -> dict:
    """Serialize the benchmark registry to a stable JSON-compatible dict."""
    entries = list_industry_benchmarks(product=product, suite=suite, launch_only=launch_only)
    return {
        "suite": "industry",
        "total": len(entries),
        "filters": {
            "product": product,
            "suite": suite,
            "launch_only": launch_only,
        },
        "benchmarks": [asdict(entry) for entry in entries],
    }


def render_industry_benchmarks_markdown(
    product: str | None = None,
    suite: str | None = None,
    launch_only: bool = False,
) -> str:
    """Render the benchmark registry as a launch-facing markdown report."""
    entries = list_industry_benchmarks(product=product, suite=suite, launch_only=launch_only)
    lines: list[str] = [
        "# Industry-Trusted Benchmark Coverage\n\n",
        "This matrix maps each Archolith product to external benchmark families that are trusted enough ",
        "to anchor launch claims. `implemented-local` means archolith-bench has a local analogue or ",
        "reporting path today. `candidate-before-launch` means the benchmark is relevant but must not be ",
        "claimed until the listed gate has a tracked evidence artifact.\n\n",
        "| Product | Suite | Benchmark | Status | Launch gate |\n",
        "|---------|-------|-----------|--------|-------------|\n",
    ]
    for entry in entries:
        lines.append(
            f"| {entry.product} | {entry.suite} | {entry.name} | {entry.status} | "
            f"{entry.launch_gate} |\n"
        )

    lines.append("\n## Details\n\n")
    for entry in entries:
        lines.append(f"### {entry.name} ({entry.benchmark_id})\n\n")
        lines.append(f"- Product: `{entry.product}`\n")
        lines.append(f"- Suite: `{entry.suite}`\n")
        lines.append(f"- Authority: {entry.authority}\n")
        lines.append(f"- Type: {entry.benchmark_type}\n")
        lines.append(f"- Status: `{entry.status}`\n")
        lines.append(f"- Source: {entry.source_url}\n")
        lines.append(f"- Paper: {entry.paper_url}\n")
        lines.append(f"- Why relevant: {entry.rationale}\n")
        lines.append(f"- Local coverage: {entry.local_coverage}\n")
        lines.append(f"- Launch gate: {entry.launch_gate}\n")
        lines.append(f"- Command: `{entry.run_command}`\n")
        lines.append(f"- Evidence path: `{entry.evidence_path}`\n\n")
    return "".join(lines)


def write_industry_benchmarks(
    out_path: Path,
    *,
    product: str | None = None,
    suite: str | None = None,
    launch_only: bool = False,
    output_format: str = "markdown",
) -> Path:
    """Write the benchmark registry to markdown or JSON."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if output_format == "json":
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(
                industry_benchmarks_json(product=product, suite=suite, launch_only=launch_only),
                f,
                indent=2,
                ensure_ascii=False,
            )
    else:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(
                render_industry_benchmarks_markdown(
                    product=product,
                    suite=suite,
                    launch_only=launch_only,
                )
            )
    return out_path
