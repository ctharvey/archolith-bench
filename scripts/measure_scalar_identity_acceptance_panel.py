#!/usr/bin/env python3
"""CLI wrapper for the offline scalar identity acceptance panel."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from archolith_bench.scalar_identity_acceptance_panel import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
