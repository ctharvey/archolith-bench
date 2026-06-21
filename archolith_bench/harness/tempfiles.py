"""Temporary-directory helpers for external benchmark execution."""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def secure_temporary_directory() -> Iterator[Path]:
    """Create a temporary directory and restrict permissions to the current user."""
    with tempfile.TemporaryDirectory() as td:
        path = Path(td)
        try:
            os.chmod(path, 0o700)
        except OSError:
            # Windows ACLs may not honor POSIX modes; keep the best-effort tempdir.
            pass
        yield path
