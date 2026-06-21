# archolith-bench — Industry Benchmark Rollout Plan

**Created:** 2026-06-21
**Status:** Chartered; not executed
**Governing remediation:** `C:\Users\thron\IdeaProjects\projects\archolith\.agent\plans\archolith-bench-remediation-plan-2026-06-20.md` Session D / P5
**Scope:** Install and run launch-facing external benchmarks only after the remediation sessions that make benchmark evidence trustworthy have landed.

---

## Summary

The existing industry registry identifies candidate benchmark families, but most entries are not completed evidence. This plan turns those candidates into an ordered rollout with explicit tooling, budget, artifacts, and launch-claim rules.

No benchmark result may be used in launch copy unless it has:

- a tracked artifact under `benchmarks/`
- same model, temperature, and max-token settings across compared arms
- direct and proxy-family arm outputs captured in one report
- prompt/input/output token accounting from the remediated metrics path
- a dated run note naming dataset subset, tool version or commit, model, and API provider

---

## Prerequisites

Complete these before spending API budget on new evidence:

1. Session A: phantom token count remediation.
2. Session B: memory A/B chat-client threading and Menhir client lifecycle fix.
3. Session E: upstream-input reduction metric, 1-based trace matching, configurable trace polling.
4. Session F: external harness environment allowlist.
5. Bulk safe fixes required for installability and local reproducibility.
6. `python -m pytest -q -p no:cacheprovider`, `python -m ruff check .`, and `python -m pip install -e . --dry-run --no-deps` must pass.

---

## Run Order

| Order | Benchmark | Product/suite | Gate | Adapter state | Artifact |
|-------|-----------|---------------|------|---------------|----------|
| 1 | LongBench v2 | archolith-context / proxy | Launch gate | In-process adapter implemented | `benchmarks/proxy-longbench-v2-YYYY-MM-DD.md` |
| 2 | BigCodeBench-Hard | archolith-context / proxy | Launch gate if coding claims are used | In-process adapter implemented | `benchmarks/proxy-bigcodebench-hard-YYYY-MM-DD.md` |
| 3 | SWE-bench Lite | archolith-context / proxy | Launch gate for coding-agent claims | External CLI scaffolded | `benchmarks/proxy-swe-bench-lite-YYYY-MM-DD.md` |
| 4 | LongMemEval Mode A | archolith-context / proxy | Launch gate for long-memory prompt curation claims | In-process adapter implemented | `benchmarks/proxy-longmemeval-mode-a-YYYY-MM-DD.md` |
| 5 | LongMemEval Mode B | menhir / memory | Launch gate for persistent-memory claims | Memory adapter implemented; throwaway Menhir required | `benchmarks/menhir-longmemeval-mode-b-YYYY-MM-DD.md` |
| 6 | CyberSecEval 4 | archolith-security / security | Gate for security benchmark claims | External CLI scaffolded | `benchmarks/security-cyberseceval-YYYY-MM-DD.md` |
| 7 | AgentDojo | archolith-security / security | Gate for tool-injection claims | External CLI scaffolded | `benchmarks/security-agentdojo-YYYY-MM-DD.md` |
| 8 | OWASP LLM/application checks | archolith-security / security | Gate for OWASP-aligned claims | Registry entry only | `benchmarks/security-owasp-YYYY-MM-DD.md` |
| 9 | MTEB retrieval/reranking | menhir / embeddings | Component diagnostic only | External CLI scaffolded | `benchmarks/menhir-mteb-retrieval-YYYY-MM-DD.md` |
| 10 | DMR | menhir / memory | Follow-up, not launch blocker unless claimed | No adapter yet | `benchmarks/menhir-dmr-YYYY-MM-DD.md` |

---

## Standard Execution Contract

For each benchmark:

1. Install the official tool in an isolated environment and record the exact version or commit.
2. Run a tiny smoke subset offline or low-budget first, preferably with existing fixtures.
3. Run direct and proxy-family arms with matching model settings.
4. Save raw JSON and a markdown summary under `benchmarks/`.
5. Regenerate the industry coverage matrix:

