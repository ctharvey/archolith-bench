# Bench dependency-evidence emitter smoke slice

**Status:** DESIGN/RESEARCH — pinned syntax adapter plus converter; not a Menhir rule

`archolith_bench.dependency_evidence_spacy` is a Bench-only converter over a bounded parsed-
document protocol, plus an optional pinned spaCy syntax adapter. The converter emits the serialized
Menhir transport shape (`scalar-dependency-v1` / `parser-evidence-v1`) with exact Python offsets,
source-slice SHA-256 hashes, parser/model/pipeline fingerprints, deterministic canonical JSON, and
an `evidence_sha256` fingerprint. It never creates a `TypedScalarProposal`, chooses a
relation/target, or composes semantic identity. The serialized evidence retains bounded parser
identifiers and fingerprints as transport metadata, but no raw source, token, or lemma text;
diagnostics are reason codes only. The transient `ParsedDocument` necessarily carries source text
for local offset validation and is never serialized into the evidence payload.

The `parse_with_spacy` entry point requires a caller-supplied `CandidateLocator` and absolute
`numeric_value` span, parses exactly that candidate slice, and translates spaCy token offsets back
to the original source. It accepts only spaCy `3.8.14` with `en_core_web_sm` `3.8.0`, the official
wheel URL, and its SHA-256 provenance; unknown model/config/version or artifact drift fails closed.
Missing spaCy/model or invalid configuration returns a typed unavailable/error result without
fallback, source text, or package installation. Successful output carries syntax cues and bounded
markers only; it does not decide operation, relation, admission, currentness, or semantic identity.

The dedicated `research-parser` extra in `pyproject.toml` is an offline-only research dependency:
it pins `spacy==3.8.14` and the official `en_core_web_sm==3.8.0` wheel by URL and SHA-256. The
official model metadata declares spaCy `>=3.8,<3.9` and a roughly 12 MB model. This extra is
intentionally omitted from the default, `all`, and `dev` dependency sets; the adapter never
installs packages or accesses the network at runtime.

The six-case non-LME smoke labels live in `fixtures/dependency_evidence_smoke_v1.json`: three
canonical-self direct absolute positives mixed across train/holdout and three protected
event/attribution/competing-value negatives. Labels are independent annotations; the emitter does
not infer admission or currentness. Explicit source-authored candidate/numeric spans and expected
syntax cues/marker categories are checked separately through the pinned adapter when its optional
extra is installed. Focused tests cover deterministic payload/hash parity, source-free output,
malformed graph/token/span abstention, parser metadata, candidate hash requirements, provenance and
version fail-closed paths, bounded adapter paths, pinned syntax clauses, exact absolute offsets, and
optional parser outcomes.

This slice is not the 48-case operation-aware panel and does not implement delta/expire or Menhir
dependency rules.
