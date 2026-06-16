#!/usr/bin/env python3
"""Layer-3 output-contract checker (retroactive test).

Validates the "unit tests for LLM output" idea from
`.agent/plans/archolith-context-deterministic-layers-direction.md` against the
real Phase-5 seeded-recall artifacts. No agent runs, no model calls, offline.

The contract is DERIVED from the seed vocabulary (see PROTOCOL.md "seeded
conventions" table + `seeded/_seed/`). Each check carries a remediation tier
matching the design's cost ladder:

  auto-fix  -> corrected by regex at ZERO model cost (the common, mechanical case)
  annotate  -> folded into the next turn as a one-liner (no extra turn)
  retry     -> rare last resort (non-mechanical divergence)

Two validation questions this answers (rung 1 of the direction doc):
  1. Does the contract PASS the convention-following generated pages? (false-positive rate)
  2. Would it FLAG divergence?  (detection power -> divergent_sample.html, + auto-fix)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXPERIMENT_ROOT = HERE.parent  # experiments/context-quality
SEED_DIR = EXPERIMENT_ROOT / "seeded" / "_seed"
ARMS = ("passthrough", "curator-off", "curator-on")
GENERATED_PAGES = ("sealed", "graded", "series", "transactions", "sets", "market")

# ---------------------------------------------------------------------------
# The contract (resident convention card + machine-checkable vocabulary)
# ---------------------------------------------------------------------------

# ~40-token compressed anchor the design keeps resident to PREVENT violations.
CONVENTION_CARD = (
    "ROWS: .list-row > .row-thumb,.row-body(.row-name,.row-sub),.row-meta(metric). "
    "COLOR: var(--accent)/var(--muted); never raw hex for theme colors. "
    "DETAIL: <header class=detail-header><a class=back-btn>. "
    "DATA: import a named helper from ./api.js "
    "(sealedList,graded,series,transactions,setsList,marketBreadth,cardSearch...); "
    "never raw fetch() in a page."
)

ROW_CHILDREN = ("row-thumb", "row-body", "row-name", "row-sub", "row-meta")

# Hex literals that DUPLICATE an existing CSS variable -> violation (auto-fixable).
# A hex with no corresponding token (e.g. #ef4444 for a negative delta) is an
# accepted extension, NOT a violation. This is the false-positive guard.
TOKEN_HEX = {
    "#16a34a": "var(--accent)",
    "#4ade80": "var(--accent-light)",
    "#8a909c": "var(--muted)",
    "#0a0b0d": "var(--bg)",
    "#0f1014": "var(--bg-2)",
    "#14161b": "var(--bg-3)",
    "#e4e6ea": "var(--text)",
}

# Invented row containers we can mechanically rewrite to the canonical class.
ROW_ALIASES = ("card-row", "item-row", "list-item", "sealed-row", "data-row", "result-row")

# Named exports defined in api.js (the helper vocabulary).
API_HELPERS = {
    "setsMatrix", "marketBreadth", "cardSearch", "cardDetail", "sealedList",
    "sealedDetail", "graded", "setsList", "setDetail", "series",
    "transactions", "vsCompare",
}

# page stem -> the helper that page is expected to call.
PAGE_HELPER = {
    "sealed": "sealedList",
    "sealed-detail": "sealedDetail",
    "graded": "graded",
    "series": "series",
    "transactions": "transactions",
    "sets": "setsList",
    "set-detail": "setDetail",
    "market": "marketBreadth",
    "cards": "cardSearch",
    "card-detail": "cardDetail",
}

PASS, FAIL, NA = "PASS", "FAIL", "NA"


@dataclass
class CheckResult:
    id: str
    name: str
    status: str  # PASS | FAIL | NA
    remediation: str  # auto-fix | annotate | retry | -
    detail: str = ""


@dataclass
class PageReport:
    path: Path
    stem: str
    is_detail: bool
    is_list: bool
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def failed(self) -> list[CheckResult]:
        return [c for c in self.checks if c.status == FAIL]

    @property
    def ok(self) -> bool:
        return not self.failed


# ---------------------------------------------------------------------------
# Page classification + checks
# ---------------------------------------------------------------------------

def _class_tokens(text: str) -> set[str]:
    """All class names used in class="..." attributes."""
    tokens: set[str] = set()
    for attr in re.findall(r'class\s*=\s*"([^"]*)"', text):
        tokens.update(attr.split())
    return tokens


def classify(stem: str, text: str) -> tuple[bool, bool]:
    classes = _class_tokens(text)
    is_detail = (
        stem.endswith("-detail")
        or "detail-header" in classes
        or "back-btn" in classes
    )
    is_list = (
        "list-row" in classes
        or bool(re.search(r'id\s*=\s*"[\w-]*list"', text))
        or any(a in classes for a in ROW_ALIASES)
        or stem in {"sealed", "graded", "series", "transactions", "sets", "market", "cards"}
    )
    return is_detail, is_list


def check_page(path: Path) -> PageReport:
    text = path.read_text(encoding="utf-8")
    stem = path.stem
    is_detail, is_list = classify(stem, text)
    classes = _class_tokens(text)
    rep = PageReport(path=path, stem=stem, is_detail=is_detail, is_list=is_list)

    # C1 row-class reuse (auto-fix) -------------------------------------------
    if is_list:
        invented = sorted(a for a in ROW_ALIASES if a in classes)
        if "list-row" in classes:
            rep.checks.append(CheckResult("C1", "row-class reuse", PASS, "auto-fix",
                                          "uses .list-row"))
        elif invented:
            rep.checks.append(CheckResult("C1", "row-class reuse", FAIL, "auto-fix",
                                          f"invented row class: {', '.join(invented)}"))
        else:
            rep.checks.append(CheckResult("C1", "row-class reuse", FAIL, "auto-fix",
                                          "list page has no .list-row"))
    else:
        rep.checks.append(CheckResult("C1", "row-class reuse", NA, "-", "not a list page"))

    # C2 row children (annotate) ----------------------------------------------
    if is_list and "list-row" in classes:
        missing = [c for c in ("row-body", "row-name", "row-meta") if c not in classes]
        if missing:
            rep.checks.append(CheckResult("C2", "row children", FAIL, "annotate",
                                          f"missing: {', '.join(missing)}"))
        else:
            rep.checks.append(CheckResult("C2", "row children", PASS, "annotate",
                                          "row-body/row-name/row-meta present"))
    else:
        rep.checks.append(CheckResult("C2", "row children", NA, "-", ""))

    # C3 metric in .row-meta (annotate) ---------------------------------------
    if is_list:
        if "row-meta" in classes:
            rep.checks.append(CheckResult("C3", "metric slot", PASS, "annotate",
                                          "metric in .row-meta"))
        else:
            rep.checks.append(CheckResult("C3", "metric slot", FAIL, "annotate",
                                          "no .row-meta metric slot"))
    else:
        rep.checks.append(CheckResult("C3", "metric slot", NA, "-", ""))

    # C4 color tokens (auto-fix) ----------------------------------------------
    lowered = text.lower()
    dup = sorted({h for h in TOKEN_HEX if h in lowered})
    if dup:
        rep.checks.append(CheckResult("C4", "color tokens", FAIL, "auto-fix",
                                      "hardcoded theme hex: " + ", ".join(
                                          f"{h}->{TOKEN_HEX[h]}" for h in dup)))
    else:
        # report non-token hex as an accepted extension (NOT a failure)
        extension = sorted(set(re.findall(r"#[0-9a-f]{6}\b", lowered))
                           - set(TOKEN_HEX) - {"#ffffff"})
        note = "no duplicated theme hex"
        if extension:
            note += f" (extension hex ok: {', '.join(extension)})"
        rep.checks.append(CheckResult("C4", "color tokens", PASS, "auto-fix", note))

    # C5 detail-header / back-btn (annotate) ----------------------------------
    if is_detail:
        have = "detail-header" in classes and "back-btn" in classes
        if have:
            rep.checks.append(CheckResult("C5", "detail header", PASS, "annotate",
                                          "detail-header + back-btn"))
        else:
            miss = [c for c in ("detail-header", "back-btn") if c not in classes]
            rep.checks.append(CheckResult("C5", "detail header", FAIL, "annotate",
                                          f"missing: {', '.join(miss)}"))
    else:
        rep.checks.append(CheckResult("C5", "detail header", NA, "-", "not a detail page"))

    # C6 api helper (annotate; raw-fetch not safely auto-fixable) --------------
    raw_fetch = bool(re.search(r"\bfetch\s*\(", text)) and stem != "api"
    expected = PAGE_HELPER.get(stem)
    if raw_fetch:
        rep.checks.append(CheckResult("C6", "api helper", FAIL, "annotate",
                                      "raw fetch() in a page; use a named ./api.js helper"))
    elif expected is not None:
        if re.search(rf"\b{re.escape(expected)}\b", text):
            rep.checks.append(CheckResult("C6", "api helper", PASS, "annotate",
                                          f"calls {expected}"))
        else:
            used = sorted(h for h in API_HELPERS if re.search(rf"\b{re.escape(h)}\b", text))
            rep.checks.append(CheckResult("C6", "api helper", FAIL, "annotate",
                                          f"expected {expected}; "
                                          + (f"found {', '.join(used)}" if used
                                             else "no known helper")))
    else:
        rep.checks.append(CheckResult("C6", "api helper", NA, "-", "no expected helper for stem"))

    return rep


# ---------------------------------------------------------------------------
# Deterministic auto-fixer (zero model cost) — covers the auto-fix tier only
# ---------------------------------------------------------------------------

def autofix(text: str) -> tuple[str, list[str]]:
    applied: list[str] = []
    fixed = text

    # C4: hardcoded theme hex -> var(--token)
    for hexv, var in TOKEN_HEX.items():
        pattern = re.compile(re.escape(hexv), re.IGNORECASE)
        if pattern.search(fixed):
            fixed = pattern.sub(var, fixed)
            applied.append(f"C4 {hexv} -> {var}")

    # C1: invented row container class -> list-row (only within class="..." attrs)
    for alias in ROW_ALIASES:
        def repl(m: re.Match) -> str:
            inner = m.group(1)
            new = " ".join("list-row" if t == alias else t for t in inner.split())
            return f'class="{new}"'
        new_fixed, n = re.subn(rf'class\s*=\s*"([^"]*\b{re.escape(alias)}\b[^"]*)"',
                               repl, fixed)
        if n:
            fixed = new_fixed
            applied.append(f"C1 .{alias} -> .list-row ({n}x)")

    return fixed, applied


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def _fmt_status(s: str) -> str:
    return {PASS: "PASS", FAIL: "FAIL", NA: " na "}[s]


def print_report(title: str, reports: list[PageReport]) -> None:
    print(f"\n## {title}")
    header = f"  {'page':<16} {'C1':>4} {'C2':>4} {'C3':>4} {'C4':>4} {'C5':>4} {'C6':>4}  verdict"
    print(header)
    print("  " + "-" * (len(header) - 2))
    for rep in reports:
        by_id = {c.id: c for c in rep.checks}
        cells = " ".join(f"{_fmt_status(by_id[cid].status):>4}"
                         for cid in ("C1", "C2", "C3", "C4", "C5", "C6"))
        verdict = "OK" if rep.ok else "VIOLATION(" + ",".join(c.id for c in rep.failed) + ")"
        print(f"  {rep.path.name:<16} {cells}  {verdict}")
    for rep in reports:
        for c in rep.failed:
            print(f"    ! {rep.path.name} {c.id} [{c.remediation}] {c.detail}")


def collect(paths: list[Path]) -> list[PageReport]:
    return [check_page(p) for p in paths if p.exists()]


def run_retrotest() -> int:
    print("Layer-3 output-contract retroactive test")
    print("=" * 50)
    print("\nResident convention card (~40 tok, prevents violations):")
    print(f'  "{CONVENTION_CARD}"')

    # 0. Seed self-check: the files that DEFINE the conventions must pass.
    seed_files = sorted(SEED_DIR.glob("*.html"))
    seed_reports = collect(seed_files)
    print_report("Seed self-check (must all be OK)", seed_reports)

    # 1. The 18 generated pages across 3 arms (false-positive question).
    total_pages = 0
    total_violations = 0
    for arm in ARMS:
        arm_dir = EXPERIMENT_ROOT / "seeded" / arm
        files = [arm_dir / f"{stem}.html" for stem in GENERATED_PAGES]
        reports = collect(files)
        print_report(f"Generated arm: {arm}", reports)
        total_pages += len(reports)
        total_violations += sum(1 for r in reports if not r.ok)

    # 2. Divergence detection + auto-fix (detection-power question).
    fixture = HERE / "divergent_sample.html"
    if fixture.exists():
        before = check_page(fixture)
        print_report("Divergence fixture (must FLAG)", [before])
        fixed_text, applied = autofix(fixture.read_text(encoding="utf-8"))
        fixed_path = HERE / "divergent_sample.fixed.html"
        fixed_path.write_text(fixed_text, encoding="utf-8")
        after = check_page(fixed_path)
        print("\n## Auto-fix (zero model cost)")
        print("  applied: " + ("; ".join(applied) if applied else "(none)"))
        print_report("Divergence fixture AFTER auto-fix", [after])

    print("\n" + "=" * 50)
    print("SUMMARY")
    print(f"  seed self-check    : {sum(1 for r in seed_reports if r.ok)}/{len(seed_reports)} OK")
    print(f"  generated pages    : {total_pages - total_violations}/{total_pages} OK "
          f"({total_violations} false-positive violations)")
    seed_ok = all(r.ok for r in seed_reports)
    if not seed_ok:
        print("  RESULT: FAIL — contract rejects its own seed (contract is wrong)")
        return 1
    if total_violations:
        print("  RESULT: contract FLAGGED convention-following pages -> false positives present")
        return 1
    print("  RESULT: contract passes all convention-following pages with zero false positives")
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Layer-3 output-contract checker")
    ap.add_argument("paths", nargs="*", type=Path,
                    help="specific files to check (default: run full retro-test)")
    ap.add_argument("--json", action="store_true", help="emit JSON for given paths")
    ap.add_argument("--fix", action="store_true",
                    help="write <name>.fixed.html for given paths")
    args = ap.parse_args(argv)

    if not args.paths:
        return run_retrotest()

    reports = collect(args.paths)
    if args.json:
        out = [
            {
                "page": str(r.path),
                "is_detail": r.is_detail,
                "is_list": r.is_list,
                "ok": r.ok,
                "checks": [vars(c) for c in r.checks],
            }
            for r in reports
        ]
        print(json.dumps(out, indent=2))
    else:
        print_report("Checked files", reports)

    if args.fix:
        for r in reports:
            fixed_text, applied = autofix(r.path.read_text(encoding="utf-8"))
            dest = r.path.with_suffix(".fixed.html")
            dest.write_text(fixed_text, encoding="utf-8")
            print(f"  fixed {r.path.name} -> {dest.name}: "
                  + ("; ".join(applied) if applied else "(no auto-fixable violations)"))

    return 0 if all(r.ok for r in reports) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