```powershell
archolith-bench industry --launch-only --out benchmarks/industry-trusted-benchmark-coverage.md
```

6. Update `BENCHMARKS.md` only after a report generation pass includes the new artifact.
7. Update `HEADLINE-NUMBERS.md` before any percentage or token count is used outside the benchmark repo.

---

## Per-Benchmark Notes

### LongBench v2

- Command shape: `archolith-bench harness longbench-v2 --arms direct,proxy_only,proxy_plus_filter --limit <n>`.
- Start with a small subset, then run the selected launch subset.
- Required deps: `datasets`.
- Record accuracy preservation, upstream input reduction, total cost, and latency.

### BigCodeBench-Hard

- Command shape: `archolith-bench harness bigcodebench-hard --arms direct,proxy_only,proxy_plus_filter --limit <n>`.
- Requires sandboxed code execution and a bounded timeout.
- Treat pass@1 preservation as the primary quality gate; token/cost reduction is secondary.

### SWE-bench Lite

- Command shape: `archolith-bench harness swe-bench --subset princeton-nlp/SWE-bench_Lite --arms direct,proxy_only,proxy_plus_filter`.
- Requires official SWE-bench tooling, Docker, and an agent scaffold compatible with OpenAI-style base URLs.
- Do not claim SWE-bench performance until official evaluation output is present.

### LongMemEval Mode A

- Command shape: `archolith-bench harness longmemeval --arms direct,proxy_only,proxy_plus_filter`.
- Tests proxy curation of long memory placed in prompt context.
- Use this for prompt-context memory claims only, not persistent memory claims.

### LongMemEval Mode B

- Command shape: `archolith-bench harness longmemeval-menhir --arms no_memory,menhir_memory --menhir-url <throwaway-url>`.
- Requires throwaway Menhir and Neo4j, never production.
- Primary metric is memory-QA accuracy lift versus `no_memory`.

### CyberSecEval 4

- Command shape depends on the official PurpleLlama runner installed on the benchmark machine.
- Treat pass rate and unsafe completion deltas as security evidence.
- Launch copy must name the subset, not imply full CyberSecEval coverage if only a slice ran.

### AgentDojo

- Requires official AgentDojo tooling and a compatible tool-use agent scaffold.
- Primary metric is utility under attack with injection resistance.
- Use for tool-injection claims only after the artifact is present.

### OWASP LLM/Application Checks

- No adapter is currently implemented.
- First pass is a manual or scripted control checklist mapped to OWASP LLM Top 10 categories.
- Do not present as an industry benchmark score unless an external scoring harness is adopted.

### MTEB Retrieval/Reranking

- Component diagnostic for embeddings only.
- Proxy arm deltas are expected to be zero unless an embeddings proxy layer exists.
- Artifact must state that MTEB is not a Menhir end-to-end memory benchmark.

### DMR

- Follow-up benchmark for memory capability, after LongMemEval Mode B is stable.
- Requires adapter design before execution.

---

## Rollback / Deferral Rules

- If a tool cannot be installed in one working session, keep the registry entry marked `candidate-before-launch` and add an explicit deferral note to the artifact.
- If direct quality regresses materially while token savings improve, do not use the token-savings number as launch evidence.
- If only fixtures or smoke subsets were run, mark the result as non-headline.
- If API budget is exhausted, stop before partial multi-arm comparisons; incomplete comparisons are not evidence.

---

## Verification

Before closing this rollout workstream:

```powershell
python -m pytest -q -p no:cacheprovider
python -m ruff check .
python -m pip install -e . --dry-run --no-deps
archolith-bench industry --launch-only --out benchmarks/industry-trusted-benchmark-coverage.md
```

Then inspect `benchmarks/industry-trusted-benchmark-coverage.md`, `BENCHMARKS.md`, and `HEADLINE-NUMBERS.md` for stale or overbroad claims.
