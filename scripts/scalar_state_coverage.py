#!/usr/bin/env python3
"""Step 4: per-kind, per-STAGE ScalarStateView coverage matrix.

Measures FOUR stages SEPARATELY (never collapsed into one pass/fail rate) for each expected value
kind, so a drop is localized to the exact stage it happens at:

    1. assertion_emitted  -- the perceiver emitted a TypedAssertion of the expected kind+value
    2. subject_bound      -- that assertion bound to an entity (binding_pending = false), not advisory
    3. view_materialized  -- a current scalar_state View node exists for that kind
    4. fold_correct       -- that View's ss_value equals the expected value (the fold computed right)

Read-only over bolt; refuses a prod-looking URI. Run AFTER a `--keep` fixture run against the seeded
namespace. Optionally aggregate several namespaces (repeated runs) to get a per-kind yield rate that
feeds the step-5 perceiver-yield work. This instrument changes nothing; it only characterizes.
"""

from __future__ import annotations

import argparse
import sys

from neo4j import GraphDatabase

from archolith_bench.harness.menhir_scalar_state import SCALAR_FIXTURE_SETS, _value_matches
from archolith_bench.harness.scalar_bolt import assert_not_prod

STAGES = ("assertion_emitted", "subject_bound", "view_materialized", "fold_correct")


def _read_assertions(session, namespace: str) -> list[dict]:
    q = (
        "MATCH (a:TypedAssertion) WHERE a.namespace = $ns AND NOT coalesce(a.superseded, false) "
        "RETURN a.subject_display AS subject_display, a.attribute AS attribute, "
        "a.value_kind AS value_kind, a.value_json AS value, "
        "coalesce(a.binding_pending, false) AS binding_pending"
    )
    return [dict(r) for r in session.run(q, ns=namespace)]


def _read_views(session, namespace: str) -> list[dict]:
    q = (
        "MATCH (v:Entity {view_kind: 'scalar_state', group_id: $ns}) "
        "WHERE coalesce(v.view_current, true) "
        "RETURN v.ss_attribute AS ss_attribute, v.ss_kind AS ss_kind, "
        "v.ss_value AS ss_value, v.ss_display AS ss_display"
    )
    return [dict(r) for r in session.run(q, ns=namespace)]


def coverage_for_namespace(session, namespace: str, fixture: str) -> list[dict]:
    """Return one per-case stage row for every 'view' case in the fixture."""
    cases = [c for c in SCALAR_FIXTURE_SETS[fixture]() if c.outcome == "view"]
    assertions = _read_assertions(session, namespace)
    views = _read_views(session, namespace)
    rows: list[dict] = []
    for c in cases:
        # Match an assertion on (kind, value): fixture values are distinct, so this disambiguates the
        # two count cases (coins=37 vs items=12) that share a kind.
        a_match = [a for a in assertions
                   if str(a["value_kind"]) == c.expect_kind and _value_matches(c.expect_value, a["value"])]
        emitted = bool(a_match)
        bound_assertions = [a for a in a_match if not a["binding_pending"]]
        bound = bool(bound_assertions)
        # Tie the View to THIS case via the attribute(s) its BOUND assertion used -- NOT ss_kind, which
        # collides across cases (two 'count' cases, or a mis-kinded assertion landing on 'status').
        slot_attrs = {str(a["attribute"]) for a in bound_assertions}
        v_slot = [v for v in views if str(v["ss_attribute"]) in slot_attrs] if slot_attrs else []
        view_materialized = bool(v_slot)
        fold_correct = any(_value_matches(c.expect_value, v["ss_value"]) for v in v_slot)
        # Kind misclassification (extraction quality): the RIGHT value surfaced under the WRONG kind,
        # so the case reads as an assertion_emitted miss when it is really a mis-typing.
        misclassified = None
        if not emitted:
            wrong = [a for a in assertions if str(a["value_kind"]) != c.expect_kind
                     and _value_matches(c.expect_value, a["value"])]
            if wrong:
                misclassified = str(wrong[0]["value_kind"])
        stages = {"assertion_emitted": emitted, "subject_bound": bound,
                  "view_materialized": view_materialized, "fold_correct": fold_correct}
        rows.append({
            "case_id": c.case_id, "kind": c.expect_kind, "expect": c.expect_value,
            "misclassified_as": misclassified, **stages,
            "drops_at": next((s for s in STAGES if not stages[s]), None),
        })
    return rows


def _fmt(b: bool) -> str:
    return "PASS" if b else "----"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--neo4j-uri", required=True)
    ap.add_argument("--neo4j-user", default="neo4j")
    ap.add_argument("--neo4j-password", default="scalarthrowaway")
    ap.add_argument("--fixture", default="default", choices=sorted(SCALAR_FIXTURE_SETS))
    ap.add_argument("--namespace", action="append", required=True,
                    help="seeded fixture namespace; repeat to aggregate across runs")
    args = ap.parse_args()

    assert_not_prod(args.neo4j_uri)
    driver = GraphDatabase.driver(args.neo4j_uri, auth=(args.neo4j_user, args.neo4j_password))

    # per (case_id, stage) hit count across namespaces
    n = len(args.namespace)
    hits: dict[str, dict[str, int]] = {}
    order: list[tuple[str, str, object]] = []
    try:
        with driver.session(database="neo4j") as s:
            for ns in args.namespace:
                for row in coverage_for_namespace(s, ns, args.fixture):
                    cid = row["case_id"]
                    if cid not in hits:
                        hits[cid] = {st: 0 for st in STAGES}
                        order.append((cid, row["kind"], row["expect"]))
                    for st in STAGES:
                        hits[cid][st] += int(row[st])
    finally:
        driver.close()

    print(f"\n== ScalarStateView coverage matrix ({args.fixture} fixture, {n} run(s)) ==")
    print(f"   namespaces: {', '.join(args.namespace)}\n")
    if n == 1:
        hdr = f"{'case_id':22} {'kind':12} {'emitted':8} {'bound':8} {'view':8} {'fold_ok':8} drops_at"
        print(hdr); print("-" * len(hdr))
        with GraphDatabase.driver(args.neo4j_uri, auth=(args.neo4j_user, args.neo4j_password)) as d2:
            with d2.session(database="neo4j") as s:
                for row in coverage_for_namespace(s, args.namespace[0], args.fixture):
                    drop = row["drops_at"] or "(full)"
                    if row["misclassified_as"]:
                        drop += f"  [value present, mis-typed as '{row['misclassified_as']}']"
                    print(f"{row['case_id']:22} {str(row['kind']):12} "
                          f"{_fmt(row['assertion_emitted']):8} {_fmt(row['subject_bound']):8} "
                          f"{_fmt(row['view_materialized']):8} {_fmt(row['fold_correct']):8} "
                          f"{drop}")
    else:
        hdr = f"{'case_id':22} {'kind':12} " + " ".join(f"{st.split('_')[0][:7]:>8}" for st in STAGES)
        print(hdr + f"   (x/{n} runs)"); print("-" * len(hdr))
        for cid, kind, _exp in order:
            cells = " ".join(f"{hits[cid][st]:>8}" for st in STAGES)
            print(f"{cid:22} {str(kind):12} {cells}")

    # per-stage totals (how many kinds reached each stage, summed over runs / max = kinds*runs)
    kinds = len(order)
    print("\n-- per-stage totals (reached / possible) --")
    for st in STAGES:
        got = sum(hits[cid][st] for cid, _k, _e in order)
        print(f"   {st:20} {got}/{kinds * n}")
    print()


if __name__ == "__main__":
    main()
