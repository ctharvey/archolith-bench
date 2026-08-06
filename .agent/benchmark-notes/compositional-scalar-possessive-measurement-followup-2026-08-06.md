# Compositional scalar possessive-measurement follow-up — 2026-08-06

This note records a replay of the unchanged independent non-LME panel after a narrow, generic
Menhir grammar repair. It supplements rather than replaces
`compositional-scalar-generic-panel-2026-08-05.md`; that first 11/12 result remains the historical
pre-change baseline.

## Why the grammar changed

The frozen v1 panel independently labeled `My weight is 68 kilograms.` as the same self-measurement
identity as the already supported verb form. Menhir's extractor produced a grounded typed proposal,
but the structural composer returned `struct.relation_unknown`. The repair adds literal self
possessive weight/kg and height/cm pairs only. It does not add an open `my <noun> is <number>` rule,
model-label aliases, benchmark identifiers, or new routing authority.

## Provenance

- Menhir: `dd60bdda61e221d501e5791a7caba2cba3a176df` (clean, pushed)
- Structural composer: `structural-v2`
- Bench panel analyzer/fixture: `b2de4ee32f0b8db95d7861993f6989aee2440413`
- Bench v2 integration test: `54991b7`
- Panel SHA-256: `1ab364aa95c422963ad0b6b4d231b89a06a827c917008673442130db9c8d8a75`
- Panel source SHA-256: `e0316bee092e6a84df931853a389a29d88a453bec3668847b366de1f81f1fac3`
- Calls: no LLM, network, Neo4j, Docker, Menhir service, or LongMemEval calls

## Result

| Measure | Pre-change `structural-v1` | Follow-up `structural-v2` |
|---|---:|---:|
| Positive exact join | 12 / 12 | 12 / 12 |
| Correct semantic identity | 11 / 12 | 12 / 12 |
| Wrong semantic identity | 0 / 12 | 0 / 12 |
| Unresolved positive | 1 / 12 | 0 / 12 |
| Negative system non-admission | 12 / 12 | 12 / 12 |
| Negative false admission | 0 / 12 | 0 / 12 |
| Negative false current | 0 / 12 | 0 / 12 |

Strict composer abstention remains 6/12 because several negative cases are intentionally rejected
earlier by the deterministic extractor. System non-admission is the relevant end-to-end negative
measure.

## Validation and interpretation

- Menhir focused extractor/composer boundary: 193 passed.
- Bench panel plus shadow integration: 44 passed.
- Bench full suite with a writable explicit temp root: 835 passed, 1 skipped.
- Two independent Luna reviews found no semantic, anti-tuning, safety, or provenance blocker.

This closes the one known generic panel gap without changing the panel after observing its score.
It does not establish population precision: each relation group still has only three positive
cases, with a 95% Wilson lower bound of 43.8%. `promotion_status=not_evaluable` remains mandatory.
