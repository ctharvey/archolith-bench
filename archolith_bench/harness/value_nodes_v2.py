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


# --- v5 delta lexicon (deterministic increment/decrement events; question/answer-blind) ---
# Each pattern requires an explicit quantity (digit, number word, or a/an/another) so vague
# statements ("added some coins") never produce a delta. The counted noun is singularized and
# matched to a COUNT cluster's entity noun; unmatched deltas are dropped (no guess).
_NUM = r"\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve"
# +1 article form ONLY ("added a new coin"). Bare "got N nouns" is deliberately NOT an
# increment - it is ambiguous with stating a new absolute ("I got 25 titles" = the list is now
# 25, not +25), which produced a confident-wrong fold on 4d6b87c8. Explicit multi-unit
# increments must say "more/additional/extra" and are matched by _DELTA_MORE.
_DELTA_ADD = re.compile(
    r"\b(?:added|acquired|purchased|bought|picked up|got)\s+(?:a|an|another|one)\s+"
    r"(?:new\s+|extra\s+|other\s+)?(?P<noun>[a-z]+)",
    re.IGNORECASE,
)
_DELTA_MORE = re.compile(
    rf"\b(?P<n>{_NUM})\s+(?:more|additional|extra)\s+(?P<noun>[a-z]+)", re.IGNORECASE
)
_DELTA_SUB = re.compile(
    rf"\b(?:sold|lost|gave away|got rid of|donated|removed)\s+(?P<n>{_NUM}|a|an|one)\s+(?P<noun>[a-z]+)",
    re.IGNORECASE,
)
# Numbers appearing in a temporal reference ("pre-1920", "since 2019") are years, not counts;
# v1 sometimes extracts them as a count of the following noun. Exclude them from anchors.
def _is_temporal_ref(fact: str, value: int) -> bool:
    return bool(
        re.search(
            rf"(?:pre-?|post-?|since\s+|before\s+|after\s+|in\s+|circa\s+){value}\b",
            fact,
            re.IGNORECASE,
        )
    )


def _delta_int(token: str) -> int | None:
    """Parse a delta magnitude from a digit, number word, or singular article."""
    t = token.lower().strip()
    if t.isdigit():
        return int(t)
    if t in {"a", "an", "another"}:
        return 1
    if t in _ONES:
        return _ONES[t]
    if t in _TENS:
        return _TENS[t]
    return None


