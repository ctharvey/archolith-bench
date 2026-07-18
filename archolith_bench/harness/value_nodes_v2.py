"""Bench-only v2 typed-value graph with supersession-aware CURRENT selection.

STATUS: EXPERIMENTAL - REJECTED (2026-07-18). This arm did NOT improve answer accuracy
over v1 (0/5 targeted supersession misses recovered; overall 0.667/0.679 vs v1 0.679) and
is excluded from every default harness configuration. Kept as documented negative evidence:
lexical full-sentence clustering fragments on real multi-clause turns, and a typed sidecar
cannot override stale untyped recall. See scripts/longmemeval/analysis/TYPED-VALUE-ARM.md
(v2 section) and results/lme-ku-buildout/value-arm-v2-verify-20260718/. Do not wire the v2
arms into default configs or product code.

Extends the frozen v1 ``ValueGraph`` (``value_nodes.py``) WITHOUT modifying it.
Extraction is byte-for-byte identical (same regexes, same subjects/values/edges);
the only differences are:

* Clustering by ``(canonical_entity, canonical_attribute, scope, kind, unit)``
  instead of exact subject text, so the same attribute series is recognized across
  wording differences while distinct attributes/scopes stay separate
  (``coins owned`` vs ``coins sold``; ``MCU films watched`` vs ``on the watch list``;
  ``Korean`` vs ``Italian`` restaurants).
* A single CURRENT value per cluster, chosen by **per-assertion** correction markers
  first (``now`` / ``used to`` / ``X not Y`` scoped to each value span, never the whole
  episode), then the latest-learned assertion using a global session/turn sequence.
  This is *latest-learned*, NOT world-valid ``valid_at``.
* Two emission modes: current-only, and current-plus-one-historical.

Normalization is oracle-assisted (a small fixture-derived alias table); see the plan
for the held-out-validation caveat before any production claim.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .value_nodes import (
    _ONES,
    _STOP_WORDS,
    _TENS,
    ValueGraph,
    ValueKind,
    _query_kind_boosts,
    _tokens,
)

# --- per-assertion correction markers (matched in a window around each value span) ---
_PRESENT_MARKERS = re.compile(
    r"\b(now|currently|nowadays|these days|so far|to date|as of now|at this point|"
    r"anymore|updated to|changed to|up to)\b",
    re.IGNORECASE,
)
_PAST_MARKERS = re.compile(
    r"\b(used to|previously|originally|back then|at first|earlier|formerly|"
    r"no longer|last year|last month|to begin with)\b",
    re.IGNORECASE,
)
_NOT_BEFORE = re.compile(r"\bnot\b[\s\w]{0,12}$", re.IGNORECASE)  # "..., not <value>"

# --- attribute (state-family) derivation from governing verbs ---
_ATTR_VERBS: dict[str, str] = {
    "watched": "watched", "watch": "watched", "watching": "watched",
    "read": "read", "reading": "read",
    "completed": "completed", "complete": "completed", "finished": "completed",
    "own": "owned", "owned": "owned", "have": "owned", "has": "owned", "had": "owned",
    "got": "owned", "added": "owned", "collect": "owned", "collecting": "owned",
    "sold": "sold", "sell": "sold", "selling": "sold",
    "lost": "lost", "lose": "lost", "losing": "lost",
    "spent": "spent", "spend": "spent", "spending": "spent",
    "tried": "tried", "try": "tried", "trying": "tried", "making": "tried", "made": "tried",
    "worn": "worn", "wore": "worn", "wear": "worn", "wearing": "worn",
    "attended": "attended", "attend": "attended", "attending": "attended",
    "played": "played", "play": "played", "playing": "played",
    "earned": "earned", "earn": "earned", "earning": "earned",
    "woke": "wake", "wake": "wake", "waking": "wake",
    "dedicate": "dedicated", "dedicated": "dedicated", "dedicating": "dedicated",
    "sticking": "sticking", "stick": "sticking",
    # NB: no "used/use/using" family - "used" collides with the "used to" past marker.
}
# Temporal/discourse/aux/filler + number words + correction-marker words that must not
# leak into the cluster signature (they are not identity or scope). Correction markers
# are still detected separately on the raw sentence in _correction_signal.
_NOISE: frozenset[str] = frozenset(_ONES) | frozenset(_TENS) | {
    "hundred", "thousand", "million", "dozen", "couple",
    "am", "pm", "at", "now", "currently", "current", "recently", "already", "just",
    "still", "again", "actually", "really", "pretty", "lately", "nowadays", "today",
    "yesterday", "tomorrow", "far", "new", "also", "these", "those", "this", "ever",
    "since", "ago", "around", "about", "roughly", "approximately", "only", "even",
    "quite", "very", "much", "many", "some", "few", "more", "less", "most", "least",
    "then", "here", "while", "per", "each", "every", "average", "usually", "often",
    "sometimes", "always", "local", "been", "being", "up", "out", "down", "over",
    "back", "get", "go", "going", "gone", "day", "week", "month", "year", "used",
    "previously", "originally", "formerly", "longer", "once", "first", "last", "next",
    "recent", "anymore", "updated", "changed", "so", "by", "way",
}
# structural container nouns that describe the holder, not the identity of the series
_DROP_STRUCTURAL = {
    "collection", "list", "game", "routine", "series", "app", "tracker", "total",
    "one", "ones", "thing", "things", "time", "times", "piece", "pieces",
}
# fixture-derived alias table (oracle-assisted): collapse synonymous identity tokens
_ALIAS: dict[str, str] = {
    "coin": "coin",
    "film": "film", "movie": "film",
    "title": "title",
    "video": "video",
    "episode": "episode",
    "session": "session",
    "restaurant": "restaurant",
    "sculpture": "sculpture",
    "page": "page",
    "night": "night",
    "screwdriver": "screwdriver",
}


@dataclass(frozen=True)
class _V2Meta:
    cluster_key: tuple
    present: bool  # authoritative-current marker on this assertion
    past: bool     # explicit-past / rejected-value marker on this assertion
    ordinal: int


def _words(text: str) -> list[str]:
    """Lowercased alphabetic word list (keeps stopwords, for verb detection)."""
    return re.findall(r"[a-z][a-z'-]*", text.lower())


def _singular(token: str) -> str:
    if len(token) > 4 and token.endswith("ies"):
        return f"{token[:-3]}y"
    if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


def _content_tokens(text: str) -> list[str]:
    out: list[str] = []
    for w in _words(text):
        if w in _STOP_WORDS:
            continue
        out.append(_singular(w))
    return out


class SupersededValueGraph(ValueGraph):
    """v1 extraction + supersession-aware CURRENT selection (bench-only, frozen arm)."""

    def __init__(self, namespace: str, *, grouping: str = "lexical") -> None:
        super().__init__(namespace)
        self._meta: dict[str, _V2Meta] = {}
        # "lexical": entity/attribute/scope/kind key (v2).
        # "coarse": drop the fragmenting context tokens, cluster by
        # (attribute, kind, unit, entity-noun) only. Near-oracle for single-attribute
        # knowledge-update items; used by the v3 authoritative-composition experiment
        # to isolate the ceiling from lexical clustering quality.
        self.grouping = grouping

    @classmethod
    def from_sessions(cls, namespace, sessions, *, grouping: str = "lexical"):  # type: ignore[override]
        graph = cls(namespace, grouping=grouping)
        for session_index, session in enumerate(sessions):
            graph._add_session(session, session_index=session_index)
        return graph

    @classmethod
    def from_item(cls, namespace, item, sessions, *, grouping: str = "lexical"):  # type: ignore[override]
        graph = cls(namespace, grouping=grouping)
        session_list = list(sessions)
        dates = list(item.get("haystack_dates") or [])
        order = sorted(
            range(len(session_list)),
            key=lambda index: (dates[index] if index < len(dates) else "", index),
        )
        for session_index in order:
            graph._add_session(session_list[session_index], session_index=session_index)
        return graph

    def _add_assertion(  # type: ignore[override]
        self,
        sentence: str,
        span: tuple[int, int],
        display: str,
        normalized,  # noqa: ANN001
        unit: str | None,
        kind: ValueKind,
        session_index: int,
        turn_index: int,
    ) -> None:
        # Reuse v1 extraction verbatim; then record v2 clustering + correction meta.
        super()._add_assertion(
            sentence, span, display, normalized, unit, kind, session_index, turn_index
        )
        edge = self.edges[-1]
        # Derive the cluster signature from the RAW sentence, not the marker-substituted
        # subject text: the count regex can swallow a scope adjective ("four Korean
        # restaurants") into the value span, and the marker itself ("<count>",
        # "local_time") would otherwise pollute the token set.
        cluster_key = self._cluster_key(sentence, kind, unit)
        present, past = self._correction_signal(sentence, span)
        self._meta[edge.edge_id] = _V2Meta(cluster_key, present, past, edge.ordinal)

    def _cluster_key(self, sentence: str, kind: ValueKind, unit: str | None) -> tuple:
        words = _words(sentence)
        attribute = self._attribute(words)
        entity_unit = _singular((unit or "").lower())
        if entity_unit in {"usd", "local_time", "weekday"}:
            entity_unit = ""
        entity_unit = _ALIAS.get(entity_unit, entity_unit)
        unit_bucket = self._unit_bucket(kind, unit)
        if self.grouping == "coarse":
            # Ignore fragmenting context tokens: cluster by attribute + kind + unit +
            # entity noun only (near-oracle for single-attribute KU items).
            return (attribute, kind.value, unit_bucket, entity_unit)
        toks = [
            _ALIAS.get(t, t)
            for t in _content_tokens(sentence)
            if t not in _DROP_STRUCTURAL and t not in _NOISE and t not in _ATTR_VERBS
        ]
        if entity_unit:
            toks.append(entity_unit)
        scope = frozenset(toks)
        return (attribute, scope, kind.value, unit_bucket)

    def stale_value_strings(self, query: str) -> set[str]:
        """Display strings of NON-current values for clusters whose kind the question
        asks about. Used by v3 authoritative composition to suppress untyped recall
        snippets that reintroduce a superseded value."""
        kinds = _query_kind_boosts(query)
        current_ids, _ = self._current_edge_ids()
        current_disp = {
            self.values[e.target_node_id].display.lower()
            for e in self.edges if e.edge_id in current_ids
        }
        stale: set[str] = set()
        for edge in self.edges:
            if edge.edge_id in current_ids:
                continue
            value = self.values[edge.target_node_id]
            if kinds and value.kind not in kinds:
                continue
            disp = value.display.lower()
            if disp and disp not in current_disp:
                stale.add(disp)
        return stale

    @staticmethod
    def _attribute(words: list[str]) -> str:
        # "on ... list" (watch list / reading list) is its own state family, and the
        # watch/read verb there is part of the list's name, not the action.
        if "list" in words:
            return "on_list"
        # Prefer a specific content verb over the generic possession verb, so an
        # auxiliary ("have been waking") does not mask the real action ("wake").
        _generic = {"have", "has", "had", "own", "owned", "got", "added", "collect", "collecting"}
        fallback = ""
        for w in words:
            fam = _ATTR_VERBS.get(w)
            if not fam:
                continue
            if w not in _generic:
                return fam
            if not fallback:
                fallback = fam
        return fallback

    @staticmethod
    def _unit_bucket(kind: ValueKind, unit: str | None) -> str:
        # For duration/measurement the unit distinguishes series (hours vs weeks);
        # for counts the counted noun already lives in the scope set.
        if kind in {ValueKind.DURATION, ValueKind.MEASUREMENT, ValueKind.FREQUENCY}:
            return (unit or "").lower()
        return ""

    @staticmethod
    def _correction_signal(sentence: str, span: tuple[int, int]) -> tuple[bool, bool]:
        start, end = span
        before = sentence[max(0, start - 40):start]
        after = sentence[end:end + 24]
        window = f"{before} {after}"
        past = bool(_PAST_MARKERS.search(window)) or bool(_NOT_BEFORE.search(before))
        present = bool(_PRESENT_MARKERS.search(window)) and not past
        return present, past

    def _current_edge_ids(self) -> tuple[set[str], dict[str, str]]:
        """Return (current_edge_ids, latest_historical_by_cluster)."""
        clusters: dict[tuple, list[str]] = {}
        for edge in self.edges:
            meta = self._meta.get(edge.edge_id)
            if meta is None:
                continue
            clusters.setdefault(meta.cluster_key, []).append(edge.edge_id)
        current: set[str] = set()
        latest_hist: dict[str, str] = {}
        for key, eids in clusters.items():
            non_past = [e for e in eids if not self._meta[e].past]
            pool = non_past or eids
            authoritative = [e for e in pool if self._meta[e].present]
            ranked = authoritative or pool
            chosen = max(ranked, key=lambda e: self._meta[e].ordinal)
            current.add(chosen)
            others = [e for e in eids if e != chosen]
            if others:
                latest_hist[key] = max(others, key=lambda e: self._meta[e].ordinal)
        return current, latest_hist

    def recall(self, query: str, limit: int = 4, *, emit_history: bool = False) -> list[str]:  # type: ignore[override]
        """Rank like v1 but over ONLY the CURRENT value per cluster (optionally plus the
        single most-recent historical per cluster, labeled ``was``). Self-contained so
        non-candidate edges never consume a slot."""
        if limit <= 0:
            return []
        current_ids, latest_hist = self._current_edge_ids()
        # Recompute edge.current so ranking + snippet labels reflect v2 supersession.
        for edge in self.edges:
            edge.current = edge.edge_id in current_ids
        candidate_ids = set(current_ids)
        if emit_history:
            candidate_ids |= set(latest_hist.values())
        query_tokens = _tokens(query)
        kind_boosts = _query_kind_boosts(query)
        ranked: list[tuple[float, object]] = []
        for edge in self.edges:
            if edge.edge_id not in candidate_ids:
                continue
            subject = self.subjects[edge.source_node_id]
            value = self.values[edge.target_node_id]
            overlap = len(query_tokens & _tokens(f"{subject.text} {edge.fact}"))
            score = float(overlap * 10)
            score += 8 if value.kind in kind_boosts else 0
            score += 2 if edge.current else 0
            score += edge.ordinal / 1_000_000
            if score > 0:
                ranked.append((score, edge))
        ranked.sort(key=lambda item: item[0], reverse=True)
        snippets: list[str] = []
        seen_facts: set[str] = set()
        for _, edge in ranked:
            if edge.fact in seen_facts:
                continue
            seen_facts.add(edge.fact)
            snippets.append(self._snippet(edge))
            if len(snippets) >= limit:
                break
        return snippets

    def _snippet(self, edge) -> str:  # type: ignore[override]
        value = self.values[edge.target_node_id]
        state = "current" if edge.current else "was"
        return f"[typed-value {value.kind.value} {state}] {edge.fact}"
