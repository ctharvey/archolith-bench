"""Bench-only typed-value graph for LongMemEval experiments.

The extractor is deterministic and question-blind: it reads user turns only and
never sees the benchmark answer. Each value node is assertion-scoped, so equal
values in unrelated memories cannot be merged by entity resolution.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any, Iterable


class ValueKind(StrEnum):
    """Typed-value families supported by the experiment."""

    BOOLEAN = "boolean"
    CLOCK_TIME = "clock_time"
    COUNT = "count"
    DURATION = "duration"
    FREQUENCY = "frequency"
    MEASUREMENT = "measurement"
    MONEY = "money"
    STATUS = "status"
    WEEKDAY = "weekday"


@dataclass(frozen=True)
class SubjectNode:
    """A source sentence with its typed value replaced by a typed marker."""

    node_id: str
    text: str


@dataclass(frozen=True)
class ValueNode:
    """An immutable value whose identity is local to one source assertion."""

    node_id: str
    kind: ValueKind
    display: str
    normalized: bool | int | float | str | list[int | float]
    unit: str | None


@dataclass
class ValueAssertionEdge:
    """A subject-to-value assertion with lightweight update state."""

    edge_id: str
    source_node_id: str
    target_node_id: str
    predicate: str
    fact: str
    session_index: int
    turn_index: int
    ordinal: int
    current: bool = True
    superseded_by: str | None = None


_ONES = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
    "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,
}
_TENS = {
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60,
    "seventy": 70, "eighty": 80, "ninety": 90,
}
_NUMBER_WORDS = sorted(
    [*_ONES, *_TENS, *(f"{t}-{o}" for t in _TENS for o in list(_ONES)[1:10])],
    key=len,
    reverse=True,
)
_NUMBER = rf"(?:\d[\d,]*(?:\.\d+)?|{'|'.join(map(re.escape, _NUMBER_WORDS))})"
_DURATION_UNITS = "seconds?|minutes?|hours?|days?|weeks?|months?|years?"
_MEASUREMENT_UNITS = (
    "ounces?|pounds?|grams?|kilograms?|miles?|kilometers?|feet|foot|inches?|cups?|"
    "tablespoons?|teaspoons?|percent(?:age)?"
)
_COUNT_UNITS = (
    "restaurants?|titles?|pages?|sessions?|films?|movies?|wears?|times?|episodes?|videos?|"
    "points?|coins?|nights?|engineers?|bikes?|recipes?|stories?|postcards?|followers?|issues?|"
    "classes?|items?|books?|songs?|attempts?|visits?|runs?|ones?"
)

_MONEY_RE = re.compile(r"(?<!\w)\$(?P<amount>\d[\d,]*(?:\.\d{1,2})?)\b", re.IGNORECASE)
_CLOCK_RE = re.compile(
    r"(?<!\d)(?P<hour>1[0-2]|0?[1-9]):(?P<minute>[0-5]\d)\s*(?P<period>[ap]\.?m\.?)\b",
    re.IGNORECASE,
)
_FREQUENCY_RE = re.compile(
    rf"\b(?:(?P<number>{_NUMBER})\s+times?\s+(?:a|an|per)\s+"
    r"(?P<number_period>day|week|month|year)|"
    r"(?P<named>once|twice)\s+(?:a|an|per)\s+(?P<named_period>day|week|month|year)|"
    r"(?P<every>every\s+other\s+(?:day|week|month|year)|daily|weekly|monthly|yearly))\b",
    re.IGNORECASE,
)
_WEEKDAY_RE = re.compile(
    r"\b(?P<weekday>Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b",
    re.IGNORECASE,
)
_STATUS_RE = re.compile(
    r"\b(?P<status>finished|completed|put down(?=(?:\s+\S+){0,8}\s+temporarily\b))\b",
    re.IGNORECASE,
)
_BOOLEAN_RE = re.compile(
    r"\b(?P<boolean>do not have|don't have|no longer have|have|own)"
    r"(?=\s+(?:an?\s+)?(?:spare|extra|backup)\b)",
    re.IGNORECASE,
)
_DURATION_RE = re.compile(
    rf"\b(?P<start>{_NUMBER})(?:\s*[-\u2013]\s*(?P<end>{_NUMBER}))?\s+"
    rf"(?P<unit>{_DURATION_UNITS})\b",
    re.IGNORECASE,
)
_MEASUREMENT_RE = re.compile(
    rf"\b(?P<start>{_NUMBER})(?:\s*[-\u2013]\s*(?P<end>{_NUMBER}))?\s+"
    rf"(?P<unit>{_MEASUREMENT_UNITS})\b",
    re.IGNORECASE,
)
_COUNT_RE = re.compile(
    rf"\b(?P<start>{_NUMBER})(?:\s*[-\u2013]\s*(?P<end>{_NUMBER}))?\s+"
    rf"(?:(?:[A-Za-z][\w'-]*\s+){{0,3}}?)(?P<unit>{_COUNT_UNITS})\b",
    re.IGNORECASE,
)
_REVERSED_COUNT_RE = re.compile(
    rf"\b(?P<unit>pages?|points?|episodes?|videos?|titles?)\s+(?P<start>{_NUMBER})\b",
    re.IGNORECASE,
)
_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+|\n+")
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOP_WORDS = {
    "a", "an", "and", "are", "did", "do", "does", "for", "have", "how", "i", "in",
    "is", "it", "me", "my", "of", "on", "the", "to", "was", "what", "when",
}
_PREDICATE_BY_KIND = {
    ValueKind.BOOLEAN: "HAS_BOOLEAN",
    ValueKind.CLOCK_TIME: "OCCURS_AT",
    ValueKind.COUNT: "HAS_COUNT",
    ValueKind.DURATION: "HAS_DURATION",
    ValueKind.FREQUENCY: "HAS_FREQUENCY",
    ValueKind.MEASUREMENT: "HAS_MEASUREMENT",
    ValueKind.MONEY: "HAS_AMOUNT",
    ValueKind.STATUS: "HAS_STATUS",
    ValueKind.WEEKDAY: "OCCURS_ON",
}


def _stable_id(*parts: object) -> str:
    raw = "\x1f".join(str(part) for part in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _number(raw: str) -> int | float:
    value = raw.lower().replace(",", "").replace(" ", "-")
    if re.fullmatch(r"\d+(?:\.\d+)?", value):
        return float(value) if "." in value else int(value)
    if value in _ONES:
        return _ONES[value]
    if value in _TENS:
        return _TENS[value]
    tens, ones = value.split("-", maxsplit=1)
    return _TENS[tens] + _ONES[ones]


def _tokens(text: str) -> set[str]:
    tokens: set[str] = set()
    for token in _TOKEN_RE.findall(text.lower()):
        if token in _STOP_WORDS:
            continue
        if len(token) > 4 and token.endswith("ies"):
            token = f"{token[:-3]}y"
        elif len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
            token = token[:-1]
        tokens.add(token)
    return tokens


def _query_kind_boosts(query: str) -> set[ValueKind]:
    low = query.lower()
    kinds: set[ValueKind] = set()
    if re.match(r"\s*(did|do|does|is|are|have|has)\b", low):
        kinds.add(ValueKind.BOOLEAN)
    if "finish" in low or "complete" in low or "status" in low:
        kinds.add(ValueKind.STATUS)
    if "how many" in low:
        kinds.add(ValueKind.COUNT)
    if "how long" in low:
        kinds.add(ValueKind.DURATION)
    if "how often" in low or "frequent" in low:
        kinds.add(ValueKind.FREQUENCY)
    if "how much" in low or "amount" in low or "earn" in low or "cost" in low:
        kinds.update({ValueKind.MONEY, ValueKind.MEASUREMENT})
    if "what time" in low:
        kinds.add(ValueKind.CLOCK_TIME)
    if "what day" in low or "day of the week" in low:
        kinds.add(ValueKind.WEEKDAY)
    return kinds


class ValueGraph:
    """Small assertion graph used only by the experimental benchmark arm."""

    def __init__(self, namespace: str) -> None:
        self.namespace = namespace
        self.subjects: dict[str, SubjectNode] = {}
        self.values: dict[str, ValueNode] = {}
        self.edges: list[ValueAssertionEdge] = []
        self._latest_by_slot: dict[tuple[str, str, str | None], ValueAssertionEdge] = {}
        self._ordinal = 0

    @classmethod
    def from_sessions(cls, namespace: str, sessions: Iterable[Iterable[dict[str, Any]]]) -> ValueGraph:
        """Build a question-blind graph from user turns in their supplied order."""
        graph = cls(namespace)
        for session_index, session in enumerate(sessions):
            graph._add_session(session, session_index=session_index)
        return graph

    @classmethod
    def from_item(
        cls,
        namespace: str,
        item: dict[str, Any],
        sessions: Iterable[Iterable[dict[str, Any]]],
    ) -> ValueGraph:
        """Build from a benchmark item, ordering sessions by their event dates."""
        graph = cls(namespace)
        session_list = list(sessions)
        dates = list(item.get("haystack_dates") or [])
        order = sorted(
            range(len(session_list)),
            key=lambda index: (dates[index] if index < len(dates) else "", index),
        )
        for session_index in order:
            graph._add_session(session_list[session_index], session_index=session_index)
        return graph

    def _add_session(self, session: Iterable[dict[str, Any]], *, session_index: int) -> None:
        for turn_index, turn in enumerate(session):
            if str(turn.get("role", "user")).strip().lower() != "user":
                continue
            self.add_turn(
                str(turn.get("content", "")),
                session_index=session_index,
                turn_index=turn_index,
            )

    def add_turn(self, text: str, *, session_index: int, turn_index: int) -> None:
        """Extract typed values from one user turn."""
        for sentence in (part.strip() for part in _SENTENCE_BOUNDARY.split(text) if part.strip()):
            self._add_sentence(sentence, session_index=session_index, turn_index=turn_index)

    def recall(self, query: str, limit: int = 4) -> list[str]:
        """Return typed assertions ranked by subject overlap and question value intent."""
        if limit <= 0:
            return []
        query_tokens = _tokens(query)
        kind_boosts = _query_kind_boosts(query)
        ranked: list[tuple[float, ValueAssertionEdge]] = []
        for edge in self.edges:
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

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable audit representation."""
        return {
            "namespace": self.namespace,
            "subjects": [asdict(node) for node in self.subjects.values()],
            "values": [asdict(node) for node in self.values.values()],
            "edges": [asdict(edge) for edge in self.edges],
        }

    def _add_sentence(self, sentence: str, *, session_index: int, turn_index: int) -> None:
        occupied: list[tuple[int, int]] = []
        specs = [
            (ValueKind.BOOLEAN, _BOOLEAN_RE),
            (ValueKind.STATUS, _STATUS_RE),
            (ValueKind.MONEY, _MONEY_RE),
            (ValueKind.CLOCK_TIME, _CLOCK_RE),
            (ValueKind.FREQUENCY, _FREQUENCY_RE),
            (ValueKind.WEEKDAY, _WEEKDAY_RE),
            (ValueKind.DURATION, _DURATION_RE),
            (ValueKind.MEASUREMENT, _MEASUREMENT_RE),
            (ValueKind.COUNT, _COUNT_RE),
            (ValueKind.COUNT, _REVERSED_COUNT_RE),
        ]
        for kind, pattern in specs:
            for match in pattern.finditer(sentence):
                span = match.span()
                if kind == ValueKind.BOOLEAN and re.search(
                    r"\b(?:do|does|did|can|could|would|will)\s+(?:i|we|you|they|he|she)"
                    r"(?:\s+\w+){0,2}\s*$",
                    sentence[:span[0]],
                    re.IGNORECASE,
                ):
                    continue
                if any(span[0] < end and span[1] > start for start, end in occupied):
                    continue
                occupied.append(span)
                display, normalized, unit = self._match_value(kind, match)
                self._add_assertion(
                    sentence,
                    span,
                    display,
                    normalized,
                    unit,
                    kind,
                    session_index,
                    turn_index,
                )

    def _add_assertion(
        self,
        sentence: str,
        span: tuple[int, int],
        display: str,
        normalized: bool | int | float | str | list[int | float],
        unit: str | None,
        kind: ValueKind,
        session_index: int,
        turn_index: int,
    ) -> None:
        marker = f"{unit or 'value'} <{kind.value}>"
        subject_text = re.sub(
            r"\s+",
            " ",
            f"{sentence[:span[0]]}{marker}{sentence[span[1]:]}",
        ).strip()
        subject_id = _stable_id(self.namespace, "subject", subject_text.lower())
        self.subjects.setdefault(subject_id, SubjectNode(subject_id, subject_text))
        value_id = _stable_id(
            self.namespace,
            "value",
            session_index,
            turn_index,
            *span,
            kind.value,
            display.lower(),
        )
        self.values[value_id] = ValueNode(value_id, kind, display, normalized, unit)
        predicate = _PREDICATE_BY_KIND[kind]
        edge_id = _stable_id(self.namespace, "edge", subject_id, value_id, predicate)
        edge = ValueAssertionEdge(
            edge_id,
            subject_id,
            value_id,
            predicate,
            sentence,
            session_index,
            turn_index,
            self._ordinal,
        )
        self._ordinal += 1
        slot = (subject_id, predicate, unit)
        previous = self._latest_by_slot.get(slot)
        if previous is not None and previous.target_node_id != value_id:
            previous.current = False
            previous.superseded_by = edge_id
        self._latest_by_slot[slot] = edge
        self.edges.append(edge)

    @staticmethod
    def _match_value(
        kind: ValueKind,
        match: re.Match[str],
    ) -> tuple[str, bool | int | float | str | list[int | float], str | None]:
        if kind == ValueKind.BOOLEAN:
            raw = match.group("boolean").lower()
            return match.group(0), raw not in {"do not have", "don't have", "no longer have"}, None
        if kind == ValueKind.STATUS:
            raw = match.group("status").lower()
            normalized = "paused" if raw.startswith("put down") else "finished"
            return match.group(0), normalized, None
        if kind == ValueKind.MONEY:
            return match.group(0), _number(match.group("amount")), "USD"
        if kind == ValueKind.CLOCK_TIME:
            hour = int(match.group("hour"))
            minute = int(match.group("minute"))
            period = match.group("period").lower().replace(".", "")
            normalized_hour = (hour % 12) + (12 if period == "pm" else 0)
            return match.group(0), f"{normalized_hour:02d}:{minute:02d}", "local_time"
        if kind == ValueKind.WEEKDAY:
            return match.group(0), match.group("weekday").lower(), "weekday"
        if kind == ValueKind.FREQUENCY:
            raw = match.group(0)
            if match.group("number"):
                period = match.group("number_period").lower()
                return raw, f"{_number(match.group('number'))}/{period}", period
            if match.group("named"):
                period = match.group("named_period").lower()
                count = 1 if match.group("named").lower() == "once" else 2
                return raw, f"{count}/{period}", period
            named = match.group("every").lower()
            normalized = {
                "daily": "1/day",
                "weekly": "1/week",
                "monthly": "1/month",
                "yearly": "1/year",
            }.get(named, named.replace(" ", "_"))
            return raw, normalized, named.rsplit(" ", maxsplit=1)[-1]
        start = match.group("start")
        end = match.groupdict().get("end")
        normalized: int | float | list[int | float] = _number(start)
        if end:
            normalized = [normalized, _number(end)]
        return match.group(0), normalized, match.group("unit").lower()

    def _snippet(self, edge: ValueAssertionEdge) -> str:
        value = self.values[edge.target_node_id]
        state = "current" if edge.current else "superseded"
        return f"[typed-value {value.kind.value} {state}] {edge.fact}"

