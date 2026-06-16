#!/usr/bin/env python3
"""Run the deterministic corpus profiler over a real corpus and print the result.

Validates Phase 2 of the corpus-profile design: the combo fill's exemplar marker
can be DERIVED from the corpus's own repetition instead of hardcoded. Offline, no
LLM. Reproduce: python rung3/derive_profile.py [src-root]
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, r"C:\Users\thron\IdeaProjects\projects\archolith\archolith-context")

from analyze_corpus import load_corpus  # noqa: E402
from archolith_proxy.curator.corpus_profile import derive_corpus_profile  # noqa: E402

_DEFAULT = Path(r"C:\Users\thron\IdeaProjects\projects\forked\yawn.frontend\src")


def main(argv: list[str]) -> int:
    root = Path(argv[0]) if argv else _DEFAULT
    files, _ = load_corpus(root)
    prof = derive_corpus_profile(files)
    print(f"corpus: {root}  ({len(files)} files)")
    print(f"DERIVED exemplar_markers : {prof.exemplar_markers}")
    print(f"   -> exemplar_suffixes  : {prof.exemplar_suffixes()}")
    print("\ntop recurring component patterns (pattern, #sibling-dirs):")
    for p, n in prof.recurring_patterns[:12]:
        print(f"  {n:3d}  {p}")
    print(f"\nfoundation_files: {prof.foundation_files}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
