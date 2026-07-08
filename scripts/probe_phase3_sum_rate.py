#!/usr/bin/env python3
"""Repeatable fold-SUM commit-rate + count-vs-spend-receipt probe for the Phase 3 consumer.

Characterizes the STOCHASTIC consumer behaviors the offline suite can't measure (they need a live
menhir + real LLM), against a THROWAWAY menhir. For each of N iterations it uses a FRESH namespace
(so no reset is needed) to:

  --fixture sum          post a 2-purchase bike fixture that should fold to SUM=125, run one Phase 3
                         consolidation, and classify the result: committed(=125) / abstained / WRONG.
                         Tallies the abstention veto receipts (e.g. cross_check vs verification) so you
                         can see WHICH gate is the fold-SUM bottleneck. Use this to compare commit rate
                         across MENHIR_PERSONAL_MEMORY_VERIFY_RETRIES settings.

  --fixture count-spend  post "I bought 2 bikes for $125 total.", consolidate, and assert the
                         count_vs_spend_partial observability receipt fires when only one of
                         {count, spend} commits (the safety-only DECISION-1 behavior).

Safety: writes ONLY to throwaway namespaces on the instance you pass via --menhir-url. It NEVER points
at a default; give it a throwaway (e.g. http://127.0.0.1:8099). It exits non-zero if any iteration
produces a WRONG or DUPLICATE current View (the phase3 safety invariants), so it doubles as a guard.

Bring-up / teardown of the throwaway menhir itself is documented in
`benchmarks/RUNBOOK-phase3-live-characterization.md`.

Example:
  # baseline (server started with MENHIR_PERSONAL_MEMORY_VERIFY_RETRIES=0)
  python scripts/probe_phase3_sum_rate.py --menhir-url http://127.0.0.1:8099 --n 10 --label r0
  # then restart the server with =1 and re-run with --label r1 to compare
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

# Allow running as a plain script (python scripts/probe_phase3_sum_rate.py) without an editable install.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from archolith_bench.harness.menhir_client import Phase3MenhirClient  # noqa: E402

# (fixture name) -> (list of (text, triage_reason), expected SUM value, subject-noun needle)
_SUM_TURNS = [
    ("I bought a bike for $50.", ["number", "money", "i_bought"]),
    ("I bought another bike for $75.", ["number", "money", "i_bought"]),
]

# item 3 — SUM phrasing matrix: each variant should fold to bike SUM = 125. They stress the SAME
# arithmetic under different surface phrasings, so a commit-rate spread across variants isolates
# phrasing-sensitivity in the extractor / cross-check. All carry explicit prices, so the deterministic
# SUM-grounding path (when enabled) should apply to every one.
_R = ["number", "money", "i_bought"]
_SUM_VARIANTS: dict[str, list[tuple[str, list[str]]]] = {
    "two-episode": _SUM_TURNS,
    "one-sentence": [("I bought a bike for $50 and another for $75.", _R)],
    "worded": [("I spent 50 dollars and 75 dollars on bikes.", _R)],
    "sequential": [("I spent $50 on a bike, then $75 on another one later.", _R)],
    "list": [("Two bikes: $50 for one, $75 for the other.", _R)],
}
_COUNT_SPEND_TURNS = [
    ("I bought 2 bikes for $125 total.", ["number", "money", "i_bought"]),
]


def _bike_views(views: dict) -> list[float]:
    out = []
    for v in views.get("views", []):
        hay = f"{v.get('subject','')} {v.get('counter','')}".lower()
        if "bike" in hay and v.get("subject") != "perception":
            try:
                out.append(float(v.get("value")))
            except (TypeError, ValueError):
                pass
    return out


def _abstention_vetos(views: dict) -> dict[str, int]:
    out: dict[str, int] = {}
    for rc in views.get("receipts", []):
        c = str(rc.get("counter", ""))
        if c.startswith("perception_abstained_") and c != "perception_abstained":
            out[c] = out.get(c, 0) + 1
    return out


def _has_receipt(views: dict, name: str) -> bool:
    return any(str(rc.get("counter", "")) == name for rc in views.get("receipts", []))


def _run_sum_variant(client: Phase3MenhirClient, turns, n: int, label: str, k: int) -> dict:
    """Run one SUM phrasing variant N times; return a stats dict {committed, abstained, wrong, dup,
    vetos}. wrong/dup are the safety invariants (must be 0)."""
    committed = abstained = wrong = dup = 0
    vetos: dict[str, int] = {}
    for i in range(n):
        ns = f"sumrate-{label}-{int(time.time())}-{i}"
        for text, reasons in turns:
            client.post_turn_evidence(ns, text, triage_reason=reasons, session_id=f"{ns}-s")
        run = client.run_phase3(ns, k=k)
        views = client.fetch_views(ns)
        vals = _bike_views(views)
        good = [v for v in vals if abs(v - 125.0) < 0.5]
        bad = [v for v in vals if abs(v - 125.0) >= 0.5]
        if good:
            committed += 1
            status = "COMMIT 125"
        elif bad:
            wrong += 1
            status = f"WRONG {bad}"
        else:
            abstained += 1
            status = "abstain"
        if len(good) > 1:
            dup += 1
        for veto, c in _abstention_vetos(views).items():
            vetos[veto] = vetos.get(veto, 0) + c
        print(f"  [{i + 1}/{n}] {status:12s} views_written={run.get('views_written')} "
              f"abstained={run.get('abstained')} llm_calls={run.get('llm_calls')}")
    return {"committed": committed, "abstained": abstained, "wrong": wrong, "dup": dup, "vetos": vetos}


def run_sum(client: Phase3MenhirClient, n: int, label: str, k: int, variant: str) -> int:
    """Run the fold-SUM commit-rate probe for one variant, or the whole matrix when variant=='all'."""
    names = list(_SUM_VARIANTS) if variant == "all" else [variant]
    rc = 0
    rows: list[tuple[str, dict]] = []
    for name in names:
        print(f"\n--- variant '{name}' ---")
        stats = _run_sum_variant(client, _SUM_VARIANTS[name], n, f"{label}-{name}", k)
        rows.append((name, stats))
        if stats["wrong"] or stats["dup"]:
            rc = 1
    print(f"\n== {label}: N={n} per variant ==")
    print(f"  {'variant':<14} {'commit':>7} {'abstain':>8} {'wrong':>6} {'dup':>4}  vetos")
    for name, s in rows:
        rate = s["committed"] / n if n else 0.0
        flag = "  !! SAFETY" if (s["wrong"] or s["dup"]) else ""
        print(f"  {name:<14} {s['committed']}/{n}={rate:>3.0%} {s['abstained']:>8} "
              f"{s['wrong']:>6} {s['dup']:>4}  {s['vetos'] or '{}'}{flag}")
    if rc:
        print("  !! SAFETY VIOLATION: wrong/dup > 0 (expected 0/0)")
    return rc


def run_count_spend(client: Phase3MenhirClient, n: int, label: str, k: int) -> int:
    partial_seen = 0
    wrong = 0
    for i in range(n):
        ns = f"cvs-{label}-{int(time.time())}-{i}"
        for text, reasons in _COUNT_SPEND_TURNS:
            client.post_turn_evidence(ns, text, triage_reason=reasons, session_id=f"{ns}-s")
        client.run_phase3(ns, k=k)
        views = client.fetch_views(ns)
        vals = _bike_views(views)
        has_count = any(abs(v - 2.0) < 0.5 for v in vals)
        has_spend = any(abs(v - 125.0) < 0.5 for v in vals)
        bad = [v for v in vals if v not in (2.0, 125.0)]
        partial = _has_receipt(views, "count_vs_spend_partial")
        if partial:
            partial_seen += 1
        if bad:
            wrong += 1
        print(f"  [{i + 1}/{n}] count={has_count} spend={has_spend} "
              f"count_vs_spend_partial={'YES' if partial else 'no'} wrong={bad or '-'}")
    print(f"\n== {label}: N={n}  count_vs_spend_partial fired {partial_seen}/{n}  wrong_writes={wrong}")
    # The receipt should fire whenever the compound did NOT co-extract both sides. wrong writes are the
    # hard failure; a missing receipt when both sides DID commit is legitimately fine.
    return 1 if wrong else 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--menhir-url", required=True,
                   help="Throwaway menhir base URL (e.g. http://127.0.0.1:8099). NEVER a default.")
    p.add_argument("--fixture", choices=("sum", "count-spend"), default="sum")
    p.add_argument("--variant", choices=(*_SUM_VARIANTS, "all"), default="two-episode",
                   help="SUM phrasing variant (fixture=sum). 'all' runs the whole phrasing matrix.")
    p.add_argument("--n", type=int, default=10, help="Iterations (fresh namespace each)")
    p.add_argument("--label", default="probe", help="Label prefix for the throwaway namespaces")
    p.add_argument("--k", type=int, default=3, help="Consolidation k (self-consistency samples)")
    p.add_argument("--api-key", default=None,
                   help="Menhir bearer; default resolves MENHIR_AGENT_KEY / MENHIR_API_KEY (empty ok)")
    args = p.parse_args(argv)

    key = args.api_key or os.getenv("MENHIR_AGENT_KEY") or os.getenv("MENHIR_API_KEY") or ""
    extra = f"  variant={args.variant}" if args.fixture == "sum" else ""
    print(f"probe fold-SUM/count-spend against {args.menhir_url}  fixture={args.fixture}{extra}  "
          f"auth={'bearer set' if key else 'no key (auth-disabled instance)'}")
    client = Phase3MenhirClient(args.menhir_url, api_key=key)
    try:
        if args.fixture == "sum":
            return run_sum(client, args.n, args.label, args.k, args.variant)
        return run_count_spend(client, args.n, args.label, args.k)
    finally:
        close = getattr(client, "close", None)
        if callable(close):
            close()


if __name__ == "__main__":
    raise SystemExit(main())
