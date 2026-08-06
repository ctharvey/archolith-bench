# Compositional scalar generic panel — 2026-08-05

This note records the first offline result from
`fixtures/compositional_scalar_generic_v1.json`. The fixture is non-LME and independently labeled;
it does not reuse LongMemEval task IDs, answer text, or LLM proposals.

## Provenance

- Menhir: `36fddd112bc45c3b8e401829e1bd72cab53dea7b` (clean)
- Bench fixture/analyzer artifact: `b2de4ee32f0b8db95d7861993f6989aee2440413`
- Panel source SHA-256: `e0316bee092e6a84df931853a389a29d88a453bec3668847b366de1f81f1fac3`
- Calls: no LLM, network, Neo4j, Docker, or Menhir service calls

## Result

| Measure | Result |
|---|---:|
| Positive exact join | 12 / 12 |
| Correct semantic identity | 11 / 12 |
| Wrong semantic identity | 0 / 12 |
| Unresolved positive | 1 / 12 |
| Negative system non-admission | 12 / 12 |
| Negative false admission | 0 / 12 |
| Negative false current | 0 / 12 |

The unresolved positive is the generic possessive measurement form `my weight is …`: Menhir's
deterministic extractor produces a grounded measurement proposal, but structural composition
currently returns `struct.relation_unknown`. The fixture intentionally preserves this failure
instead of changing the label or phrase to make the score perfect.

## Interpretation

The result establishes that the new labeled lane is working and that the supported composed cases
have no observed identity mismatch. It does not establish population precision: 11 admitted
positives give a 95% Wilson lower bound of about 74.1%, and each relation group has only two or three
admissions. `promotion_status=not_evaluable` is therefore correct. The next expansion should add
new generic semantic groups and whole-group holdouts without modifying current cases in response to
their scores.
