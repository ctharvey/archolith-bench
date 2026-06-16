"""Shared path resolution for the rung3 experiment scripts.

Replaces hardcoded absolute paths. Override via env vars:
  ARCHOLITH_CONTEXT_ROOT  -> the archolith-context repo (for sys.path / archolith_proxy imports)
  ARCHOLITH_CORPUS        -> the corpus src/ root used by the experiments
Defaults are computed relative to this file's location in the workspace.
"""
from __future__ import annotations

import os
from pathlib import Path

_HERE = Path(__file__).resolve()
# rung3 -> context-quality -> experiments -> archolith-bench -> archolith
_ARCHOLITH = _HERE.parents[4]
_PROJECTS = _HERE.parents[5]


def context_root() -> Path:
    env = os.environ.get("ARCHOLITH_CONTEXT_ROOT")
    return Path(env) if env else _ARCHOLITH / "archolith-context"


def corpus_root() -> Path:
    env = os.environ.get("ARCHOLITH_CORPUS")
    return Path(env) if env else _PROJECTS / "forked" / "yawn.frontend" / "src"
