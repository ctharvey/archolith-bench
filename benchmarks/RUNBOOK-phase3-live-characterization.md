# Runbook: Phase 3 live characterization (throwaway menhir)

How to reproduce the live consumer characterization (fold-SUM commit rate, `count_vs_spend_partial`
receipt, `verify_retries` comparison) against a **throwaway** menhir. All stochastic, so it needs a
real menhir + real LLM — the offline `--offline-fixture stub` suite cannot measure it.

## Safety rules (non-negotiable)

- **Never touch the real menhir on `:8090`** or the real (remote) menhir Neo4j. Use a throwaway only.
- The throwaway Neo4j is `docker-compose.benchmark.yml` in the **menhir** repo (distinct container,
  ports 7475/7688, isolated volume). Bring it up/down explicitly.
- The throwaway env file contains an `OPENAI_API_KEY` — write it under a temp dir and **delete it at
  teardown**. Never commit it.
- All probe writes go to throwaway namespaces (`sumrate-*`, `cvs-*`, `phase3-bench-*`); fresh namespace
  per iteration means no reset is needed.

## 1. Bring up the throwaway Neo4j (menhir repo)

```bash
cd <menhir>
docker compose -f docker-compose.benchmark.yml up -d       # neo4j on bolt 7688, browser 7475
```

## 2. Write a throwaway env file (temp; holds the OpenAI key)

```bash
ENVF="$TEMP/menhir-bench-8099.env"        # a temp path, NOT the repo
cat > "$ENVF" <<EOF
NEO4J_URI=bolt://localhost:7688
NEO4J_USER=neo4j
NEO4J_PASSWORD=benchthrowaway
NEO4J_DATABASE=neo4j
MENHIR_API_HOST=127.0.0.1
MENHIR_API_PORT=8099
MENHIR_PERSONAL_MEMORY_CHAT_MODEL=gpt-4o-mini
MENHIR_PERSONAL_MEMORY_CONSOLIDATION_ENABLED=1
# the retry knob under test — 0 = default/off, 1 to compare
MENHIR_PERSONAL_MEMORY_VERIFY_RETRIES=0
EOF
grep '^OPENAI_API_KEY=' <menhir>/.env >> "$ENVF"    # reuse the dev key
```

Auth: menhir disables bearer auth when no `MENHIR_*_KEY` is set. If your shell already exports
`MENHIR_AGENT_KEY` it leaks into both the server and the client and they match automatically — either
is fine, just be consistent.

## 3. Start the throwaway menhir on :8099 (menhir repo)

```bash
cd <menhir>
ENV_FILE="$ENVF" NEO4J_URI=bolt://localhost:7688 NEO4J_USER=neo4j NEO4J_PASSWORD=benchthrowaway \
  MENHIR_API_PORT=8099 MENHIR_PERSONAL_MEMORY_VERIFY_RETRIES=0 \
  .venv/Scripts/python.exe -m menhir.cli serve --port 8099 --host 127.0.0.1
# wait for GET http://127.0.0.1:8099/api/health -> {"status":"ok", ... "startup_mode":"full"}
```

## 4. Run the characterization (archolith-bench repo)

```bash
cd <archolith-bench>
# a) the full scripted phase3 suite (gates + count-vs-spend characterization)
python -m archolith_bench.cli harness menhir-phase3 --menhir-url http://127.0.0.1:8099 \
    --confirm-menhir-reset --format json --out results/live-cq/suite.json

# b) fold-SUM commit-rate probe (compare verify_retries=0 vs 1 by restarting the server between runs)
python scripts/probe_phase3_sum_rate.py --menhir-url http://127.0.0.1:8099 --n 10 --label r0
#   -> restart the server with MENHIR_PERSONAL_MEMORY_VERIFY_RETRIES=1, then:
python scripts/probe_phase3_sum_rate.py --menhir-url http://127.0.0.1:8099 --n 10 --label r1

# c) count_vs_spend_partial receipt
python scripts/probe_phase3_sum_rate.py --menhir-url http://127.0.0.1:8099 --fixture count-spend --n 5
```

The probe exits non-zero if any iteration produces a WRONG or DUPLICATE current View (the phase3
safety invariants), so it doubles as a guard, not just a report.

## 5. Teardown (always)

```bash
# stop the :8099 server (Ctrl-C, or kill the PID holding the port)
cd <menhir> && docker compose -f docker-compose.benchmark.yml down -v   # removes the throwaway volume
rm -f "$ENVF"                                                            # delete the key-bearing env file
# verify: :8099 down, real :8090 still up and untouched
```

## Recorded results

See `menhir-phase3-view-consolidation-2026-07-07.md` -> "Live characterization (2026-07-08)". Summary:
fold-SUM commits ~5/10 at BOTH `verify_retries` 0 and 1 (abstentions dominated by the `cross_check`
veto, which fires before the verifier — so `verify_retries` can't help this fixture); the
`count_vs_spend_partial` receipt fires as designed; safety invariants clean; real `:8090` untouched.
