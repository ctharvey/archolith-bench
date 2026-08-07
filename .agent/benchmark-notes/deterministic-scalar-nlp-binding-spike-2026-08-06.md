# Deterministic scalar NLP binding spike — 2026-08-06

The frozen 78-task research run is recorded at:

- `results/deterministic-scalar-shadow/lme-full-78-nlp-binding-spike-v1-20260806/report.md`

Decision: retain the experiment as evidence for a broader deterministic proposal generator, but do not promote the prototype or add its Python dependencies to the production path yet.

The experiment found a viable layered design:

1. recognize and normalize numeric/time/unit spans;
2. bind spans to a self-related predicate and noun phrase through a pinned dependency parse;
3. emit evidence and abstention receipts;
4. hand only high-confidence candidates to Menhir's existing typed identity gate and composer;
5. keep graph promotion disabled in shadow mode.

The key result is improved proposal coverage, not completed scalar correctness. The next acceptance surface must score identity and event/state role separately from value recognition so a grounded subset such as “my other two bikes” cannot overwrite an authoritative total.
