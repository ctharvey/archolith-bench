"""Adaptive claim segmentation for LME ingest.

Two-stage detector that identifies independently durable claims in conversation
turns, avoiding the 8x episode inflation of blind sentence splitting while
preserving extraction quality for knowledge-update scenarios.

Stage A: cheap deterministic gate (regex + heuristics)
Stage B: targeted LLM claim extraction (only for escalated messages)

See: .agent/plans/menhir-adaptive-claim-segmentation-plan.md
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class SegmentationMode(str, Enum):
    """Outcome of the segmentation decision."""
    CONTEXT_ONLY = "context_only"       # store as context, skip graph extraction
    EXTRACT_WHOLE = "extract_whole"     # extract the full message as one episode
    SEGMENT_CLAIMS = "segment_claims"   # extract individual claim spans
    SKIP = "skip"                       # do not ingest at all


@dataclass
class ClaimSegment:
    """A durable claim extracted from a longer message."""
    text: str
    subject: str = ""
    claim_type: str = ""        # state_update, new_fact, correction, etc.
    durable: bool = True
    char_start: int = 0
    char_end: int = 0
    segment_index: int = 0


@dataclass
class ClaimRiskSignals:
    """Signals detected by the Stage A deterministic gate."""
    correction_markers: list[str] = field(default_factory=list)
    state_change_verbs: list[str] = field(default_factory=list)
    sentence_count: int = 0
    char_length: int = 0
    has_multiple_subjects: bool = False
    has_topic_shift: bool = False
    has_buried_update: bool = False
    has_multiple_numbers: bool = False
    has_multiple_locations: bool = False

    @property
    def high_confidence_single_claim(self) -> bool:
        """Message likely contains at most one durable claim."""
        return (
            self.sentence_count <= 2
            and not self.correction_markers
            and not self.state_change_verbs
            and not self.has_multiple_subjects
        )

    @property
    def escalate(self) -> bool:
        """Any strong signal suggesting the message needs claim extraction."""
        return bool(
            self.correction_markers
            or self.state_change_verbs
            or self.has_multiple_subjects
            or self.has_topic_shift
            or self.has_buried_update
            or (self.has_multiple_numbers and self.char_length > 200)
            or (self.has_multiple_locations and self.char_length > 200)
        )


# ---------------------------------------------------------------------------
# Stage A: Deterministic gate
# ---------------------------------------------------------------------------

# Correction / update markers — words that signal a fact is being revised.
_CORRECTION_MARKERS = re.compile(
    r"\b(?:actually|instead|no longer|not anymore|now (?:that|I|we|she|he|they|it)|"
    r"used to|again|turns out|changed|anymore|switched|rather than)\b",
    re.IGNORECASE,
)

# State-change verbs — actions that create or revise durable facts.
_STATE_CHANGE_VERBS = re.compile(
    r"\b(?:moved|changed|started|stopped|switched|left|quit|joined|"
    r"bought|sold|married|divorced|graduated|retired|promoted|transferred|"
    r"adopted|resigned|relocated|enrolled|dropped)\b",
    re.IGNORECASE,
)

# Sentence boundary (same as the existing splitter).
_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")

# Multiple distinct numbers (dates, amounts, counts).
_NUMBER_PATTERN = re.compile(r"\$?\d[\d,]*(?:\.\d+)?(?:\s*(?:hours?|minutes?|times?|days?|weeks?|months?|years?))?")

# Location-like proper nouns (capitalized multi-word sequences after prepositions).
_LOCATION_PREP = re.compile(
    r"\b(?:in|to|from|at|near|around)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)",
)

# Subject-predicate detection: crude heuristic — count distinct capitalized names
# or first-person references that appear as sentence subjects.
_SUBJECT_PATTERN = re.compile(
    r"(?:^|[.!?]\s+)(?:My\s+(?:friend|sister|brother|mom|dad|wife|husband|partner)\s+)?"
    r"([A-Z][a-z]{2,})",
)
_FIRST_PERSON = re.compile(r"\b[Ii]\b")


def detect_claim_risk_signals(text: str) -> ClaimRiskSignals:
    """Stage A: analyze a message for signals that suggest multiple durable claims."""
    signals = ClaimRiskSignals()
    signals.char_length = len(text)

    # Sentence count
    sentences = _SENTENCE_BOUNDARY.split(text)
    signals.sentence_count = len([s for s in sentences if s.strip()])

    # Correction markers
    signals.correction_markers = [m.group() for m in _CORRECTION_MARKERS.finditer(text)]

    # State-change verbs
    signals.state_change_verbs = [m.group() for m in _STATE_CHANGE_VERBS.finditer(text)]

    # Multiple numbers
    numbers = _NUMBER_PATTERN.findall(text)
    signals.has_multiple_numbers = len(set(numbers)) >= 3

    # Multiple locations
    locations = _LOCATION_PREP.findall(text)
    signals.has_multiple_locations = len(set(locations)) >= 2

    # Multiple subjects — distinct named entities appearing as sentence subjects
    named_subjects = set(_SUBJECT_PATTERN.findall(text))
    # Filter out common non-name words that happen to be capitalized at sentence start
    _COMMON_STARTERS = {
        "The", "This", "That", "These", "Those", "What", "Where", "When",
        "How", "Why", "Which", "Who", "Here", "There", "Some", "Many",
        "Most", "Any", "Each", "Every", "Both", "All", "One", "Two",
        "Can", "Could", "Would", "Should", "Will", "May", "Might",
        "For", "And", "But", "Also", "Yes", "Yeah", "Sure", "Thanks",
        "Great", "Good", "Nice", "Sounds", "Let",
    }
    named_subjects -= _COMMON_STARTERS
    signals.has_multiple_subjects = len(named_subjects) >= 2

    # Buried update: long message with a correction marker or state-change verb
    # but most of the text is non-factual filler
    if (signals.char_length > 300
            and (signals.correction_markers or signals.state_change_verbs)
            and signals.sentence_count >= 3):
        signals.has_buried_update = True

    # Topic shift: check if distinct locations or named subjects appear in
    # different sentences (crude proxy for semantic distance)
    if signals.sentence_count >= 3:
        sentence_subjects = []
        for sent in sentences:
            subjs = set(_SUBJECT_PATTERN.findall(sent)) - _COMMON_STARTERS
            locs = set(_LOCATION_PREP.findall(sent))
            sentence_subjects.append(subjs | locs)
        # If non-overlapping subject sets across sentences, likely topic shift
        for i in range(len(sentence_subjects) - 1):
            if sentence_subjects[i] and sentence_subjects[i + 1]:
                if not sentence_subjects[i] & sentence_subjects[i + 1]:
                    signals.has_topic_shift = True
                    break

    return signals


def is_short_and_coherent(text: str, max_chars: int = 300, max_sentences: int = 3) -> bool:
    """Quick check: message is short enough to always extract as a whole."""
    if len(text) > max_chars:
        return False
    sentences = _SENTENCE_BOUNDARY.split(text)
    return len([s for s in sentences if s.strip()]) <= max_sentences


# ---------------------------------------------------------------------------
# Assistant turn classification
# ---------------------------------------------------------------------------

# Patterns that suggest an assistant message contains durable content
# (not just generic advice/filler).
_ASSISTANT_DURABLE_PATTERNS = re.compile(
    r"\b(?:I(?:'ve| have) (?:scheduled|booked|reserved|ordered|created|set up|"
    r"configured|deployed|committed|pushed|merged|installed)|"
    r"(?:your|the) (?:appointment|reservation|booking|order|subscription|"
    r"membership|account|profile|settings?) (?:is|are|has been|was)|"
    r"I(?:'ll| will) (?:remember|note|keep track|make a note)|"
    r"(?:confirmed|completed|finished|done|approved|accepted|rejected|denied|cancelled))\b",
    re.IGNORECASE,
)


def is_memory_bearing_assistant_output(text: str) -> bool:
    """Check if an assistant message contains durable-content classes worth extracting."""
    return bool(_ASSISTANT_DURABLE_PATTERNS.search(text))


# ---------------------------------------------------------------------------
# Top-level decision function
# ---------------------------------------------------------------------------

def segmentation_mode(
    role: str,
    content: str,
    *,
    max_short_chars: int = 300,
    max_short_sentences: int = 3,
) -> SegmentationMode:
    """Determine how a conversation turn should be processed for graph extraction.

    Returns one of:
        CONTEXT_ONLY   — store as context, skip extraction
        EXTRACT_WHOLE  — extract the full message as one episode
        SEGMENT_CLAIMS — run Stage B to extract individual claim spans
        SKIP           — do not ingest
    """
    if not content or not content.strip():
        return SegmentationMode.SKIP

    # Assistant messages: context-only by default unless they contain durable content
    if role.strip().lower() == "assistant":
        if is_memory_bearing_assistant_output(content):
            return SegmentationMode.EXTRACT_WHOLE
        return SegmentationMode.CONTEXT_ONLY

    # User messages: always worth extracting, question is whether to segment
    if is_short_and_coherent(content, max_short_chars, max_short_sentences):
        return SegmentationMode.EXTRACT_WHOLE

    signals = detect_claim_risk_signals(content)

    if signals.high_confidence_single_claim:
        return SegmentationMode.EXTRACT_WHOLE

    if signals.escalate:
        return SegmentationMode.SEGMENT_CLAIMS

    return SegmentationMode.EXTRACT_WHOLE


# ---------------------------------------------------------------------------
# Stage B: LLM-based claim segmenter
# ---------------------------------------------------------------------------

_SEGMENTER_PROMPT = """\
You are a memory claim extractor. Given a conversation message, identify independently \
durable factual claims — facts that should be remembered long-term.

