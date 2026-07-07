# Benchmark Evidence

This directory contains curated, tracked benchmark evidence for launch-facing
numbers. Raw suite output still lands in `results/`, which is local runtime
scratch space and remains gitignored.

Use this directory for:

- stable summary tables used by `README.md`, `BENCHMARKS.md`, and
  `HEADLINE-NUMBERS.md`
- methodology notes and formulas
- links back to the source result artifact names

Do not use fixture-only or sample-only results as launch headlines. If a result
comes from fixtures, label it as format evidence only.

## Current Evidence

| File | Scope | Launch headline eligible |
|------|-------|--------------------------|
| `proxy-code-review-2026-05-30.md` | Historical proxy code-review run | Partial; actual upstream input deltas only |
| `filter-2026-05-30.md` | Filter compression run over 12 corpus samples | Yes |
| `audit-fixture-2026-06-06.md` | Fixture audit report format evidence | No |
| `industry-trusted-benchmark-coverage.md` | Product-to-industry-benchmark launch coverage matrix | No; coverage/gate artifact only |
| `mteb-embedding-baseline-2026-06-19.md` | Single-arm embedding-model component baseline | No; component diagnostic, not proxy or memory-system A/B |
| `menhir-phase3-view-consolidation-2026-07-07.md` | Menhir Phase 3 consumer-pipeline validation (TurnEvidence -> Views) | No; consumer-correctness validation, not a proxy or model score |

## Refresh TODO

- Re-run proxy benchmarks against the current launch proxy configuration.
- Cover `proxy_only` and `proxy_plus_filter`, 4K and 15K budgets, and the current launch model.
- Record actual upstream input reduction separately from internal context-curation savings.
- Replace or supplement the historical proxy evidence before using broader launch copy.
- Run `archolith-bench industry --launch-only --out benchmarks/industry-trusted-benchmark-coverage.md`
  after changing product scope or benchmark policy.
- Keep MTEB artifacts named as embedding-model baselines unless an embeddings
  proxy/cache layer exists and a true A/B run is added.
- `scripts/run_mteb_local.py` intentionally stays separate from `MtebAdapter`:
  it drives MTEB's in-process encoder API for local embedding-model measurement,
  while `MtebAdapter` is the archolith-bench harness wrapper for evidence parsing.
