# Industry-Trusted Benchmark Coverage

This matrix maps each Archolith product to external benchmark families that are trusted enough to anchor launch claims. `implemented-local` means archolith-bench has a local analogue or reporting path today. `candidate-before-launch` means the benchmark is relevant but must not be claimed until the listed gate has a tracked evidence artifact.

| Product | Suite | Benchmark | Status | Launch gate |
|---------|-------|-----------|--------|-------------|
| archolith-context | proxy | RULER | implemented-local | Run direct, proxy_only, and proxy_plus_filter on `ruler_recall`; publish recall preservation, upstream input reduction, and any quality regressions together. |
| archolith-context | proxy | LongBench v2 | candidate-before-launch | Before making any industry-backed context-quality claim, add a small adapter or documented manual run for the code-repo and long-dialogue subsets, then compare direct vs proxy answers. |
| archolith-context | proxy | SWE-bench Lite / Verified | candidate-before-launch | Run at least a smoke subset through the same model direct vs proxy and report pass/fail, token/cost, and any patch-quality regression. Do not claim SWE-bench performance until this exists. |
| archolith-context | proxy | BigCodeBench-Hard | candidate-before-launch | Optional before launch; useful for a cheap proxy-overhead sanity check. Report it separately from multi-turn context claims. |
| archolith-filter | filter | HELM efficiency metrics | implemented-local | Run the filter suite on the launch corpus and publish per-category savings, total savings, sample count, corpus source, and known no-op categories. |
| archolith-filter | filter | SWE-bench-style agent traces | candidate-before-launch | Add at least one tracked corpus summary showing sample provenance and category balance, then rerun `archolith-bench filter`. |
| archolith-audit | audit | HELM-style token/cost accounting | implemented-local | Use real before/after session logs, not fixtures. Publish server-level deltas and note any new waste type regressions. |
| menhir | memory | MTEB retrieval/reranking slices | candidate-before-launch | Do not make durable-memory retrieval claims from archolith-bench until a Menhir-owned MTEB-style or project-memory retrieval evaluation exists. |
| archolith-security | security | CyberSecEval 4 | candidate-before-launch | Before making security benchmark claims, run a scoped CyberSecEval subset relevant to the released products and publish pass/fail, refusal, and false-refusal caveats. |
| archolith-security | security | AgentDojo | candidate-before-launch | Run or explicitly defer an AgentDojo-style prompt-injection evaluation for proxy/tool workflows before claiming security hardening against malicious tool output. |
| archolith-context | security | OWASP LLM Top 10 + ASVS | candidate-before-launch | Complete a scoped OWASP LLM Top 10 + ASVS checklist for public proxy surfaces and track the findings/remediations before presenting the proxy as launch-safe. |

## Details

### RULER (ruler)

- Product: `archolith-context`
- Suite: `proxy`
- Authority: NVIDIA
- Type: long-context synthetic retrieval and aggregation
- Status: `implemented-local`
- Source: https://github.com/NVIDIA/RULER
- Paper: https://arxiv.org/abs/2404.06654
- Why relevant: RULER is the closest external methodology for testing whether long-context systems can retrieve and aggregate facts across very long distractor contexts. That maps directly to archolith-context continuity, recall preservation, and repeated-read reduction.
- Local coverage: `scenarios/ruler_recall.json` implements a RULER-style seeded-fact recall workload with late-turn probes. It is local and reproducible, but not a leaderboard-equivalent RULER run.
- Launch gate: Run direct, proxy_only, and proxy_plus_filter on `ruler_recall`; publish recall preservation, upstream input reduction, and any quality regressions together.
- Command: `archolith-bench proxy --scenario scenarios/ruler_recall.json --arms direct,proxy_only,proxy_plus_filter --budgets 15000`
- Evidence path: `benchmarks/proxy-ruler-recall-YYYY-MM-DD.md`

### LongBench v2 (longbench-v2)

- Product: `archolith-context`
- Suite: `proxy`
- Authority: THUDM / Tsinghua
- Type: realistic long-context multitask and code-repo understanding
- Status: `candidate-before-launch`
- Source: https://github.com/THUDM/LongBench
- Paper: https://arxiv.org/abs/2412.15204
- Why relevant: LongBench v2 includes long-document, long-dialogue, structured-data, and code-repository understanding. It is relevant to the proxy's claim that curated context can preserve useful state without replaying the whole transcript.
- Local coverage: `scenarios/long_agent.json` is a local long-agent analogue. A real LongBench v2 adapter is not implemented yet and should not be claimed as completed.
- Launch gate: Before making any industry-backed context-quality claim, add a small adapter or documented manual run for the code-repo and long-dialogue subsets, then compare direct vs proxy answers.
- Command: `TODO: add archolith-bench proxy-longbench --subset code_repo,long_dialogue or a documented external LongBench v2 run artifact`
- Evidence path: `benchmarks/proxy-longbench-v2-YYYY-MM-DD.md`

