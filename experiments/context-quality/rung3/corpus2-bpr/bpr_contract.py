#!/usr/bin/env python3
"""2nd-corpus recall metric — feature contract for bulletproof-react (the GATE).

The standing hard gate on the rung-3 recall findings is a 2nd-corpus confirm: the
exemplar-aware combo (xfcombo) won briefing-only recall on ONE corpus
(`forked/yawn.frontend`, marker `*Page.tsx`). This contract ports the Phase-B recall
scorer to a SECOND, differently-structured template-convention corpus —
`forked/bulletproof-react/apps/react-vite/src` — to test whether the WIN generalizes
or was corpus-specific.

bulletproof-react's feature convention is genuinely different from yawn.frontend's
(kebab-case, React Query + a shared axios api-client, no `*Page.tsx`), so a clean
re-derivation here tests the MECHANISM, not the `Page.tsx` string. Conventions
(every real feature — comments / discussions / users — follows them):
  CORE (a hard FAIL means the convention was broken):
    C1 query   - a `features/<x>/api/get-*.ts` exporting a `use<X>` hook built with
                 `useQuery` + `queryOptions` (the data-fetch template)
    C2 client  - data flows through `@/lib/api-client` (`api.get/post/...`); NO raw
                 `fetch(`/`axios(` inside the feature
    C3 rquery  - imports from `@tanstack/react-query` (useQuery/useMutation/queryOptions)
    C4 list    - a `components/*.tsx` that consumes a `use<X>` query hook (view/data split)
  SOFT (reported, counts toward recall score, not a hard FAIL):
    C5 zod     - a `create-*.ts` mutation with a `z.object(...)` input schema + `useMutation`
    C6 types   - imports domain types from `@/types/api`

Mirrors `../feature_contract.py` (yawn.frontend) one-for-one so the two corpora are
scored the same shape: 4 CORE + 2 SOFT, binary `check_feature` + a graded variant.

Usage:
    python bpr_contract.py                 # validate vs real bpr features
    python bpr_contract.py <feature-dir>   # score one feature (Phase D use)
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))  # rung3/ for paths.py
from paths import corpus_root  # noqa: E402

CORPUS = corpus_root() / "features"
# Ground-truth conforming features (the dominant api/get + components convention).
# `auth` is intentionally excluded — it is login/register forms, not a data-list
# feature, so it does not target the browse-screen convention a new feature imitates.
GROUND_TRUTH = ["comments", "discussions", "users"]

CORE = ("C1", "C2", "C3", "C4")
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
        if p.is_file() and p.suffix in {".ts", ".tsx"}:
            out[p] = p.read_text(encoding="utf-8", errors="replace")
    return out


def check_feature(feature_dir: Path) -> FeatureReport:
    rep = FeatureReport(name=feature_dir.name)
    files = _read_all(feature_dir)
    code_text = "\n".join(files.values())
    api_files = {p: t for p, t in files.items() if "/api/" in p.as_posix() or p.parent.name == "api"}
    comp_files = {p: t for p, t in files.items()
                  if "/components/" in p.as_posix() or p.parent.name == "components"}

    # C1 query template: a get-*.ts exporting a use<X> hook via the React-Query
    # template family — useQuery+queryOptions OR the infinite variant
    # (useInfiniteQuery+infiniteQueryOptions). "queryOptions" substring covers both.
    def _is_query_template(t: str) -> bool:
        return (("useQuery" in t or "useInfiniteQuery" in t)
                and ("queryOptions" in t or "infiniteQueryOptions" in t)
                and bool(re.search(r"export\s+const\s+use[A-Z]\w*", t)))

    get_files = {p: t for p, t in api_files.items() if p.name.startswith("get-")}
    if get_files and any(_is_query_template(t) for t in get_files.values()):
        hit = next(p.name for p, t in get_files.items() if _is_query_template(t))
        rep.checks.append(Check("C1", "query hook", PASS, "annotate", hit))
    else:
        rep.checks.append(Check("C1", "query hook", FAIL, "annotate",
                                "no get-*.ts exporting a use<X> hook via useQuery+queryOptions"))

    # C2 api-client, no raw fetch/axios in the feature
    uses_client = bool(re.search(r"@/lib/api-client", code_text)) and bool(
        re.search(r"\bapi\.(get|post|put|patch|delete)\b", code_text))
    raw_http = bool(re.search(r"\bfetch\s*\(", code_text)) or bool(
        re.search(r"\baxios\b", code_text))
    if uses_client and not raw_http:
        rep.checks.append(Check("C2", "api-client", PASS, "annotate",
                                "uses @/lib/api-client, no raw fetch/axios"))
    else:
        why = []
        if not uses_client:
            why.append("no @/lib/api-client api.<verb> call")
        if raw_http:
            why.append("raw fetch()/axios in feature")
        rep.checks.append(Check("C2", "api-client", FAIL, "annotate", "; ".join(why)))

    # C3 react-query usage
    if re.search(r"@tanstack/react-query", code_text):
        rep.checks.append(Check("C3", "react-query", PASS, "annotate",
                                "imports @tanstack/react-query"))
    else:
        rep.checks.append(Check("C3", "react-query", FAIL, "annotate",
                                "no @tanstack/react-query import"))

    # C4 list/view component that consumes a use<X> query hook (view/data split)
    consumes_hook = any(re.search(r"\buse[A-Z]\w*\s*\(", t) for t in comp_files.values())
    if comp_files and consumes_hook:
        hit = next(p.name for p, t in comp_files.items() if re.search(r"\buse[A-Z]\w*\s*\(", t))
        rep.checks.append(Check("C4", "list component", PASS, "annotate", hit))
    else:
        rep.checks.append(Check("C4", "list component", FAIL, "annotate",
                                "no component consuming a use<X> query hook"))

    # C5 zod mutation input schema (soft)
    create_files = {p: t for p, t in api_files.items() if p.name.startswith("create-")}
    if create_files and any(
        ("useMutation" in t and re.search(r"z\.object\s*\(", t)) for t in create_files.values()
    ):
        rep.checks.append(Check("C5", "zod mutation", PASS, "annotate",
                                "create-*.ts with z.object schema + useMutation"))
    else:
        rep.checks.append(Check("C5", "zod mutation", FAIL, "annotate",
                                "no create-*.ts with zod input schema (soft)"))

    # C6 domain types from @/types/api (soft)
    if re.search(r"@/types/api", code_text):
        rep.checks.append(Check("C6", "api types", PASS, "annotate", "imports @/types/api"))
    else:
        rep.checks.append(Check("C6", "api types", FAIL, "annotate",
                                "no @/types/api import (soft)"))

    return rep


def graded_feature_score(feature_dir: Path) -> tuple[float, dict[str, float]]:
    """Finer-grained recall score (0.0-6.0), parallel to the yawn graded lens.

    Decomposes each anchor into half-credit sub-signals so a near-miss and a perfect
    feature do not both read "PASS". Per-anchor in [0,1]; total in [0,6].
    """
    files = _read_all(feature_dir)
    code_text = "\n".join(files.values())
    api_files = {p: t for p, t in files.items() if p.parent.name == "api" or "/api/" in p.as_posix()}
    comp_files = {p: t for p, t in files.items()
                  if p.parent.name == "components" or "/components/" in p.as_posix()}
    g: dict[str, float] = {}

    get_files = {p: t for p, t in api_files.items() if p.name.startswith("get-")}
    g["C1"] = 0.5 * bool(get_files) + 0.5 * any(
        (("useQuery" in t or "useInfiniteQuery" in t)
         and ("queryOptions" in t or "infiniteQueryOptions" in t))
        for t in get_files.values())

    g["C2"] = 0.5 * bool(re.search(r"@/lib/api-client", code_text)) \
        + 0.5 * (not (re.search(r"\bfetch\s*\(", code_text) or re.search(r"\baxios\b", code_text)))

    g["C3"] = float(bool(re.search(r"@tanstack/react-query", code_text)))

    g["C4"] = 0.5 * bool(comp_files) + 0.5 * any(
        re.search(r"\buse[A-Z]\w*\s*\(", t) for t in comp_files.values())

    create_files = {p: t for p, t in api_files.items() if p.name.startswith("create-")}
    g["C5"] = 0.5 * bool(create_files) + 0.5 * any(
        ("useMutation" in t and re.search(r"z\.object\s*\(", t)) for t in create_files.values())

    g["C6"] = float(bool(re.search(r"@/types/api", code_text)))

    return sum(g.values()), g


def _print(reports: list[FeatureReport], title: str) -> None:
    print(f"\n## {title}")
    ids = ("C1", "C2", "C3", "C4", "C5", "C6")
    hdr = f"  {'feature':<16} " + " ".join(f"{c:>4}" for c in ids) + "  core  recall"
    print(hdr)
    print("  " + "-" * (len(hdr) - 2))
    for r in reports:
        by = {c.id: c for c in r.checks}
        cells = " ".join(
            f"{('PASS' if by[i].status==PASS else 'FAIL' if by[i].status==FAIL else ' na '):>4}"
            for i in ids)
        kept, tot = r.recall_score
        print(f"  {r.name:<16} {cells}  {'OK ' if r.ok else 'FAIL':>4}  {kept}/{tot}")
    for r in reports:
        for c in r.core_fails:
            print(f"    ! {r.name} {c.id} [{c.tier}] {c.detail}")


def run_validation() -> int:
    print("bulletproof-react feature contract — validation against real features")
    print("=" * 60)
    reports = [check_feature(CORPUS / n) for n in GROUND_TRUTH if (CORPUS / n).exists()]
    if not reports:
        print(f"(no ground-truth features found under {CORPUS} — is ARCHOLITH_CORPUS set "
              f"to the bulletproof-react react-vite src?)")
        return 2
    _print(reports, "Ground-truth features (core should be OK)")
    false_pos = sum(1 for r in reports if not r.ok)
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
    ap = argparse.ArgumentParser(description="bulletproof-react feature contract")
    ap.add_argument("feature", nargs="?", type=Path)
    args = ap.parse_args(argv)
    if args.feature:
        _print([check_feature(args.feature)], f"Feature: {args.feature.name}")
        return 0
    return run_validation()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
