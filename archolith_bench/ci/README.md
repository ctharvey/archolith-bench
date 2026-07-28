# CI Recall Benchmark for Menhir

Protects API keys from PR code while benchmarking a PR's menhir recall quality
against a pinned baseline.

## Why

A PR author could modify the benchmark script to steal `OPENAI_API_KEY` or burn
the LLM budget. This tool:

1. **Never gives the PR code the real API key.** The PR's menhir subprocess sees
   `OPENAI_BASE_URL=http://127.0.0.1:8765/v1` (a local proxy) and a dummy key.
   The proxy holds the real key and forwards only `/v1/chat/completions` and
   `/v1/embeddings`.
2. **Reserves call budget before forwarding** (200 calls by default) and
   stops the subprocess when the USD or wall-clock guard trips.
3. **Tests a Menhir PR's code, not its tests.** The trusted bench harness stays
   in the `archolith-bench` checkout; the target PR is checked out from the
   sibling Menhir repository.
4. **Compares to a pinned baseline.** The baseline file lives in `main` and is
   hash-pinned. PR edits to it are ignored.

## Usage

```powershell
# First time: start Neo4j and ingest the LongMemEval graph (see scripts/longmemeval/lib/ingest.py)
docker run -d --name neo4j-bench -p 7687:7687 -e NEO4J_AUTH=neo4j/password neo4j:5

# Per-PR: review the diff on github.com first, then:
.\scripts\bench-pr.ps1 -PR 123

# Dry run (no API key, proxy, LLM, or Menhir start):
.\scripts\bench-pr.ps1 -PR 123 -DryRun

# If menhir is already running:
.\scripts\bench-pr.ps1 -PR 123 -SkipMenhirStart

```

The script writes:
- `.bench/runs/<PR>/card.md` — the PR comment card
- `.bench/runs/<PR>/results.json` — per-question scores
- `.bench/runs/<PR>/traces.jsonl` — every LLM call (timestamp, path, status, cost)
- `.bench/runs/<PR>/budget.json` — calls/usd/elapsed/killed
- `.bench/runs/<PR>/menhir-stdout.log`, `menhir-stderr.log`

Post the card to the PR:
```powershell
gh pr comment 123 --body-file .bench/runs/123/card.md
```

## Execution boundary

The runner allowlists the Menhir child environment, replaces `OPENAI_API_KEY`
with a proxy-only dummy value, and gives it a fake home directory. That limits
accidental credential exposure; it is **not** an operating-system sandbox for
arbitrary hostile code. Run unfamiliar or adversarial PRs in a disposable
VM/container rather than relying on this local helper as a security boundary.

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│ GITHUB (PR author can touch this)                            │
│  PR opened → maintainer reviews → runs bench-pr.ps1 -PR N    │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────┐
│ LOCAL DEV MACHINE                                           │
│                                                             │
│  bench-pr.ps1                                               │
│    1. git -C ../menhir fetch origin pull/N/head             │
│    2. git -C ../menhir worktree add menhir-pr-N <sha>        │
│    3. python -m archolith_bench.ci --menhir-dir <worktree>  │
│       │                                                     │
│       ├─ BudgetProxy (port 8765)                           │
│       │   holds real OPENAI_API_KEY                         │
│       │   forwards only /v1/chat/completions, /v1/embeddings│
│       │   caps: 200 calls / $5 / 15min                     │
│       │                                                     │
│       ├─ menhir subprocess (port 8090, from PR worktree)   │
│       │   env: OPENAI_BASE_URL=http://127.0.0.1:8765/v1    │
│       │   env: OPENAI_API_KEY=dummy                         │
│       │   env: HOME=.bench/runs/N/fake-home (sandbox)       │
│       │                                                     │
│       ├─ run_stratified_slice (6× harness calls)            │
│       ├─ compare_results vs baseline from main              │
│       └─ render_pr_card → .bench/runs/N/card.md             │
└──────────────────────────────────────────────────────────────┘
```

## Safety properties

| Threat | Mitigation |
|--------|-----------|
| PR author steals API key | Key never leaves proxy process. PR code talks to `127.0.0.1:8765` with a dummy key. |
| PR author burns budget | Call slots are atomically reserved; the proxy stops the child immediately when USD/time guards trip. |
| PR author changes bench script | The harness runs from the trusted `archolith-bench` checkout, outside the Menhir PR worktree. |
| PR author changes baseline | Baseline loaded from `main`. PR edits ignored. |
| PR author triggers repeatedly | Cooldown 10min + max 3 runs per PR. |
| PR code inherits shell credentials | Child environment is allowlisted; `HOME` is fake and GitHub/OpenAI credentials are excluded. |
| Maintainer forgets to review | The script is for Menhir PRs; review the PR diff before granting it local execution. |

## Gate rules

| Result | Condition |
|--------|-----------|
| ✅ PASS | overall Δ ≥ -2% AND no single type Δ < -10% |
| ⚠️ WARN | overall PASS but any single type Δ < -10% |
| ❌ FAIL | overall Δ < -2% |

## Baseline promotion

After a deliberate recall improvement lands on `main`, promote a new baseline:

1. Run the full benchmark against `main`:
   ```powershell
   .\scripts\bench-pr.ps1 -PR 0 -SkipMenhirStart  # 0 = local main, no PR
   ```
   (or run the orchestrator directly with menhir already on `main`)
2. Copy `.bench/runs/0/results.json` to `benchmarks/longmemeval-baseline.json`
   with the schema below.
3. Compute the SHA-256 of the graph snapshot and pin it in `snapshot_hash`.
4. Commit + push. Future PRs will compare against this new baseline.

## Baseline file schema

`benchmarks/longmemeval-baseline.json`:
```json
{
  "baseline_version": "2026-07-19-v1",
  "baseline_commit": "abc1234",
  "stratified_slice_hash": "sha256:...",
  "graph_snapshot": "longmemeval-2026-07-19.dump",
  "snapshot_hash": "sha256:...",
  "questions_per_type": 20,
  "total_questions": 120,
  "scoring_method": "llm_judge_gpt-4o-mini",
  "results": {
    "overall": 0.230,
    "by_type": {
      "single-session": 0.350,
      "multi-session": 0.180,
      "long-preference": 0.220,
      "long-entity": 0.300,
      "long-deduction": 0.150,
      "long-counting": 0.180
    },
    "per_question": [
      {"id": "Q-001", "type": "single-session", "score": 1.0}
    ]
  },
  "promoted_at": "2026-07-19T14:32:00Z",
  "promoted_by": "cth@archolith.dev",
  "notes": "First stratified baseline after frontier-gate refactor"
}
```

The current baseline file is a **STUB** — replace with real numbers from a
verified run before relying on the gate.

## Module layout

- `archolith_bench/ci/budget_proxy.py` — reverse proxy with caps
- `archolith_bench/ci/stratified.py` — runs the harness 6× (one per type)
- `archolith_bench/ci/compare.py` — gate logic (PASS/WARN/FAIL)
- `archolith_bench/ci/card.py` — PR comment markdown renderer
- `archolith_bench/ci/orchestrator.py` — end-to-end
- `archolith_bench/ci/__main__.py` — CLI entry (`python -m archolith_bench.ci`)
- `scripts/bench-pr.ps1` — PowerShell wrapper
- `benchmarks/longmemeval-baseline.json` — pinned baseline (STUB)
- `tests/test_ci_compare.py` — gate logic tests
- `tests/test_ci_card.py` — card rendering tests
