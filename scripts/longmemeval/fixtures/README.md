# LongMemEval ingestion regression fixtures

These fixtures exercise the persistent graph ingester in `scripts/longmemeval/lib/ingest.py`.
They are regression tests, not benchmark samples and not sources for headline accuracy numbers.

## Rachel suburbs extraction fixture

`fixtures/longmemeval/menhir_suburbs_extraction_regression.json` reproduces the
`830ce83f` knowledge-update failure in a compact form:

1. establish that Rachel lives in Chicago;
2. ingest twelve filler turns so Chicago is outside Graphiti's ten-episode extraction window;
3. ingest the original message saying Rachel moved back to the suburbs;
4. require a current Rachel-to-suburb fact and a retired Rachel-to-Chicago fact.

Run it from Git Bash:

```bash
./scripts/longmemeval/run_suburbs_fixture.sh
```

The runner refuses an existing container, volume, or manifest by default. It creates a dedicated
Neo4j container, volume, ports, manifest, log directory, and verification artifact under
`results/lme-fixtures/suburbs-fix-20260716-v1/`. Set a different
`LME_FIXTURE_RUN_ID` for another fresh run. Set `LME_FIXTURE_ALLOW_RESUME=1` only to resume an
interrupted run with the same graph.

Before spending extraction tokens, the runner verifies that the configured Menhir checkout
contains commit `c949dfa5e87ba70e1d3a498f81b89b6af77c3980`, the combined-extraction fix.

**Current status (2026-07-16): RED.** The first live run retained the suburb proposition text but
bound it to the Rachel–Chicago edge, created no suburb entity, and left one Chicago edge current.
See `.agent/benchmark-notes/menhir-suburbs-ingestion-fixture-2026-07-16.md`. Do not start a fresh
full-corpus ingest until this fixture passes.


A passing `verification.json` proves:

- the suburb entity exists;
- a current Rachel-to-suburb edge exists;
- the prior Chicago edge is invalidated or expired;
- no current Rachel-to-Chicago edge remains;
- the target suburb episode exists in the isolated namespace.

The graph remains running for inspection. Remove it manually when finished:

```bash
docker rm -f menhir-lme-suburbs-fix-20260716-v1
docker volume rm menhir-lme-data-suburbs-fix-20260716-v1
```

This fixture validates ingestion and graph mutation only. Run a separately isolated full
LongMemEval build and answer-scoring pass for benchmark-level accuracy evidence.
