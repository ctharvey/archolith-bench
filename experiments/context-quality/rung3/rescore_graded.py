#!/usr/bin/env python3
"""Re-score the committed Phase B/C/D outputs with the GRADED metric.

Tests the ceiling-effect concern from the full-context review: the binary
`feature_contract` gates F1-F4 as all-or-nothing, so "all 6/6" in Phase B could be
metric saturation, not a true tie. This re-scores the EXISTING committed generated
features with `graded_feature_score` (partial credit) and prints binary vs graded
side by side. Offline, no API, no regeneration — pure re-analysis of committed
artifacts. Reproduce: python rung3/rescore_graded.py
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from feature_contract import check_feature, graded_feature_score  # noqa: E402

# (label, output dir, how to find each feature within it)
#   flat: <dir>/<arm>/src/features/<deck-ish>   (B)  or <dir>/<arm> single feature dir
#   nested: <dir>/<task>/<arm>/src/features/<feat>   (C-multi, D)
OUTPUTS = [
    ("Phase B (live, re-read OK)", "phaseB-output", "flat-feature"),
    ("Phase C (frozen, 1 task)", "phaseC-output", "flat-arm"),
    ("Phase C-multi (frozen, 3 tasks)", "phaseC-multi-output", "nested"),
    ("Phase D (combo, 3 tasks)", "phaseD-output", "nested"),
]


def _features_in(arm_dir: Path) -> list[Path]:
    """Return the feature dir(s) under an arm cwd (src/features/<x>) or the arm dir itself."""
    feats = arm_dir / "src" / "features"
    if feats.exists():
        return [d for d in sorted(feats.iterdir()) if d.is_dir()]
    # phaseB-output stores the feature dir directly (e.g. passthrough-decks/)
    if any(p.suffix in {".tsx", ".ts"} for p in arm_dir.rglob("*")):
        return [arm_dir]
    return []


def _score(feat: Path) -> tuple[str, float]:
    rep = check_feature(feat)
    kept, tot = rep.recall_score
    graded, _g = graded_feature_score(feat)
    return f"{kept}/{tot}{'*' if rep.ok else ''}", graded


def main() -> int:
    print("Graded re-score of committed Phase B/C/D outputs (ceiling-effect check)")
    print("binary = feature_contract F1-F6 (PASS/FAIL); graded = partial-credit /6.0\n")
    for label, dirname, layout in OUTPUTS:
        root = HERE / dirname
        if not root.exists():
            print(f"## {label}: MISSING ({dirname})\n")
            continue
        print(f"## {label}  ({dirname})")
        print(f"  {'arm/feature':<34}{'binary':<10}{'graded':<8}")
        print("  " + "-" * 50)
        rows = []
        if layout == "nested":
            for task in sorted(p for p in root.iterdir() if p.is_dir()):
                for arm in sorted(p for p in task.iterdir() if p.is_dir()):
                    for feat in _features_in(arm):
                        b, g = _score(feat)
                        rows.append((f"{task.name}/{arm.name}", b, g))
        else:  # flat-arm or flat-feature
            for arm in sorted(p for p in root.iterdir() if p.is_dir()):
                for feat in _features_in(arm):
                    b, g = _score(feat)
                    rows.append((arm.name, b, g))
        for name, b, g in rows:
            print(f"  {name:<34}{b:<10}{g:<8.2f}")
        if rows:
            mean_g = sum(g for _n, _b, g in rows) / len(rows)
            print(f"  {'-- mean graded':<34}{'':<10}{mean_g:<8.2f}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
