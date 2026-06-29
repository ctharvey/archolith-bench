"""R1 retrieval metrics, computed from a ranked id list + the gold corpus.

The R1 win condition (deferred-verification.md) requires reporting these
together: a condition that lifts exact-string / symbol recall while inflating
stale-hit or wrong-scope injection has NOT won. ``exact_string_recall`` and
``symbol_recall`` are averaged only over the queries that actually target an
exact string / symbol (their family denominator), so an all-families run still
reports each family-specific metric honestly.
"""

from __future__ import annotations

from collections.abc import Sequence

from .models import R1Memory, R1Query


def recall_at_k(ranked: Sequence[str], support_ids: Sequence[str], k: int) -> float:
    """Fraction of gold support ids present in the top-k."""
    if not support_ids:
        return 0.0
    top = set(ranked[:k])
    return sum(1 for sid in support_ids if sid in top) / len(support_ids)


def exact_string_hit(
    ranked: Sequence[str], memories_by_id: dict[str, R1Memory], query: R1Query, k: int
) -> float | None:
    """1.0 if a top-k memory contains the query's target exact string, else 0.0.

    Returns None when the query has no exact-string target (excluded from the
    average). A memory "contains" the string if it is in its gold exact_strings
    set or appears verbatim in its text.
    """
    target = query.target_exact_string
    if not target:
        return None
    for mid in ranked[:k]:
        mem = memories_by_id.get(mid)
        if mem and (target in mem.exact_strings or target in mem.text):
            return 1.0
    return 0.0


def symbol_hit(
    ranked: Sequence[str], memories_by_id: dict[str, R1Memory], query: R1Query, k: int
) -> float | None:
    """1.0 if a top-k memory carries the query's target symbol, else 0.0.

    Returns None when the query has no symbol target (excluded from the average).
    """
    target = query.target_symbol
    if not target:
        return None
    for mid in ranked[:k]:
        mem = memories_by_id.get(mid)
        if mem and target in mem.symbols:
            return 1.0
    return 0.0


def stale_hit_rate(
    ranked: Sequence[str], memories_by_id: dict[str, R1Memory], query: R1Query, k: int
) -> float:
    """Fraction of top-k that are stale under a current-intent query.

    Always 0.0 for historical-intent queries: returning historical memories is
    correct when the query asks about history.
    """
    if query.intent != "current":
        return 0.0
    top = ranked[:k]
    if not top:
        return 0.0
    stale = sum(1 for mid in top if mid in memories_by_id and memories_by_id[mid].stale)
    return stale / len(top)


def wrong_scope_injection_rate(
    ranked: Sequence[str], memories_by_id: dict[str, R1Memory], query: R1Query, k: int
) -> float:
    """Fraction of top-k whose repo/project conflicts with the query's scope."""
    top = ranked[:k]
    if not top:
        return 0.0
    wrong = sum(
        1 for mid in top if mid in memories_by_id and _scope_conflict(query, memories_by_id[mid])
    )
    return wrong / len(top)


def _scope_conflict(query: R1Query, memory: R1Memory) -> bool:
    """True if repo or project is set on both sides and disagrees."""
    for attr in ("repo", "project"):
        q_val = getattr(query, attr)
        m_val = getattr(memory, attr)
        if q_val and m_val and q_val != m_val:
            return True
    return False
