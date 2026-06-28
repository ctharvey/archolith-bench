"""Deterministic facet extraction — cheap rules, no LLM.

This is the "extracted facets" mode from the R2 plan: it answers *can a cheap
extractor recover enough?* The output is intentionally compared **separately**
from gold facets so hand-authored labels never inflate the apparent extractor
quality (Risk #2 in the plan).

Every rule here is a regex or a vocabulary lookup. No model calls, no network,
fully deterministic given the same input + config.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .models import Memory, MemoryFacetSet

# A file path / filename with a known code-ish extension.
_FILE_RE = re.compile(
    r"\b[\w./-]+\.(?:py|md|json|js|ts|tsx|jsx|yaml|yml|toml|sh|txt|cfg|ini|rs|go|java)\b"
)
# test_foo / foo_test identifiers.
_TEST_RE = re.compile(r"\b(?:test_\w+|\w+_test)\b")
# PascalCase / CamelCase identifiers (≥2 internal caps-or-tail) — class/type names.
_PASCAL_RE = re.compile(r"\b[A-Z][a-z0-9]+(?:[A-Z][a-z0-9]+)+\b")
# A callable reference: word( ... — captures the function name.
_CALL_RE = re.compile(r"\b([a-z_][a-z0-9_]+)\s*\(")
# Backtick `code` spans and 'quoted' / "quoted" string literals → object candidates.
_BACKTICK_RE = re.compile(r"`([^`]+)`")
_QUOTED_RE = re.compile(r"[\"']([^\"']{2,})[\"']")
# An ISO date or datetime.
_ISO_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2})?)?\b")

# verb-lemma → surface forms. Matched as whole words, case-insensitive.
_OPERATION_LEXICON: dict[str, tuple[str, ...]] = {
    "add": ("add", "adds", "added", "adding", "introduce", "introduced", "create", "created"),
    "fix": ("fix", "fixes", "fixed", "fixing", "patch", "patched"),
    "remove": ("remove", "removed", "removes", "removing", "delete", "deleted", "drop", "dropped"),
    "rename": ("rename", "renamed", "renames", "renaming"),
    "refactor": ("refactor", "refactored", "refactors", "refactoring"),
    "revert": ("revert", "reverted", "reverts", "reverting", "rollback", "rolled back"),
    "deprecate": ("deprecate", "deprecated", "deprecates"),
    "update": ("update", "updated", "updates", "updating", "bump", "bumped"),
    "configure": ("configure", "configured", "config", "set", "enable", "enabled", "disable", "disabled"),
}

# keyword → canonical evidence_type.
_EVIDENCE_LEXICON: dict[str, str] = {
    "commit": "commit",
    "pr": "pr",
    "pull request": "pr",
    "test": "test",
    "log": "log",
    "logs": "log",
    "traceback": "log",
    "stack trace": "log",
    "issue": "issue",
    "benchmark": "benchmark",
    "bench": "benchmark",
    "trace": "trace",
}

# phrase → belief bucket heuristic.
_HISTORICAL_MARKERS: tuple[str, ...] = (
    "used to",
    "previously",
    "no longer",
    "deprecated",
    "formerly",
    "back then",
    "old approach",
    "we removed",
)
_CURRENT_MARKERS: tuple[str, ...] = ("now ", "currently", "current ", "as of today", "today we")


@dataclass
class ExtractorConfig:
    """Vocabularies the extractor needs that can't be inferred from free text.

    `repos` / `projects` / `namespaces` are matched as whole-word literals; they
    let the extractor recover scope facets a regex can't guess. Keep them small
    and fixture-specific.
    """

    repos: tuple[str, ...] = ()
    projects: tuple[str, ...] = ()
    namespaces: tuple[str, ...] = ()
    max_symbols: int = 8
    max_objects: int = 6


class FacetExtractor:
    """Derive a `MemoryFacetSet` from raw text with deterministic rules."""

    def __init__(self, config: ExtractorConfig | None = None) -> None:
        self.config = config or ExtractorConfig()

    def extract(self, text: str) -> MemoryFacetSet:
        lower = text.lower()
        facets = MemoryFacetSet()

        files = {m.group(0) for m in _FILE_RE.finditer(text)}
        facets.file = files

        tests = {m.group(0) for m in _TEST_RE.finditer(text)}
        facets.test = tests

        symbols: set[str] = set(_PASCAL_RE.findall(text))
        for name in _CALL_RE.findall(text):
            # Drop bare keywords that happen to be followed by "(".
            if name not in {"if", "for", "while", "return", "print", "def"}:
                symbols.add(name)
        # test names are their own facet; don't double-count them as symbols.
        symbols -= tests
        facets.symbol = set(sorted(symbols)[: self.config.max_symbols])

        objects: set[str] = set()
        objects.update(m.group(1).strip() for m in _BACKTICK_RE.finditer(text))
        objects.update(m.group(1).strip() for m in _QUOTED_RE.finditer(text))
        # backticked file/symbol tokens are already covered; keep objects distinct.
        objects -= files
        facets.object = set(sorted(objects)[: self.config.max_objects])

        facets.operation = {
            lemma
            for lemma, forms in _OPERATION_LEXICON.items()
            if any(_word_present(form, lower) for form in forms)
        }

        facets.evidence_type = {
            etype for keyword, etype in _EVIDENCE_LEXICON.items() if _word_present(keyword, lower)
        }

        facets.actor = self._extract_actor(text)
        facets.repo = _match_vocab(self.config.repos, lower)
        facets.project = _match_vocab(self.config.projects, lower)
        facets.namespace = _match_vocab(self.config.namespaces, lower)
        facets.belief_bucket = self._extract_bucket(lower)

        iso = _ISO_RE.search(text)
        facets.valid_time = iso.group(0) if iso else None

        return facets

    def extract_memory(self, memory: Memory) -> Memory:
        """Return a copy of `memory` whose facets come from extraction, not gold.

        Provenance facets that text cannot reveal (`source_id`, `learned_time`)
        are carried over from the gold record so they don't silently disappear in
        extracted mode — they aren't something an extractor is meant to infer.
        """
        extracted = self.extract(memory.text)
        extracted.source_id = memory.facets.source_id
        extracted.learned_time = memory.facets.learned_time
        return Memory(id=memory.id, text=memory.text, facets=extracted, superseded=memory.superseded)

    def extract_memory_hybrid(self, memory: Memory) -> Memory:
        """Hybrid extraction (facet-extraction-plan.md, Priority 6).

        Deterministic facets are **read from the gold record** — standing in for the
        Layer-2 structural model + Git history, where `file/symbol/test/repo/project/
        namespace/source_id/valid_time/learned_time/belief_bucket` are *exact*. Only
        the interpretive facets (`actor/object/operation/evidence_type`) are extracted
        from prose. This models the realistic case the pure-`extracted` mode gets
        wrong: a system never regexes "which repo / which file / when" out of text —
        it knows them; only intent is genuinely hard to recover.
        """
        interp = self.extract(memory.text)
        gold = memory.facets
        facets = MemoryFacetSet(
            # interpretive — recovered from text (the genuinely lossy part)
            actor=interp.actor,
            object=interp.object,
            operation=interp.operation,
            evidence_type=interp.evidence_type,
            # deterministic — read from structure/Git (gold stand-in), never from prose
            file=set(gold.file),
            symbol=set(gold.symbol),
            test=set(gold.test),
            repo=gold.repo,
            project=gold.project,
            namespace=gold.namespace,
            source_id=gold.source_id,
            valid_time=gold.valid_time,
            learned_time=gold.learned_time,
            belief_bucket=gold.belief_bucket,
        )
        return Memory(id=memory.id, text=memory.text, facets=facets, superseded=memory.superseded)

    def _extract_actor(self, text: str) -> set[str]:
        actors: set[str] = set()
        if re.search(r"\b(?:I|we|our|my)\b", text):
            actors.add("self")
        return actors

    def _extract_bucket(self, lower: str) -> str | None:
        if any(marker in lower for marker in _HISTORICAL_MARKERS):
            return "historical"
        if any(marker in lower for marker in _CURRENT_MARKERS):
            return "current"
        return None


def _word_present(needle: str, haystack_lower: str) -> bool:
    """Whole-word (or whole-phrase) membership test, case-insensitive."""
    return re.search(rf"\b{re.escape(needle.lower())}\b", haystack_lower) is not None


def _match_vocab(vocab: tuple[str, ...], haystack_lower: str) -> str | None:
    """Return the first vocab entry present as a whole word, else None."""
    for entry in vocab:
        if _word_present(entry, haystack_lower):
            return entry
    return None
