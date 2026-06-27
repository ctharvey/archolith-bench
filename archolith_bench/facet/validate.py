"""Fixture validator for the facet/retrieval eval ladder.

Authoring a retrieval fixture by hand is the part most likely to go wrong — the
classic failure (R2 Risk #1) is a fixture that *looks* fine but is "too clean":
every gold answer is trivially top-ranked, no stale or wrong-scope distractor
actually competes, no vague query where embedding should win. Scores then look
great and prove nothing.

This validator separates **errors** (the fixture is malformed and can't be run)
from **warnings** (the fixture runs but is probably too clean / under-spec). It is
pure structural analysis — it never runs a retriever, so it stays deterministic
and offline. Run it on every fixture before trusting a ladder result.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .models import STALE_BUCKETS, FacetFixture, Query

_KNOWN_BUCKETS = STALE_BUCKETS | {"current", None}
_KNOWN_INTENTS = {"current", "historical", "any"}
_ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}([T ]\d{2}:\d{2}(:\d{2})?)?$")

# R2 spec target (facet-retrieval.md "First archolith-bench fixture").
SPEC_MIN_MEMORIES = 50
SPEC_MIN_QUERIES = 20


@dataclass
class ValidationReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    stats: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        """True if the fixture is runnable (no errors). Warnings are allowed."""
        return not self.errors

    def render(self) -> str:
        lines = [f"fixture validation: {'OK' if self.ok else 'FAILED'}"]
        for key, value in self.stats.items():
            lines.append(f"  {key}: {value}")
        for err in self.errors:
            lines.append(f"  ERROR   {err}")
        for warn in self.warnings:
            lines.append(f"  WARN    {warn}")
        return "\n".join(lines)


def validate_fixture(fixture: FacetFixture) -> ValidationReport:
    report = ValidationReport()
    by_id = fixture.memories_by_id

    _check_structure(report, fixture, by_id)
    _check_coverage(report, fixture)
    _fill_stats(report, fixture)
    return report


def _check_structure(report: ValidationReport, fixture: FacetFixture, by_id: dict) -> None:
    """Hard errors: malformed records that make a run meaningless."""
    seen: set[str] = set()
    for memory in fixture.memories:
        if memory.id in seen:
            report.errors.append(f"duplicate memory id: {memory.id}")
        seen.add(memory.id)
        if not memory.text.strip():
            report.errors.append(f"memory {memory.id} has empty text")
        bucket = memory.facets.belief_bucket
        if bucket not in _KNOWN_BUCKETS:
            report.errors.append(f"memory {memory.id} has unknown belief_bucket: {bucket!r}")
        for tfacet in ("valid_time", "learned_time"):
            value = getattr(memory.facets, tfacet)
            if value is not None and not _ISO_RE.match(value):
                report.warnings.append(f"memory {memory.id} {tfacet}={value!r} is not ISO-8601 date(time)")

    q_ids: set[str] = set()
    for query in fixture.queries:
        if query.id in q_ids:
            report.errors.append(f"duplicate query id: {query.id}")
        q_ids.add(query.id)
        if query.intent not in _KNOWN_INTENTS:
            report.errors.append(f"query {query.id} has unknown intent: {query.intent!r}")
        for sid in query.support_ids:
            if sid not in by_id:
                report.errors.append(f"query {query.id} references missing support id: {sid}")
        if not query.support_ids and not _is_abstention(query):
            report.warnings.append(
                f"query {query.id} has no support_ids (mark it an abstention case in `note` if intended)"
            )


def _check_coverage(report: ValidationReport, fixture: FacetFixture) -> None:
    """Quality warnings: the distractor families R2 requires, and 'too clean' guards."""
    memories = fixture.memories
    queries = fixture.queries

    if len(memories) < SPEC_MIN_MEMORIES:
        report.warnings.append(f"only {len(memories)} memories (R2 spec target is {SPEC_MIN_MEMORIES})")
    if len(queries) < SPEC_MIN_QUERIES:
        report.warnings.append(f"only {len(queries)} queries (R2 spec target is {SPEC_MIN_QUERIES})")

    # stale / superseded distractor present at all
    if not any(m.is_stale for m in memories):
        report.warnings.append("no stale/superseded memory — stale_hit_rate cannot be exercised")

    # symbol-rename case
    if not any("rename" in m.facets.operation for m in memories):
        report.warnings.append("no memory with operation 'rename' — symbol-rename case missing")

    # wrong-repo distractor potential: same topic facet across different repos
    if not _has_cross_repo_topic_collision(memories):
        report.warnings.append(
            "no cross-repo topic collision — wrong_scope_injection cannot be exercised "
            "(need ≥2 memories sharing object/symbol/operation but in different repos)"
        )

    # at least one vague query where embedding should win (sparse facets)
    if not any(_is_vague(q) for q in queries):
        report.warnings.append(
            "no vague query with sparse facets — the 'embedding should beat facets' case is missing"
        )

    # historical-intent query
    if not any(q.intent == "historical" for q in queries):
        report.warnings.append("no historical-intent query — currentness policy can't be tested both ways")

    # paraphrase group with >=2 members
    groups = _paraphrase_groups(queries)
    if not any(len(ids) >= 2 for ids in groups.values()):
        report.warnings.append("no paraphrase group with ≥2 members — paraphrase_stability is undefined")

    # multi-support query (support_sufficiency needs >1 support somewhere)
    if not any(len(q.support_ids) >= 2 for q in queries):
        report.warnings.append("no query needs ≥2 support memories — support_sufficiency is trivial")

    # 'too clean' heuristic: a current-intent query whose support faces no competing
    # distractor (a non-support memory sharing a topic facet) is uncontested.
    uncontested = [q.id for q in queries if q.intent == "current" and q.support_ids and not _has_distractor(q, fixture)]
    if uncontested:
        report.warnings.append(
            "uncontested current queries (support has no competing same-topic distractor) "
            f"— likely too clean: {uncontested}"
        )


def _fill_stats(report: ValidationReport, fixture: FacetFixture) -> None:
    memories = fixture.memories
    queries = fixture.queries
    report.stats = {
        "memories": len(memories),
        "queries": len(queries),
        "stale_memories": sum(1 for m in memories if m.is_stale),
        "repos": sorted({m.facets.repo for m in memories if m.facets.repo}),
        "belief_buckets": _counts(m.facets.belief_bucket or "none" for m in memories),
        "query_intents": _counts(q.intent for q in queries),
        "paraphrase_groups": {g: len(ids) for g, ids in _paraphrase_groups(queries).items()},
        "vague_queries": [q.id for q in queries if _is_vague(q)],
        "multi_support_queries": [q.id for q in queries if len(q.support_ids) >= 2],
    }


# --- helpers ---------------------------------------------------------------
def _is_abstention(query: Query) -> bool:
    return "abstention" in query.note.lower() or "no answer" in query.note.lower()


def _is_vague(query: Query, max_pairs: int = 1) -> bool:
    """A query is 'vague' if it carries almost no discrete facet constraints."""
    return len(query.facets.discrete_pairs()) <= max_pairs


def _topic_values(facets) -> set[str]:
    return facets.values("object") | facets.values("symbol") | facets.values("operation")


def _has_cross_repo_topic_collision(memories) -> bool:
    by_topic: dict[str, set[str]] = {}
    for m in memories:
        if not m.facets.repo:
            continue
        for topic in _topic_values(m.facets):
            by_topic.setdefault(topic, set()).add(m.facets.repo)
    return any(len(repos) >= 2 for repos in by_topic.values())


def _has_distractor(query: Query, fixture: FacetFixture) -> bool:
    """True if some non-support memory shares a topic facet with the query."""
    support = set(query.support_ids)
    q_topic = _topic_values(query.facets)
    if not q_topic:
        return True  # vague query: can't judge contestation by topic, don't flag
    for m in fixture.memories:
        if m.id in support:
            continue
        if q_topic & _topic_values(m.facets):
            return True
    return False


def _paraphrase_groups(queries) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {}
    for q in queries:
        if q.paraphrase_group:
            groups.setdefault(q.paraphrase_group, []).append(q.id)
    return groups


def _counts(items) -> dict[str, int]:
    out: dict[str, int] = {}
    for item in items:
        out[item] = out.get(item, 0) + 1
    return dict(sorted(out.items()))
