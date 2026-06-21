"""Continuity tracking for multi-turn sessions: repeat file reads, diagnostics, and decision retention."""

from __future__ import annotations

import re

from ..core.metrics import ContinuityMetrics

_FILE_PATH_RE = re.compile(
    r"""
    (?:[A-Z]:\\[^\s`'"]+)
    |(?:(?:\.{1,2}|[\w.-]+)[\\/][^\s`'"]+)
    |(?:/[\w.\-]+(?:/[\w.\-]+)+)
    |(?<!\S)\.[A-Za-z0-9_.-]+
    |(?<!\S)(?:README|Makefile|Dockerfile|LICENSE|AGENTS\.md|pyproject\.toml|package\.json)(?=$|[\s,.;:)\]}])
    """,
    re.IGNORECASE | re.VERBOSE,
)
_COMMAND_RE = re.compile(r'(?:npm|pip|python|git|cargo|go|docker|kubectl|make)\s+\S+', re.IGNORECASE)

_REREAD_PHRASES = re.compile(
    r"(?:let me (?:re-?read|read|open|check|look at|view|cat|see) "
    r"|i (?:need to |should )?(?:re-?read|read|open|check|look at|view) "
    r"|can you (?:re-?read|read|open|show|print|display) "
    r"|show me (?:the |that |those )?(?:file|content|output|result)s?)",
    re.IGNORECASE,
)


def _extract_file_paths(response: str) -> set[str]:
    """Extract POSIX, Windows, relative, dotfile, and common no-extension paths."""
    paths = set()
    for match in _FILE_PATH_RE.finditer(response):
        path = match.group(0).rstrip(".,;)]}")
        if path:
            paths.add(path)
    return paths


class ContinuityTracker:
    """Track re-mentions of file paths and commands across a scenario run.

    Scans each arm response for file paths / commands first seen in earlier
    turns.  Records repeat_file_reads and repeat_diagnostics.

    decision_retention is derived from final-turn fact probes: for each
    expected keyword, did the arm recall it at least as well as the direct
    baseline?  A decision is "retained" if keyword recall is not degraded.

    verification_continuity is derived from whether the last-turn response
    refers to a previously stated conclusion, plan, or next step (heuristic:
    the last user message is about wrapping up / verifying; the response
    should reference prior work rather than starting from scratch).
    """

    def __init__(self) -> None:
        self._seen_files: dict[str, int] = {}
        self._seen_commands: dict[str, int] = {}
        self._repeat_file_reads: int = 0
        self._repeat_diagnostics: int = 0
        self._decision_retained: int = 0
        self._decision_total: int = 0
        self._verification_continued: int = 0
        self._verification_total: int = 0

    def observe_turn(self, turn: int, response: str) -> dict:
        """Scan a response, update internal state, and return per-turn stats."""
        files_in_response = _extract_file_paths(response)
        commands_in_response = set(_COMMAND_RE.findall(response))

        repeat_files = 0
        new_files = 0
        for f in files_in_response:
            if f in self._seen_files:
                repeat_files += 1
                self._repeat_file_reads += 1
            else:
                new_files += 1
                self._seen_files[f] = turn

        repeat_cmds = 0
        new_cmds = 0
        for c in commands_in_response:
            if c in self._seen_commands:
                repeat_cmds += 1
                self._repeat_diagnostics += 1
            else:
                new_cmds += 1
                self._seen_commands[c] = turn

        return {
            "turn": turn,
            "files_mentioned": len(files_in_response),
            "repeat_files": repeat_files,
            "new_files": new_files,
            "commands_mentioned": len(commands_in_response),
            "repeat_commands": repeat_cmds,
            "new_commands": new_cmds,
        }

    def record_probe_result(self, direct_recall: float, arm_recall: float) -> None:
        """Record whether a fact-probe decision was retained (arm >= direct)."""
        self._decision_total += 1
        if arm_recall >= direct_recall:
            self._decision_retained += 1

    def record_verification(self, response: str, prior_files: set[str], prior_commands: set[str]) -> None:
        """Record whether a final-turn response references prior work.

        Verification is "continued" if the response mentions at least one
        previously-seen file path or command without expressing intent to
        re-read it (which would indicate information loss).
        """
        self._verification_total += 1
        mentions_prior_file = any(f.lower() in response.lower() for f in prior_files)
        mentions_prior_cmd = any(c.lower() in response.lower() for c in prior_commands)
        wants_reread = bool(_REREAD_PHRASES.search(response))
        if (mentions_prior_file or mentions_prior_cmd) and not wants_reread:
            self._verification_continued += 1

    def compute(self, final_response: str = "", known_files: set | None = None, known_commands: set | None = None) -> ContinuityMetrics:
        decision_retention = (
            self._decision_retained / self._decision_total
            if self._decision_total else 0.0
        )
        if self._verification_total == 0 and final_response and known_files is not None:
            self.record_verification(final_response, known_files, known_commands or set())
        verification_continuity = (
            self._verification_continued / self._verification_total
            if self._verification_total else 0.0
        )
        return ContinuityMetrics(
            repeat_file_reads=self._repeat_file_reads,
            repeat_diagnostics=self._repeat_diagnostics,
            decision_retention=decision_retention,
            verification_continuity=verification_continuity,
        )
