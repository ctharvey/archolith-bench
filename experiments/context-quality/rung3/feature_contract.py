#!/usr/bin/env python3
"""Phase-B recall metric — a feature-level output contract for the TS corpus.

Rung 3 Phase B asks: when the agent adds a NEW feature screen, does it reuse the
app's established conventions? This contract is the automated, deterministic recall
scorer (the Rung-1 idea applied to the real `forked/yawn.frontend` corpus). Unlike
the seed HTML contract (single page), a "feature" here is a FOLDER of files, so the
contract scores a directory.

Conventions derived from the real corpus (cards-v3 / set-v3 / graded-v3 / sealed /
card-index all follow them):
  CORE (a hard FAIL means the convention was broken):
    F1 page    - a `<Name>Page.tsx` with a default export
    F2 hook    - a `use<Name>Data.ts` exporting `use<Name>Data` (view/data split)
    F3 data    - data flows through `@/data/apiClient` or `@/data/repository`;
                 NO raw `fetch(` inside the feature
    F4 css     - a `*.module.css` imported as `import s from './*.module.css'`
  SOFT (reported, counts toward the recall score, not a hard contract FAIL):
    F5 ui      - imports from the `@/ui` barrel
    F6 domain  - imports from `@/domain/*` (slug/models/formatters)

Remediation tiers (Layer-3 cost ladder): these anchors are STRUCTURAL, so they are
annotate/retry, not regex auto-fix — an honest contrast with the seed contract,
where token/class violations were mechanically auto-fixable. Layer-3 auto-fix shines
for mechanical conventions; architectural structure falls to annotate/prevention.

Usage:
    python feature_contract.py                 # validate vs real features + fixture
    python feature_contract.py <feature-dir>   # score one feature (Phase B use)
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Ensure local modules are importable.
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from paths import corpus_root  # noqa: E402

CORPUS = corpus_root() / "features"
# Ground-truth conforming features (the dominant Page + hook + css convention).
# NOTE: `transactions` is intentionally excluded — it is a real structural VARIANT
# (table components consumed by pages/transactions.astro, no *Page.tsx). The
# contract correctly flags it; it is not the convention a new browse screen targets.
GROUND_TRUTH = ["cards-v3", "set-v3", "graded-v3", "graded", "sealed", "series",
                "card-index", "home"]

CORE = ("F1", "F2", "F3", "F4")
PASS, FAIL, NA = "PASS", "FAIL", "NA"


@dataclass
class Check:
    id: str
    name: str
    status: str
    tier: str
    detail: str = ""


@dataclass
class FeatureReport:
    name: str
    checks: list[Check] = field(default_factory=list)

    @property
    def core_fails(self) -> list[Check]:
        return [c for c in self.checks if c.id in CORE and c.status == FAIL]

    @property
    def ok(self) -> bool:
        return not self.core_fails

    @property
    def recall_score(self) -> tuple[int, int]:
        scored = [c for c in self.checks if c.status != NA]
        return sum(1 for c in scored if c.status == PASS), len(scored)


def _read_all(feature_dir: Path) -> dict[Path, str]:
    out: dict[Path, str] = {}
    for p in feature_dir.rglob("*"):
        if p.is_file() and p.suffix in {".ts", ".tsx", ".css"}:
            out[p] = p.read_text(encoding="utf-8", errors="replace")
    return out


def check_feature(feature_dir: Path) -> FeatureReport:
    rep = FeatureReport(name=feature_dir.name)
    files = _read_all(feature_dir)
    names = [p.name for p in files]
    all_text = "\n".join(files.values())
    code_text = "\n".join(t for p, t in files.items() if p.suffix in {".ts", ".tsx"})

    # F1 page (default export in a *Page.tsx)
    page_files = [p for p in files if p.name.endswith("Page.tsx")]
    if page_files and any("export default" in files[p] for p in page_files):
        rep.checks.append(Check("F1", "page default export", PASS, "retry",
                                page_files[0].name))
    else:
        rep.checks.append(Check("F1", "page default export", FAIL, "retry",
                                "no *Page.tsx with a default export"))

    # F2 data hook (use<Name>Data exported from a use*Data.ts)
    hook_files = [p for p in files if re.match(r"use.*Data\.ts$", p.name)]
    if hook_files and any(re.search(r"export\s+(?:default\s+)?function\s+use\w*Data"
                                    r"|export\s+const\s+use\w*Data", files[p])
                          for p in hook_files):
        rep.checks.append(Check("F2", "data hook", PASS, "annotate", hook_files[0].name))
    else:
        rep.checks.append(Check("F2", "data hook", FAIL, "annotate",
                                "no use<Name>Data hook (view/data not split)"))

    # F3 data layer, no raw fetch
    uses_layer = bool(re.search(r"@/data/(apiClient|repository)", code_text))
    raw_fetch = bool(re.search(r"\bfetch\s*\(", code_text))
    if uses_layer and not raw_fetch:
        rep.checks.append(Check("F3", "data layer", PASS, "annotate",
                                "uses @/data/apiClient|repository, no raw fetch"))
    else:
        why = []
        if not uses_layer:
            why.append("no @/data/apiClient|repository import")
        if raw_fetch:
            why.append("raw fetch() in feature")
        rep.checks.append(Check("F3", "data layer", FAIL, "annotate", "; ".join(why)))

    # F4 css module (imported)
    has_css = any(n.endswith(".module.css") for n in names)
    imports_css = bool(re.search(r"import\s+\w+\s+from\s+['\"][^'\"]*\.module\.css['\"]",
                                 code_text))
    if has_css and imports_css:
        rep.checks.append(Check("F4", "css module", PASS, "annotate",
                                "*.module.css imported"))
    else:
        rep.checks.append(Check("F4", "css module", FAIL, "annotate",
                                "no imported *.module.css (inline/global styling?)"))

    # F5 ui barrel (soft)
    if re.search(r"from\s+['\"]@/ui", code_text):
        rep.checks.append(Check("F5", "ui barrel", PASS, "annotate", "imports @/ui"))
    else:
        rep.checks.append(Check("F5", "ui barrel", FAIL, "annotate", "no @/ui import (soft)"))

    # F6 domain reuse (soft)
    if re.search(r"from\s+['\"]@/domain", code_text):
        rep.checks.append(Check("F6", "domain reuse", PASS, "annotate", "imports @/domain"))
    else:
        rep.checks.append(Check("F6", "domain reuse", FAIL, "annotate",
                                "no @/domain import (soft)"))

    return rep


def _print(reports: list[FeatureReport], title: str) -> None:
    print(f"\n## {title}")
    hdr = f"  {'feature':<16} " + " ".join(f"{c:>4}" for c in
                                           ("F1", "F2", "F3", "F4", "F5", "F6")) + "  core  recall"
    print(hdr)
    print("  " + "-" * (len(hdr) - 2))
    for r in reports:
        by = {c.id: c for c in r.checks}
        cells = " ".join(f"{('PASS' if by[i].status==PASS else 'FAIL' if by[i].status==FAIL else ' na '):>4}"
                         for i in ("F1", "F2", "F3", "F4", "F5", "F6"))
        kept, tot = r.recall_score
        print(f"  {r.name:<16} {cells}  {'OK ' if r.ok else 'FAIL':>4}  {kept}/{tot}")
    for r in reports:
        for c in r.core_fails:
            print(f"    ! {r.name} {c.id} [{c.tier}] {c.detail}")


def run_validation() -> int:
    print("Phase-B feature contract — validation against real conforming features")
    print("=" * 60)
    reports = [check_feature(CORPUS / n) for n in GROUND_TRUTH if (CORPUS / n).exists()]
    _print(reports, "Ground-truth features (core should be OK)")
    false_pos = sum(1 for r in reports if not r.ok)

    # Divergent fixture (in this script's dir).
    fixture = Path(__file__).resolve().parent / "divergent_feature"
    if fixture.exists():
        _print([check_feature(fixture)], "Divergence fixture (must FAIL core)")

    print("\n" + "=" * 60)
    n = len(reports)
    print(f"SUMMARY: {n - false_pos}/{n} ground-truth features pass the CORE contract "
          f"({false_pos} false positives)")
    avg = sum(r.recall_score[0] for r in reports)
    tot = sum(r.recall_score[1] for r in reports)
    print(f"         ground-truth mean recall: {avg}/{tot} anchors "
          f"({100 * avg // max(1, tot)}%)")
    return 1 if false_pos else 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Phase-B feature contract")
    ap.add_argument("feature", nargs="?", type=Path)
    args = ap.parse_args(argv)
    if args.feature:
        _print([check_feature(args.feature)], f"Feature: {args.feature.name}")
        return 0
    return run_validation()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