### SWE-bench Lite / Verified (swe-bench-lite)

- Product: `archolith-context`
- Suite: `proxy`
- Authority: Princeton NLP / Stanford
- Type: real GitHub issue resolution
- Status: `candidate-before-launch`
- Source: https://github.com/SWE-bench/SWE-bench
- Paper: https://arxiv.org/abs/2310.06770
- Why relevant: SWE-bench is the trusted coding-agent benchmark for real issue resolution. It is relevant because archolith-context targets agent sessions that must retain repo state, decisions, and test feedback across multiple turns.
- Local coverage: `scenarios/code_review.json`, `scenarios/debugging.json`, and `scenarios/long_agent.json` cover local SWE-bench-like behaviors but are not SWE-bench results.
- Launch gate: Run at least a smoke subset through the same model direct vs proxy and report pass/fail, token/cost, and any patch-quality regression. Do not claim SWE-bench performance until this exists.
- Command: `TODO: wrap SWE-bench inference/evaluation with direct vs proxy base URLs, then run a small Lite/Verified smoke subset before broad OSS promotion`
- Evidence path: `benchmarks/proxy-swe-bench-smoke-YYYY-MM-DD.md`

### BigCodeBench-Hard (bigcodebench-hard)

- Product: `archolith-context`
- Suite: `proxy`
- Authority: BigCode Project
- Type: function-level code generation with complex instructions
- Status: `candidate-before-launch`
- Source: https://github.com/bigcode-project/bigcodebench
- Paper: https://arxiv.org/abs/2406.15877
- Why relevant: BigCodeBench-Hard is relevant as a compact, reproducible coding workload when full SWE-bench runs are too expensive. It is less agentic than SWE-bench, so it should be a secondary signal for proxy overhead and answer preservation.
- Local coverage: No direct local BigCodeBench adapter exists. Existing coding scenarios are multi-turn agent workloads rather than function-level benchmark tasks.
- Launch gate: Optional before launch; useful for a cheap proxy-overhead sanity check. Report it separately from multi-turn context claims.
- Command: `TODO: add direct/proxy OpenAI-compatible backend configuration for BigCodeBench-Hard or keep this as a later benchmark`
- Evidence path: `benchmarks/proxy-bigcodebench-hard-YYYY-MM-DD.md`

### HELM efficiency metrics (helm-efficiency)

- Product: `archolith-filter`
- Suite: `filter`
- Authority: Stanford CRFM
- Type: holistic model evaluation including efficiency
- Status: `implemented-local`
- Source: https://github.com/stanford-crfm/helm
- Paper: https://openreview.net/forum?id=iO4LZibEqW
- Why relevant: HELM is not a tool-output compression benchmark, but its efficiency framing is the trusted external evaluation lens for reporting token and cost effects alongside quality.
- Local coverage: `archolith-bench filter` reports raw tokens, filtered tokens, and savings by real tool-output category. This is the product-specific implementation of token-efficiency measurement.
- Launch gate: Run the filter suite on the launch corpus and publish per-category savings, total savings, sample count, corpus source, and known no-op categories.
- Command: `archolith-bench filter --corpora corpora/ --format markdown`
- Evidence path: `benchmarks/filter-YYYY-MM-DD.md`

### SWE-bench-style agent traces (swe-bench-traces-filter)

- Product: `archolith-filter`
- Suite: `filter`
- Authority: Derived workload from SWE-bench-style coding sessions
- Type: tool-output compression on coding-agent traces
- Status: `candidate-before-launch`
- Source: https://github.com/SWE-bench/SWE-bench
- Paper: https://arxiv.org/abs/2310.06770
- Why relevant: The filter product should be tested on the same kind of logs it will compress: file reads, test output, search output, diffs, and shell traces from coding-agent issue-resolution runs.
- Local coverage: The current `corpora/` directory has real session samples across 8 categories. It should be expanded with SWE-bench-like agent traces before stronger launch claims.
- Launch gate: Add at least one tracked corpus summary showing sample provenance and category balance, then rerun `archolith-bench filter`.
- Command: `archolith-bench filter --corpora corpora/ --format markdown`
- Evidence path: `benchmarks/filter-swe-style-traces-YYYY-MM-DD.md`

### HELM-style token/cost accounting (helm-token-accounting)

- Product: `archolith-audit`
- Suite: `audit`
- Authority: Stanford CRFM
- Type: efficiency, transparency, and reproducibility reporting
- Status: `implemented-local`
- Source: https://github.com/stanford-crfm/helm
- Paper: https://openreview.net/forum?id=iO4LZibEqW
- Why relevant: archolith-audit is not a model-quality benchmark. Its trusted external analogue is HELM's transparent reporting of efficiency metrics, with reproducible inputs and clear caveats.
- Local coverage: `archolith-bench audit` compares before/after MCP audit JSON reports and writes aggregate token and waste deltas. Current bundled fixtures are examples only.
- Launch gate: Use real before/after session logs, not fixtures. Publish server-level deltas and note any new waste type regressions.
- Command: `archolith-bench audit --before <real-before.json> --after <real-after.json> --format markdown`
- Evidence path: `benchmarks/audit-live-before-after-YYYY-MM-DD.md`

