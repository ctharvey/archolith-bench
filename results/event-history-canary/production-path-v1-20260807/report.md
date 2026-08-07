# Event History production-path canary

Status: **PASS**
Classification: **noncanonical development canary** (not LongMemEval headline evidence)

## Outcome

- Three namespaces processed with zero event-history failures.
- Seven grounded event assertions created from nine turns.
- Future intent and third-party activity were excluded.
- Latest generic route: advisory winner `brass compass` at world time 2025-03-15.
- Predecessor route: leading winner `red toaster` before `glass blender`.
- Same-time route: ambiguity advisory with no selected object.

## API usage

- Chat calls: 3
- Embedding calls: 3
- Input tokens: 1438
- Output tokens: 516
- Total tokens: 1954
- Missing token rows: 0

## Checks

- [x] `phase3_all_enabled`
- [x] `phase3_no_failures`
- [x] `phase3_three_chat_calls`
- [x] `latest_excludes_intent_and_third_party`
- [x] `latest_selects_world_time_winner_advisory`
- [x] `predecessor_selects_red_toaster`
- [x] `same_time_is_ambiguous`
- [x] `every_assertion_has_turn_foundation`
- [x] `every_assertion_contributes_to_event_view`
- [x] `one_current_view_per_namespace`
- [x] `one_watermark_per_namespace`
- [x] `all_usage_completed`
- [x] `usage_complete`

## Provenance

- Menhir: `370eff1e20f3f4c29d97a5761047ec51a339c7b8` (dirty: false)
- Bench: `0bd3f765141e574d1f77805e326d1414aef3e6d2` (dirty: true)
- Neo4j container: `menhir-event-canary-20260807`, Bolt 7712
- Menhir API: port 8162, PID 9904
- Event history: enabled, perceiver v1, authority enabled
- Scalar state/history: disabled
