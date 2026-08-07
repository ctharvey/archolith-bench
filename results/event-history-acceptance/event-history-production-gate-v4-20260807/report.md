# Event History LongMemEval production gate

Status: **PASS (5/5)**
Classification: **NONCANONICAL focused acceptance** — not a canonical KU78 headline run

## Outcomes

- LongMemEval latest-event case: 3/3 correct votes.
- LongMemEval predecessor case: 2/3 correct votes, with 1 fail-closed abstention.
- Intent-only control: 3/3 abstentions.
- Negated-acquisition control: 3/3 abstentions.
- Possession-only control: 3/3 abstentions.
- Wrong unique selections: 0.
- Safety violations: 0.

## API usage

- Model: gpt-4o-mini
- Calls: 15
- Input tokens: 10539
- Output tokens: 1897
- Total tokens: 12436
- Cached input tokens: 2048
- Missing usage calls: 0

## Provenance

- Menhir: `370eff1e20f3f4c29d97a5761047ec51a339c7b8` (dirty: False)
- Bench: `0bd3f765141e574d1f77805e326d1414aef3e6d2` (dirty: True)
- Source fixture SHA-256: `bba252a302e7b257a0f7457fe97411f7de144aafd1c6b44c98a0e88ee8570907`
- Acceptance fixture: `C:\Users\thron\IdeaProjects\projects\archolith\archolith-bench\fixtures\event_history_acceptance_v1.json`

This focused panel validates perception, projection, deterministic selection, routing metadata, and safety controls. It does not replace the separate Neo4j-backed production-path canary or the canonical scalar KU78 benchmark.
