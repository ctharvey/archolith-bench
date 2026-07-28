# archolith-bench Launch Readiness Tracker

Date: 2026-06-19
Status: Imminent pre-launch, not launched
Release posture: fix only Critical and High issues before public release; defer polish unless it blocks trust or installability.

## Launch Sequencing (decided 2026-06-19)

Run pre-launch work in this order so any future headline numbers reflect the final, post-remediation system:

1. **Audits** — run code/security audits and remediate findings first.
2. **Industry benchmarks** — square away the `archolith-bench industry` registry: complete or explicitly defer each candidate and security (CyberSecEval/AgentDojo/OWASP) gate.
3. **Actual benchmark runs** — refresh proxy, audit before/after, and stack runs LAST, immediately before launch, against the final system. Do not spend a live proxy/API run before the system is frozen.

## Current Decision Log

- Public benchmark copy must not use numeric claims until refreshed evidence is recorded in `HEADLINE-NUMBERS.md`.
- Historical proxy evidence is retained for methodology review only; no historical proxy value is currently an active headline.
- `benchmarks/` is the tracked evidence folder for launch-facing benchmark summaries.
- Raw `results/` and `logs/` remain local runtime output and stay gitignored.
- `stack` remains visible as an experimental/pending suite, not a launch headline.
- `archolith-filter` and the `archolith-audit` distribution are optional extras so the base package can install before sibling packages are published.
- Optional sibling package path is source-first for launch: install `../archolith-filter` and `../archolith-mcp-audit` editable before `pip install -e ".[all]"`. Standalone `.[all]` remains unavailable to public users until both sibling packages are published to the configured package index.
- Default upstream is OpenAI-compatible: `https://api.openai.com/v1`, model `gpt-4o-mini`, proxy `http://localhost:9800/v1`.
- Industry and security benchmark coverage is now tracked through `archolith-bench industry`; candidate entries are launch gates, not completed evidence.

## Resolved For Launch

| Area | Resolution | Evidence |
|------|------------|----------|
| Headline number posture | README and `HEADLINE-NUMBERS.md` no longer expose active numeric claims until refreshed launch evidence exists | `README.md`, `HEADLINE-NUMBERS.md` |
| Public benchmark evidence | Added tracked evidence summaries under `benchmarks/` | `benchmarks/README.md` |
| Pytest collection | Default pytest collection limited to `tests/`; archival `experiments/` excluded | `pyproject.toml` |
| Base installability | Kept `archolith-filter` and `archolith-audit` as optional distribution extras | `pyproject.toml`, `README.md` |
| Optional sibling install path | Source-first workflow documented for full-suite installs; standalone `.[all]` is explicitly not public until sibling packages are published | `README.md`, `AGENTS.md`, `.agent/README.md` |
| Config defaults | Runtime, README, `.env.example`, and agent docs use OpenAI endpoint defaults | `.env.example`, `archolith_bench/core/api.py`, `README.md`, `.agent/architecture.md` |
| Repository URL | README matches `pyproject.toml` canonical URL | `README.md`, `pyproject.toml` |
| Stack suite wording | Stack labeled experimental/pending in docs and generated report output | `README.md`, `BENCHMARKS.md`, `archolith_bench/core/report.py` |
| Industry benchmark registry | Added executable product-to-benchmark coverage matrix for RULER, LongBench v2, SWE-bench, BigCodeBench, HELM, MTEB, CyberSecEval, AgentDojo, and OWASP security checks | `archolith_bench/core/industry.py`, `benchmarks/industry-trusted-benchmark-coverage.md` |

## Remaining Critical / High Work

