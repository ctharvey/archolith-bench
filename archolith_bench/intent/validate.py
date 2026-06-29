"""Fixture validator for the intent bench — the silliness guardrail.

Like the oracle/facet validators, this **flags, it does not design** the benchmark. It
catches two classes of problem so a bad intent fixture can't quietly produce a misleading
result:

- ERRORS — self-contradictory or unrunnable: empty corpus/queries, duplicate ids, an
  `expected_top` / no-harm support that points at no memory, broken date order, an unknown
  belief bucket. A result over an erroring fixture cannot be trusted.
- WARNINGS — "too clean" / uninformative, specific to intent-aware retrieval:
  * SINGLE-ROLE-CORPUS — too few distinct content roles, so intent has nothing to
    re-rank between (the whole experiment is "different intent -> different role").
  * NO-PREFERRED-ROLE — a query's classified intent has NO memory carrying a role it
    prefers, so intent-correct@1 can never reward that intent.
  * UNCLASSIFIED-QUERY — a main query matches no intent cue (LOW confidence), so it is
    not exercising a real intent (fine for a no-harm query, flagged for a main one).
  * EXPECTED-TOP-MISMATCH — the hand-authored `expected_top` does not carry a preferred
    role for the query's intent (the author's gold contradicts the matrix).
  * NO-SUPERSEDED — history-wanting intents (AVOID_REPEAT / VERIFY_CURRENTNESS) present
    but no superseded memory, so the temporal-lens behavior can't be exercised.
  * TOPIC-NOT-CONSTANT — the corpus does not share a common topic core, so a ranking
    change could be topic leakage rather than the intent signal.

Run it on every fixture before trusting a ladder result.
"""

from __future__ import annotations

from dataclasses import dataclass

from .classifier import IntentConfidence, TaskIntent, classify_intent, primary_intent
from .matrix import Affinity, affinity
from .models import IntentFixture, IntentMemory
from .roles import ContentRole, derive_content_role

ALLOWED_BUCKETS: frozenset[str] = frozenset({"current", "historical", "anergic", "blocked"})
MIN_DISTINCT_ROLES = 3            # below this, intent has too little to differentiate
HISTORY_INTENTS = frozenset({TaskIntent.AVOID_REPEAT, TaskIntent.VERIFY_CURRENTNESS})


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


def _roles_of(m: IntentMemory) -> set[ContentRole]:
    return derive_content_role(m.to_candidate().metadata)


def _has_preferred(roles: set[ContentRole], intent: TaskIntent) -> bool:
    return any(affinity(intent, r) is Affinity.PREFER for r in roles)


def validate_intent_fixture(fixture: IntentFixture) -> list[Finding]:
    """Return all findings (errors + warnings) for an intent fixture."""
    findings: list[Finding] = []
    by_id = {m.id: m for m in fixture.memories}

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

    q_seen: set[str] = set()
    for q in list(fixture.queries) + list(fixture.no_harm_queries):
        if q.id in q_seen:
            findings.append(Finding("error", "DUP-QUERY-ID", q.id, "duplicate query id"))
        q_seen.add(q.id)
        if q.expected_top and q.expected_top not in by_id:
            findings.append(Finding("error", "DANGLING-EXPECTED", q.id,
                                    f"expected_top {q.expected_top!r} not in corpus"))
        for sid in q.support_ids:
            if sid not in by_id:
                findings.append(Finding("error", "DANGLING-SUPPORT", q.id,
                                        f"support {sid!r} not in corpus"))

    # --- corpus-level silliness -------------------------------------------
    all_roles: set[ContentRole] = set()
    for m in fixture.memories:
        all_roles |= _roles_of(m)
    if fixture.memories and len(all_roles) < MIN_DISTINCT_ROLES:
        findings.append(Finding("warn", "SINGLE-ROLE-CORPUS", "fixture",
                                f"only {len(all_roles)} distinct content role(s) (< {MIN_DISTINCT_ROLES}); "
                                "intent has too little to re-rank between"))

    # topic held constant: some token must appear in a majority of memories.
    if len(fixture.memories) > 1:
        counts: dict[str, int] = {}
        for m in fixture.memories:
            for t in _tokens(m.text):
                counts[t] = counts.get(t, 0) + 1
        half = (len(fixture.memories) + 1) // 2
        if not any(c >= half for c in counts.values()):
            findings.append(Finding("warn", "TOPIC-NOT-CONSTANT", "fixture",
                                    "no token shared by half the corpus; a ranking change may be topic "
                                    "leakage, not the intent signal"))

    has_superseded = any(m.superseded or m.belief_bucket in ("historical", "anergic", "blocked")
                         for m in fixture.memories)

    # --- per (main) query checks ------------------------------------------
    history_intent_present = False
    for q in fixture.queries:
        hits, conf = classify_intent(q.text)
        intent = primary_intent(hits)
        if {h.intent for h in hits} & HISTORY_INTENTS:
            history_intent_present = True

        if conf is IntentConfidence.LOW:
            findings.append(Finding("warn", "UNCLASSIFIED-QUERY", q.id,
                                    "main query matches no intent cue (LOW confidence) — not testing a real intent"))
            continue

        # is there any memory whose role the intent prefers? else unrewardable.
        rewardable = any(_has_preferred(_roles_of(m), intent) for m in fixture.memories)
        if not rewardable:
            findings.append(Finding("warn", "NO-PREFERRED-ROLE", q.id,
                                    f"no memory carries a preferred role for intent {intent.value!r}"))

        # the hand-authored expected_top should itself carry a preferred role.
        if q.expected_top and q.expected_top in by_id:
            if not _has_preferred(_roles_of(by_id[q.expected_top]), intent):
                findings.append(Finding("warn", "EXPECTED-TOP-MISMATCH", q.id,
                                        f"expected_top {q.expected_top!r} carries no preferred role for "
                                        f"intent {intent.value!r} (gold contradicts the matrix)"))

    if history_intent_present and not has_superseded:
        findings.append(Finding("warn", "NO-SUPERSEDED", "fixture",
                                "history-wanting intents (avoid_repeat / verify_currentness) present but no "
                                "superseded memory — temporal-lens behavior cannot be exercised"))

    return findings


def has_errors(findings: list[Finding]) -> bool:
    return any(f.level == "error" for f in findings)
