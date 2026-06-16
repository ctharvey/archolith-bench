#!/usr/bin/env python3
"""One-command driver for the OFFLINE rung-3 pipeline (no API, no metered cost).

Runs the free, deterministic steps end-to-end so the whole offline arm is
reproducible from a clean checkout:
  1. analyze_corpus            — corpus characterization (size vs budget, edges, foundations)
  2. phase_a_foundation_survival — the foundation-survival mechanism test (PASS/FAIL)
  3. derive_profile            — deterministic exemplar-marker derivation
  4. rescore_graded            — graded re-score of the committed B/C/D outputs
  5. feature_contract          — recall-metric self-validation (ground truth + fixture)
  6. make_figure               — regenerate figure-cascade.png

The metered phases (phase_c_*, phase_d_combo — they call DeepSeek) are intentionally
NOT run here; invoke them individually when you want fresh generations.
Set ARCHOLITH_CORPUS / ARCHOLITH_CONTEXT_ROOT to override paths (see paths.py).
Reproduce: python rung3/run_offline.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
STEPS = [
    ("corpus characterization", ["analyze_corpus.py"]),
    ("Phase A — foundation survival", ["phase_a_foundation_survival.py"]),
    ("profiler — derive exemplar marker", ["derive_profile.py"]),
    ("graded re-score (committed B/C/D)", ["rescore_graded.py"]),
    ("recall-metric self-validation", ["feature_contract.py"]),
    ("regenerate cascade figure", ["make_figure.py"]),
]


def main() -> int:
    failures = []
    for label, argv in STEPS:
        print("\n" + "=" * 72)
        print(f"# {label}  ->  {' '.join(argv)}")
        print("=" * 72)
        rc = subprocess.run([sys.executable, *[str(HERE / a) for a in argv]],
                            cwd=HERE).returncode
        # feature_contract returns 1 if any ground-truth false positive — that is a
        # real signal, not a driver failure; only treat a crash (>=2) as a failure.
        if rc >= 2 or (rc == 1 and argv[0] != "feature_contract.py"):
            failures.append((label, rc))
    print("\n" + "=" * 72)
    if failures:
        print("OFFLINE PIPELINE: FAILURES")
        for label, rc in failures:
            print(f"  ! {label} (rc={rc})")
        return 1
    print("OFFLINE PIPELINE: all steps ran.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