Rules:
- Extract ONLY factual claims about people, places, events, preferences, states, or changes.
- Do NOT extract questions, requests, opinions about hypotheticals, or generic advice.
- Do NOT extract travel planning, weather discussion, or other transient conversation.
- Each claim should be a self-contained statement that makes sense without the surrounding context.
- If a claim updates or contradicts a previous fact, mark claim_type as "state_update".
- If no durable claims exist, return an empty segments array.
- Preserve the original wording as closely as possible.

Message role: {role}
Message:
{content}

Respond with ONLY a valid JSON object:
{{"segments": [{{"text": "...", "subject": "...", "claim_type": "new_fact|state_update|preference|event", "durable": true}}]}}"""


async def extract_claim_segments(
    content: str,
    role: str = "user",
    *,
    llm_client: Any = None,
    model: str | None = None,
) -> list[ClaimSegment]:
    """Stage B: use a small LLM call to extract durable claim spans.

    If no LLM client is provided, falls back to a simple heuristic extraction
    that pulls sentences containing correction markers or state-change verbs.
    """
    if llm_client is not None:
        return await _llm_extract_claims(content, role, llm_client, model)
    return _heuristic_extract_claims(content, role)


def _heuristic_extract_claims(content: str, role: str) -> list[ClaimSegment]:
    """Fallback: extract sentences that contain state-change or correction signals."""
    sentences = _SENTENCE_BOUNDARY.split(content)
    segments = []
    for i, sent in enumerate(sentences):
        sent = sent.strip()
        if not sent:
            continue
        has_correction = bool(_CORRECTION_MARKERS.search(sent))
        has_state_change = bool(_STATE_CHANGE_VERBS.search(sent))
        if has_correction or has_state_change:
            claim_type = "state_update" if has_correction else "new_fact"
            # Try to identify the subject
            subj_match = _SUBJECT_PATTERN.search(sent)
            subject = subj_match.group(1) if subj_match else ""
            start = content.find(sent)
            segments.append(ClaimSegment(
                text=sent,
                subject=subject,
                claim_type=claim_type,
                durable=True,
                char_start=start if start >= 0 else 0,
                char_end=(start + len(sent)) if start >= 0 else len(sent),
                segment_index=i,
            ))
    return segments


async def _llm_extract_claims(
    content: str,
    role: str,
    llm_client: Any,
    model: str | None,
) -> list[ClaimSegment]:
    """Use an OpenAI-compatible client to extract claims."""
    import json as _json

    prompt = _SEGMENTER_PROMPT.format(role=role, content=content)
    _model = model or os.getenv("LME_EXTRACT_MODEL", "gpt-4o-mini")

    try:
        resp = await llm_client.chat.completions.create(
            model=_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=1024,
            response_format={"type": "json_object"},
        )
        raw = resp.choices[0].message.content.strip()
        data = _json.loads(raw)
        segments = []
        for i, seg in enumerate(data.get("segments", [])):
            text = seg.get("text", "").strip()
            if not text:
                continue
            start = content.find(text)
            segments.append(ClaimSegment(
                text=text,
                subject=seg.get("subject", ""),
                claim_type=seg.get("claim_type", "new_fact"),
                durable=seg.get("durable", True),
                char_start=start if start >= 0 else 0,
                char_end=(start + len(text)) if start >= 0 else len(text),
                segment_index=i,
            ))
        return segments
    except Exception as exc:
        logger.warning("LLM claim extraction failed: %s; falling back to heuristic", exc)
        return _heuristic_extract_claims(content, role)