### MTEB retrieval/reranking slices (mteb-retrieval)

- Product: `menhir`
- Suite: `memory`
- Authority: Embeddings Benchmark / MTEB
- Type: retrieval and reranking evaluation
- Status: `candidate-before-launch`
- Source: https://github.com/embeddings-benchmark/mteb
- Paper: https://arxiv.org/abs/2210.07316
- Why relevant: Menhir is the durable memory direction. Its closest trusted benchmark family is retrieval evaluation: can stored facts be recalled when queried later?
- Local coverage: archolith-bench does not currently run Menhir retrieval benchmarks. Proxy fact probes are only an indirect signal.
- Launch gate: Do not make durable-memory retrieval claims from archolith-bench until a Menhir-owned MTEB-style or project-memory retrieval evaluation exists.
- Command: `TODO: implement in menhir or a future archolith-bench memory suite`
- Evidence path: `benchmarks/menhir-retrieval-YYYY-MM-DD.md`

### CyberSecEval 4 (cyberseceval-4)

- Product: `archolith-security`
- Suite: `security`
- Authority: Meta / PurpleLlama
- Type: LLM cybersecurity vulnerabilities and defensive capabilities
- Status: `candidate-before-launch`
- Source: https://github.com/meta-llama/PurpleLlama/tree/main/CybersecurityBenchmarks
- Paper: https://arxiv.org/abs/2408.01605
- Why relevant: CyberSecEval is the closest external benchmark family for archolith-security's LLM security posture: prompt injection, insecure code generation, code interpreter risk, vulnerability exploitation, autonomous offensive operations, and defensive SOC/autopatch tasks.
- Local coverage: No archolith-bench CyberSecEval adapter exists. Current coverage is only documentation-level mapping, so no CyberSecEval score can be claimed.
- Launch gate: Before making security benchmark claims, run a scoped CyberSecEval subset relevant to the released products and publish pass/fail, refusal, and false-refusal caveats.
- Command: `TODO: add archolith-bench security-cyberseceval or document an external CyberSecEval run against the launch model/proxy configuration`
- Evidence path: `benchmarks/security-cyberseceval-YYYY-MM-DD.md`

### AgentDojo (agentdojo)

- Product: `archolith-security`
- Suite: `security`
- Authority: ETH Zurich SPY Lab
- Type: prompt injection attacks and defenses for tool-using agents
- Status: `candidate-before-launch`
- Source: https://github.com/ethz-spylab/agentdojo
- Paper: https://arxiv.org/abs/2406.13352
- Why relevant: AgentDojo directly matches Archolith's agent/tool threat model: untrusted tool results, indirect prompt injection, data exfiltration attempts, and over-defense that breaks useful work.
- Local coverage: No local AgentDojo adapter exists. Proxy and filter tests are not a substitute for an adversarial tool-agent security benchmark.
- Launch gate: Run or explicitly defer an AgentDojo-style prompt-injection evaluation for proxy/tool workflows before claiming security hardening against malicious tool output.
- Command: `TODO: add archolith-bench security-agentdojo or document an external AgentDojo run for the launch proxy/tool configuration`
- Evidence path: `benchmarks/security-agentdojo-YYYY-MM-DD.md`

### OWASP LLM Top 10 + ASVS (owasp-llm-asvs)

- Product: `archolith-context`
- Suite: `security`
- Authority: OWASP Foundation
- Type: LLM application and API security control verification
- Status: `candidate-before-launch`
- Source: https://owasp.org/www-project-top-10-for-large-language-model-applications/
- Paper: https://owasp.org/www-project-application-security-verification-standard/
- Why relevant: The proxy exposes API, admin, trace, live-stream, memory, and plugin surfaces. OWASP LLM Top 10 covers LLM-specific risks such as prompt injection, data leakage, and excessive agency; ASVS anchors conventional application controls such as authentication, authorization, input validation, logging, and secure configuration.
- Local coverage: archolith-bench does not run an OWASP security audit. Recent launch audits identified admin/live stream exposure risks, but those are review findings rather than an automated benchmark.
- Launch gate: Complete a scoped OWASP LLM Top 10 + ASVS checklist for public proxy surfaces and track the findings/remediations before presenting the proxy as launch-safe.
- Command: `TODO: add archolith-bench security-checklist or link a tracked OWASP review artifact for archolith-context`
- Evidence path: `benchmarks/security-owasp-context-YYYY-MM-DD.md`

