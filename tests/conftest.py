"""Pytest collection guard for menhir-coupled ladder benches.

The R3 (belief/temporal/scope) and R5 (cost-aware scheduler) ladder benches
import menhir's pure-domain modules -- e.g. ``menhir.domain.belief`` and
``menhir.domain.git_staleness`` -- to exercise the ported signal layer. ``menhir``
is a separate repository, not a dependency of archolith-bench, and it is not
installable in CI (its private ``cth-mcp-framework`` + graphiti chain cannot be
resolved there).

So: when ``menhir`` is not importable we skip those ladder modules and run the
rest of the offline bench suite. When a menhir checkout is on ``PYTHONPATH``
(local ladder runs), the modules collect and run normally -- no behavior change.
"""

from __future__ import annotations

import importlib.util

collect_ignore_glob: list[str] = []

if importlib.util.find_spec("menhir") is None:
    # r3/ and r5/ bench subpackages import menhir at module import time.
    collect_ignore_glob += ["test_r3_*.py", "test_r5_*.py"]