@dataclass(frozen=True)
class _DeltaEvent:
    magnitude: int  # signed: + increment, - decrement
    noun: str       # singularized + aliased counted noun (cluster match key)
    session_index: int
    turn_index: int
    phrase: str     # evidence text for the advisory hint


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
        self._deltas: list[_DeltaEvent] = []  # v5 increment/decrement events
        self._delta_origin: set[str] = set()  # count edges whose value is a delta magnitude
        self._pending_delta_spans: list[tuple[int, int]] = []
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
        # A count value whose span sits inside a delta phrase ("3 more cards") is the delta
        # magnitude, not an independent anchor; record it so _derived_hints excludes it.
        if kind is ValueKind.COUNT and any(
            span[0] < end and span[1] > start for start, end in self._pending_delta_spans
        ):
            self._delta_origin.add(edge.edge_id)

    def _add_sentence(self, sentence: str, *, session_index: int, turn_index: int) -> None:  # type: ignore[override]
        # Capture delta events first so their spans are known while v1 extraction runs: a count
        # value that lies inside a delta phrase ("3 more cards") is the delta magnitude, not a
        # standalone anchor, and must be excluded from the anchor set in _add_assertion.
        self._pending_delta_spans = self._scan_deltas(sentence, session_index, turn_index)
        super()._add_sentence(sentence, session_index=session_index, turn_index=turn_index)
        self._pending_delta_spans = []

    def _scan_deltas(
        self, sentence: str, session_index: int, turn_index: int
    ) -> list[tuple[int, int]]:
        # Verb-anchored patterns first so the bare "N more <noun>" pattern cannot double-count
        # the same span ("bought 3 more cards" is one +3 event, not +3 twice).
        occupied: list[tuple[int, int]] = []
        # (pattern, sign, has_explicit_n). _DELTA_ADD is the +1 article form (no "n" group).
        for pattern, sign, has_n in ((_DELTA_ADD, 1, False), (_DELTA_SUB, -1, True), (_DELTA_MORE, 1, True)):
            for match in pattern.finditer(sentence):
                span = match.span()
                if any(span[0] < end and span[1] > start for start, end in occupied):
                    continue
                magnitude = _delta_int(match.group("n")) if has_n else 1
                if not magnitude:
                    continue
                occupied.append(span)
                noun = _singular(match.group("noun").lower())
                noun = _ALIAS.get(noun, noun)
                self._deltas.append(
                    _DeltaEvent(sign * magnitude, noun, session_index, turn_index, match.group(0).strip())
                )
        return occupied

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

    # --- v4 advisory composition -----------------------------------------------------
    # The v3 experiment showed authoritative single-pick + suppression nets negative:
    # every regression came from DELETING the correct candidate (71315a70 wrong recency
    # pick, dfde3500 over-merged referents, e66b632c previous-value question). The typed
    # layer's recency signal was right; the act of deletion lost the answer. The advisory
    # arm therefore ADVISES instead of decides: keep every candidate (additive, so it can
    # never drop the right value), annotate each with its cluster role, and hard-suppress
    # ONLY an author-rejected value (explicit correction marker on the cluster) - the one
    # deletion that cannot backfire because the user themselves rejected it.

    def _advisory_labels(self) -> tuple[dict[str, str], set[str]]:
        """Per-edge advisory role labels and the set of author-rejected edge ids to drop.

        Recency is asserted (and a value deleted) ONLY for an unambiguous BINARY supersession:
        the author explicitly rejected a competing value (an explicit-past / ``not X`` marker -
        ``used to``, ``no longer``, ``previously``, ``..., not <value>``) AND exactly one distinct
        value survives to replace it. Two conditions, both required:
          * A bare present marker (``now``, ``currently``) is NOT enough - the marker regex is
            noisy on multi-clause turns and a present marker does not identify *which* sibling
            went stale (this drove the v3 wrong-``current`` picks, e.g. 71315a70's 5-6h).
          * If more than one distinct value survives, the (coarse) cluster is over-merged across
            referents (dfde3500 merges Juan/Wednesday with Maria/Thursday); asserting a single
            ``current`` there tags the wrong referent, so the whole cluster degrades to a
            candidate list and nothing is deleted.
        Labels, for clusters with >1 distinct display value:
          * clean binary supersession -> replacement value(s) = ``current``, rejected = DROPPED;
          * otherwise every member = ``candidate`` (the answer model disambiguates - no unearned
            recency claim, no deletion).
        Single-value clusters get no label (plain typed snippet).
        """
        by_id = {edge.edge_id: edge for edge in self.edges}
        clusters: dict[tuple, list[str]] = {}
        for edge in self.edges:
            meta = self._meta.get(edge.edge_id)
            if meta is None:
                continue
            clusters.setdefault(meta.cluster_key, []).append(edge.edge_id)
        labels: dict[str, str] = {}
        drop: set[str] = set()
        for eids in clusters.values():
            displays = {self.values[by_id[e].target_node_id].display for e in eids}
            if len(displays) <= 1:
                continue  # nothing to disambiguate
            rejected = [e for e in eids if self._meta[e].past]
            survivors = [e for e in eids if not self._meta[e].past]
            survivor_values = {self.values[by_id[e].target_node_id].display for e in survivors}
            # Clean binary supersession only: explicit rejection + a single surviving value.
            # Anything else (no rejection, or multiple surviving values = over-merged cluster)
            # degrades to a neutral candidate list with no deletion.
            if rejected and len(survivor_values) == 1:
                for e in rejected:
                    labels[e] = "superseded"
                    drop.add(e)
                for e in survivors:
                    labels[e] = "current"
            else:
                for e in eids:
                    labels[e] = "candidate"
        return labels, drop

    def advisory_recall(self, query: str, limit: int = 4) -> list[str]:
        """Additive v1-style ranking (never drops a candidate) with advisory role labels.

        Reuses v1's exact ranking so answer-support is >= additive v1; the only additions
        are (a) role annotations from ``_advisory_labels`` and (b) removal of author-rejected
        values (explicit correction markers only). A small nudge floats a marker-confirmed
        ``current`` above its ``earlier`` siblings without displacing unrelated snippets."""
        if limit <= 0:
            return []
        labels, drop = self._advisory_labels()
        query_tokens = _tokens(query)
        kind_boosts = _query_kind_boosts(query)
        ranked: list[tuple[float, object]] = []
        for edge in self.edges:
            if edge.edge_id in drop:
                continue
            subject = self.subjects[edge.source_node_id]
            value = self.values[edge.target_node_id]
            overlap = len(query_tokens & _tokens(f"{subject.text} {edge.fact}"))
            score = float(overlap * 10)
            score += 8 if value.kind in kind_boosts else 0
            score += 2 if labels.get(edge.edge_id) == "current" else 0
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
            snippets.append(self._advisory_snippet(edge, labels.get(edge.edge_id)))
            if len(snippets) >= limit:
                break
        return snippets

    def _advisory_snippet(self, edge, label: str | None) -> str:
        value = self.values[edge.target_node_id]
        tag = f"{value.kind.value} {label}" if label else value.kind.value
        return f"[typed-value {tag}] {edge.fact}"

    # --- v5 derivation ("assumptions") layer -----------------------------------------
    # Targets the miss class no selection mechanism reaches, because the answer is never
    # stated literally (69fee5aa: "37 coins" + "added a new coin" -> 38). The typed layer
    # DERIVES the value by folding signed deltas onto a single stated anchor and surfaces it
    # as an explicitly-labeled ADVISORY hint (never authoritative; the v4 base is unchanged
    # and no stated value is deleted). Gated hard toward silence: the catastrophic failure is
    # a confident-wrong derived number, so a hint fires only for an unambiguous, integer-
    # consistent, query-relevant fold.

    def derived_recall(self, query: str, limit: int = 4) -> list[str]:
        """v4 advisory base + at most one derived count hint per relevant cluster, prepended
        within the same total top-k. Falls back to plain advisory when nothing derives."""
        base = self.advisory_recall(query, limit)
        hints = self._derived_hints(query)
        if not hints:
            return base
        merged: list[str] = []
        seen: set[str] = set()
        for snippet in [*hints, *base]:
            if snippet in seen:
                continue
            seen.add(snippet)
            merged.append(snippet)
            if len(merged) >= limit:
                break
        return merged

    def _derived_hints(self, query: str) -> list[str]:
        """Derive count values by folding signed deltas onto a single stated anchor.

        Emits a hint for a COUNT cluster only when ALL hold: the counted noun is asked about
        (query-relevant); exactly one distinct integer anchor exists; >=1 delta with the same
        counted noun occurs at-or-after the anchor; the fold is integer-consistent, non-negative,
        and differs from every stated value (else it is redundant). Otherwise emit nothing.
        """
        if not self._deltas:
            return []
        low_query = query.lower()
        # Aggregate valid COUNT anchors per counted noun ACROSS ALL clusters. The anchor gate is
        # global on purpose: if a noun has more than one distinct stated count anywhere (e.g. an
        # incidental "my other two bikes" alongside "three bikes" and "four bikes"), its count is
        # ambiguous and no fold is trustworthy - derive nothing. Over-merging distinct attributes
        # here only causes MORE silence, never a wrong derivation. Temporal-reference years and
        # delta-magnitude counts are excluded from anchors.
        anchor_values: dict[str, set[int]] = {}
        stated: dict[str, set[int]] = {}
        anchor_key: dict[str, tuple[int, int]] = {}
        for edge in self.edges:
            meta = self._meta.get(edge.edge_id)
            if meta is None:
                continue
            value = self.values[edge.target_node_id]
            if value.kind is not ValueKind.COUNT:
                continue
            noun = meta.cluster_key[3] if len(meta.cluster_key) >= 4 else ""
            if not noun:
                continue
            normalized = value.normalized
            if isinstance(normalized, list):
                stated.setdefault(noun, set()).update(
                    x for x in normalized if isinstance(x, int) and not isinstance(x, bool)
                )
                continue
            if not isinstance(normalized, int) or isinstance(normalized, bool):
                continue
            if edge.edge_id in self._delta_origin or _is_temporal_ref(edge.fact, normalized):
                continue
            anchor_values.setdefault(noun, set()).add(normalized)
            stated.setdefault(noun, set()).add(normalized)
            key = (edge.session_index, edge.turn_index)
            if noun not in anchor_key or key < anchor_key[noun]:
                anchor_key[noun] = key
        hints: list[str] = []
        for noun, values in anchor_values.items():
            if noun not in low_query:
                continue  # relevance gate: only surface a hint the question asks about
            if len(values) != 1:
                continue  # globally ambiguous stated count -> silence
            anchor_value = next(iter(values))
            deltas = [
                d for d in self._deltas
                if d.noun == noun and (d.session_index, d.turn_index) >= anchor_key[noun]
            ]
            if not deltas:
                continue
            total = sum(d.magnitude for d in deltas)
            derived = anchor_value + total
            if total == 0 or derived < 0 or derived in stated.get(noun, set()):
                continue  # no-op, impossible, or redundant with a stated value
            evidence = "; ".join(d.phrase for d in deltas[:2])
            sign = f"+{total}" if total > 0 else str(total)
            hints.append(
                f"[typed-value count derived] {noun}: ~{derived} "
                f"(stated {anchor_value} {sign}: {evidence})"
            )
        return hints
