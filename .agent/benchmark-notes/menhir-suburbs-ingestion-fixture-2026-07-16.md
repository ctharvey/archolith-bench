# Menhir suburbs ingestion fixture — first live run

**Date:** 2026-07-16
**Status:** RED — do not start a full fresh LongMemEval rebuild yet
**Menhir anchor:** `c949dfa5e87ba70e1d3a498f81b89b6af77c3980`
**Fixture:** `fixtures/longmemeval/menhir_suburbs_extraction_regression.json`
**Graph:** `menhir-lme-suburbs-fix-20260716-v1` / `menhir-lme-data-suburbs-fix-20260716-v1`
**Result:** `results/lme-fixtures/suburbs-fix-20260716-v1/verification.json`

## Run

```bash
./scripts/longmemeval/run_suburbs_fixture.sh
```

The dedicated graph was fresh, all 14 fixture turns ingested, 14 episodes reached READY, no episode
remained FAILED, persistent promotion completed, and the graph was retained for inspection.

## Verification result

```text
suburb_entities=0
current_suburb_edges=0
expired_stale_edges=1
current_stale_edges=1
target_episodes=1
```

The target episode exists and one prior Chicago relationship was retired, but the required suburb
entity and current Rachel-to-suburb edge do not exist. Direct graph inspection showed the remaining
current edge was:

```text
Rachel --["Rachel moved back to the suburbs."]-- Chicago
```

This means the combined extractor retained the proposition text but still resolved its endpoints to
the wrong nodes for the full LongMemEval utterance. The shorter sentence used by the original Menhir
smoke is not sufficient acceptance coverage for the real item.

## Secondary ingester finding

The ingester passes `source="user"` for user turns and claims this creates an external-testimony
anchor. Current Menhir requires a `turn_evidence_uuid` before accepting that trust level. The live
fixture therefore created an `Admission denied: remote-api claimed user` entity. This is noisy
benchmark data and the source/trust contract must be reconciled before a headline run.

## Gate

Do not spend on a fresh 500-item LongMemEval ingest until this exact fixture passes. The next Menhir
fix must create a suburb entity, bind the current fact to Rachel and that entity, retire every current
Rachel-to-Chicago edge, and remove or correctly ground the admission-denial artifact.