| Priority | Item | Why It Matters | Exit Criteria |
|----------|------|----------------|---------------|
| Critical | Refresh proxy benchmarks against current launch setup | Current proxy evidence is historical and single-scenario | New tracked evidence under `benchmarks/` covering current proxy config, `proxy_only`, `proxy_plus_filter`, 4K and 15K budgets, and launch model |
| High | Run one real before/after audit or keep audit out of launch copy | Current audit number is fixture/projection evidence only | Either tracked live audit evidence exists, or README/launch copy continues to show audit as pending |
| High | Generate real stack evidence or keep stack experimental | Stack suite is advertised but not headline-ready | Tracked stack evidence exists, or all stack mentions remain clearly experimental/pending |
| High | Run or explicitly defer candidate industry benchmarks | The registry identifies SWE-bench/LongBench/trace-derived filter and audit gates that are not completed evidence | Candidate entries either have tracked evidence under `benchmarks/` or remain clearly labeled as pre-launch TODOs |
| High | `menhir` / LongMemEval IR gate (persistent memory, retrieval-only) — 2026-07-15 update | First full n=500 corpus run is now tracked evidence (`benchmarks/longmemeval-menhir-2026-07-15.md`, `results/lme-gate/longmemeval-menhir-2026-07-15.{json,md}`). Result: **overall PASS** on the recalibrated gate — menhir Hit@3(support)=4.60% vs graphiti(vector-only)=0.40% (~11.5x), MRR@10 0.0466 vs 0.0033 (~14x), explainability 100%. The roadmap's original absolute 0.80 threshold was found unvalidated for this corpus and recalibrated to a relative "beats vector-only baseline" bar — see `menhir-mvp-roadmap.md` M1. **This PASS is a comparative retrieval-quality claim, NOT the Mode-B answer-accuracy lift** the `industry-trusted-benchmark-coverage.md` launch gate for this product actually asks for — that run is still not tracked. | Do not cite this PASS as a memory-QA accuracy number. It licenses "menhir's graph retrieval beats vector-only search on this corpus" (in absolute terms menhir found supporting evidence for only 81/500 questions, 16.2%). The Mode-B accuracy-lift run remains the open item for a launch-facing accuracy claim. |
| High | Run or explicitly defer security benchmark gates | CyberSecEval, AgentDojo, and OWASP entries are candidate mappings only; they are not completed security evidence | Security claims either have tracked evidence under `benchmarks/` or launch copy avoids benchmark-backed security claims |

## Launch TODO Checklist

- [ ] Re-run proxy benchmarks against the current launch setup: OpenAI endpoint, `gpt-4o-mini`, current proxy config, `proxy_only` and `proxy_plus_filter`, 4K and 15K budgets.
- [ ] Add refreshed proxy evidence under `benchmarks/` and update `README.md`, `BENCHMARKS.md`, and `HEADLINE-NUMBERS.md` from that evidence.
- [x] Decide and document the supported install path for `archolith-filter` and the `archolith-audit` distribution: source checkout editable installs before `pip install -e ".[all]"`.
- [ ] Either run and track one real before/after audit or keep audit waste reduction marked pending everywhere launch-facing.
- [ ] Either generate and track real stack-suite evidence or keep `stack` marked experimental/pending everywhere launch-facing.
- [ ] Generate `benchmarks/industry-trusted-benchmark-coverage.md` after every benchmark-policy change and complete/defer each candidate-before-launch gate.
- [ ] Complete or explicitly defer the CyberSecEval, AgentDojo, and OWASP security gates before making security launch claims.
- [ ] Add a Windows test note or CI config that sets `TMP`/`TEMP` to a writable project-local or `C:\tmp` path before running pytest.

## Deferred Polish

- Publish a fuller benchmark methodology page after the refreshed proxy run.
- Add a generated report mode that writes directly into `benchmarks/` with metadata.
- Add CI that runs `python -m pytest -q` with a project-local temp directory on Windows.
- Revisit whether optional extras should include direct Git URLs after sibling repos and release policy are public.

## Verification Snapshot

Run on 2026-06-19:

```powershell
rg -n "58\.6%\*\* \| 10-turn|Proxy token savings|50\.0|71\.5%\*\* \| Live|Best single-turn|116,900|integrate\.api\.nvidia|localhost:9801|UPSTREAM_BASE_URL=https://api\.deepseek\.com/v1|BENCHMARK_MODEL=deepseek-chat|Full-stack headline|github\.com/ctharvey/archolith" projects/archolith/archolith-bench -g "!experiments/**" -g "!results/**" -g "!logs/**" -g "!.pytest_cache/**"
# No matches

git -c safe.directory=C:/Users/thron/IdeaProjects/projects/archolith/archolith-bench -C projects/archolith/archolith-bench diff --check
# Pass; only CRLF normalization warnings

$env:TMP='C:\tmp'; $env:TEMP='C:\tmp'; python -m pytest -q
# 35 passed in 0.96s
```

Note: default `pytest` without temp override can hit a local Windows permission issue at
`C:\Users\thron\AppData\Local\Temp\pytest-of-thron`; this is environment-specific and not a repo collection failure.
