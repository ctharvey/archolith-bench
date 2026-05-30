"""Corpus loader for tool-output samples used in the filter suite."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


CORPORA_DIR = Path(__file__).resolve().parent.parent.parent / "corpora"

CATEGORY_MAP: dict[str, str] = {
    "git_diff": "git_diff",
    "git_log": "git_log",
    "git_status": "git_status",
    "git_show": "git_show",
    "search": "search",
    "logs": "logs",
    "json": "json",
    "read_file": "read_file",
    "lint": "lint",
    "build": "build",
    "test": "test",
    "generic": "generic",
}

# Representative shell commands / tool names for each category so that
# filter_output routes samples through their specialised filter, not generic.
CATEGORY_FILTER_DEFAULTS: dict[str, dict[str, str]] = {
    "git_diff":   {"command": "git diff --staged"},
    "git_log":    {"command": "git log --oneline -20"},
    "git_status": {"command": "git status"},
    "git_show":   {"command": "git show HEAD"},
    "search":     {"command": "rg --heading pattern src"},
    "logs":       {"command": "", "tool": "wait_for_job"},
    "json":       {"command": "", "tool": "mcp__memory__recall_memories"},
    "read_file":  {"command": "", "tool": "read_file"},
    "lint":       {"command": "eslint src/"},
    "build":      {"command": "npm run build"},
    "test":       {"command": "npm test"},
    "generic":    {},
}

_FILENAME_PATTERN = re.compile(
    r"^(git_diff|git_log|git_status|git_show|search|logs|json|read_file|lint|build|test|generic)"
)


@dataclass
class CorpusSample:
    name: str
    category: str
    path: Path
    raw_text: str = ""


def list_corpora(corpora_dir: Path | None = None) -> list[CorpusSample]:
    """Discover all corpus samples in the corpora directory."""
    cdir = corpora_dir or CORPORA_DIR
    samples: list[CorpusSample] = []
    for p in sorted(cdir.glob("*.txt")):
        cat = _infer_category(p.stem)
        samples.append(CorpusSample(name=p.stem, category=cat, path=p))
    return samples


def load_sample(sample: CorpusSample) -> str:
    """Load the raw text for a corpus sample."""
    if not sample.raw_text:
        sample.raw_text = sample.path.read_text(encoding="utf-8")
    return sample.raw_text


def load_all_corpora(corpora_dir: Path | None = None) -> list[CorpusSample]:
    """Load all corpus samples with their text."""
    samples = list_corpora(corpora_dir)
    for s in samples:
        load_sample(s)
    return samples


def _infer_category(stem: str) -> str:
    """Infer a command category from the filename stem."""
    m = _FILENAME_PATTERN.match(stem)
    if m:
        return m.group(1)
    return "generic"