"""Fixture validator for the oracle bench — the silliness guardrail.

Like the facet validator, this **flags, it does not design** the benchmark. It
catches two classes of problem so a bad fixture can't quietly produce a misleading
result:

- ERRORS — the fixture is self-contradictory or unrunnable (dangling support,
  stale gold under a current-intent query, anachronistic gold, bad buckets, broken
  date order). A result over an erroring fixture cannot be trusted.
- WARNINGS — the fixture is "too clean" / rigged / uninformative: uncontested
  queries (no real distractor), fake paraphrases, scoped queries shallower than k,
  no stale memory to suppress, or a gold answer that dominates so totally nothing
  realistic competes. These are the silliness guards.

Run it on every fixture before trusting a ladder/ablation result.
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import OracleFixture, OracleMemory, OracleQuery

ALLOWED_BUCKETS: frozenset[str] = frozenset({"current", "historical", "anergic", "blocked"})
SCOPE_KEYS: tuple[str, ...] = ("repo", "branch", "project", "namespace")
PARAPHRASE_OVERLAP = 0.85


@dataclass(frozen=True)
class Finding:
    level: str          # "error" | "warn"
    code: str
    where: str          # query id, memory id, or "fixture"
    message: str

    def __str__(self) -> str:
        return f"[{self.level.upper():5s} {self.code}] {self.where}: {self.message}"


def _tokens(text: str) -> set[str]:
    return {t for t in "".join(c.lower() if c.isalnum() else " " for c in text).split() if len(t) > 1}


def _topic(obj: OracleMemory | OracleQuery) -> set[str]:
    """Topic surface for distractor checks: symbols + content tokens."""
    return set(obj.symbols) | _tokens(getattr(obj, "text", ""))


def _scope_keys_set(obj: OracleMemory | OracleQuery) -> dict[str, str]:
    return {k: getattr(obj, k) for k in SCOPE_KEYS if getattr(obj, k)}


def _scope_conflict(q: OracleQuery, m: OracleMemory) -> bool:
    for k in SCOPE_KEYS:
        qv, mv = getattr(q, k), getattr(m, k)
        if qv and mv and qv != mv:
            return True
    return False


def _in_scope(q: OracleQuery, m: OracleMemory) -> bool:
    return bool(_scope_keys_set(q)) and not _scope_conflict(q, m)


def validate_oracle_fixture(fixture: OracleFixture, k: int = 5) -> list[Finding]:
    """Return all findings (errors + warnings) for a fixture."""
    findings: list[Finding] = []
    by_id = fixture.memories_by_id

    # --- structural errors -------------------------------------------------
    if not fixture.memories:
        findings.append(Finding("error", "EMPTY-CORPUS", "fixture", "no memories"))
    if not fixture.queries:
        findings.append(Finding("error", "EMPTY-QUERIES", "fixture", "no queries"))

    seen: set[str] = set()
    for m in fixture.memories:
        if m.id in seen:
            findings.append(Finding("error", "DUP-ID", m.id, "duplicate memory id"))
        seen.add(m.id)
        if m.belief_bucket is not None and m.belief_bucket not in ALLOWED_BUCKETS:
            findings.append(Finding("error", "BAD-BUCKET", m.id, f"belief_bucket={m.belief_bucket!r}"))
        if m.valid_at and m.invalid_at and str(m.valid_at) > str(m.invalid_at):
            findings.append(Finding("error", "DATE-ORDER", m.id, "valid_at is after invalid_at"))

    # --- per-query checks --------------------------------------------------
    has_stale = any(m.is_stale for m in fixture.memories)
    any_query_scoped = any(_scope_keys_set(q) for q in fixture.queries)
    distinct_repos = {m.repo for m in fixture.memories if m.repo}

    for q in fixture.queries:
        if not q.support_ids:
            findings.append(Finding("error", "NO-SUPPORT", q.id, "query has no support_ids"))
        for sid in q.support_ids:
            if sid not in by_id:
                findings.append(Finding("error", "DANGLING-SUPPORT", q.id, f"support {sid!r} not in corpus"))
                continue
            support = by_id[sid]
            # gold answer to a CURRENT query must not itself be stale
            if q.intent == "current" and support.is_stale:
                findings.append(Finding("error", "STALE-GOLD", q.id,
                                        f"current-intent support {sid!r} is stale/superseded"))
            # gold answer must have been knowable at as_of
            if q.as_of_time and support.created_at and str(support.created_at) > str(q.as_of_time):
                findings.append(Finding("error", "ANACHRONISTIC-GOLD", q.id,
                                        f"support {sid!r} created after as_of {q.as_of_time}"))

        valid_support = [by_id[s] for s in q.support_ids if s in by_id]

        # silliness: uncontested query — no non-support memory shares any topic.
        qtopic = _topic(q) | {t for s in valid_support for t in _topic(s)}
        contested = any(
            m.id not in q.support_ids and (_topic(m) & qtopic)
            for m in fixture.memories
        )
        if valid_support and not contested:
            findings.append(Finding("warn", "UNCONTESTED", q.id,
                                    "no distractor shares a topic with the query — too easy to be informative"))

        # silliness: fake paraphrase — query is a near-copy of a support's text.
        for s in valid_support:
            qt, st = _topic(q), _topic(s)
            if qt and st and len(qt & st) / len(qt | st) >= PARAPHRASE_OVERLAP:
                findings.append(Finding("warn", "FAKE-PARAPHRASE", q.id,
                                        f"query is a near-verbatim copy of support {s.id!r}"))
                break

        # silliness: scoped query shallower than k in-scope candidates -> wrong_scope@k
        # is a corpus-depth artifact, not a combiner result.
        if _scope_keys_set(q):
            in_scope = sum(1 for m in fixture.memories if _in_scope(q, m))
            if in_scope < k:
                findings.append(Finding("warn", "THIN-SCOPE", q.id,
                                        f"only {in_scope} in-scope memories (< k={k}); wrong_scope@k uninformative"))

    # --- fixture-level silliness ------------------------------------------
    current_queries = [q for q in fixture.queries if q.intent == "current"]
    if current_queries and not has_stale:
        findings.append(Finding("warn", "NO-STALE", "fixture",
                                "current-intent queries but no stale memory — cannot test stale suppression"))
    if any_query_scoped and len(distinct_repos) < 2:
        findings.append(Finding("warn", "NO-SCOPE-VAR", "fixture",
                                "scoped queries but all memories share one repo — cannot test wrong-scope"))

    return findings


def has_errors(findings: list[Finding]) -> bool:
    return any(f.level == "error" for f in findings)
