"""Diagnostic: dump the scalar-state graph over bolt to explain unbound perception.

Read-only. Auto-discovers the scalar-e2e namespace and prints, for the binding question:
  * user :Episodic count + bodies (is the producer shape right? content STARTS WITH 'user:')
  * resolved :Entity nodes in the namespace (did Graphiti resolve entities to bind to?)
  * :TypedAssertion rows in full (what perception extracted; binding_pending; subject)
  * :TypedAssertionHead + :ScalarConsolidationWatermark state
  * current scalar_state Views

Usage: python scripts/inspect_scalar_state_graph.py [bolt_uri] [password]
Defaults: bolt://localhost:7691  scalarthrowaway
"""

from __future__ import annotations

import sys

from neo4j import GraphDatabase

URI = sys.argv[1] if len(sys.argv) > 1 else "bolt://localhost:7691"
PW = sys.argv[2] if len(sys.argv) > 2 else "scalarthrowaway"


def main() -> None:
    driver = GraphDatabase.driver(URI, auth=("neo4j", PW))
    with driver.session(database="neo4j") as s:
        # discover the scalar-e2e namespace(s)
        ns_rows = s.run(
            "MATCH (e:Episodic) WHERE e.group_id STARTS WITH 'scalar-e2e' "
            "RETURN e.group_id AS ns, count(*) AS episodes ORDER BY episodes DESC"
        ).data()
        print(f"== namespaces ({URI}) ==")
        for r in ns_rows:
            print(f"  {r['ns']}: {r['episodes']} episodes")
        if not ns_rows:
            print("  (none found -- did the --keep run finish and preserve the namespace?)")
            # still show any global scalar nodes
            for label in ("TypedAssertion", "TypedAssertionHead", "ScalarConsolidationWatermark"):
                n = s.run(f"MATCH (n:{label}) RETURN count(n) AS c").single()["c"]
                print(f"  global {label}: {n}")
            return
        ns = ns_rows[0]["ns"]
        print(f"\n== inspecting namespace: {ns} ==")

        # 1. FOUR-CHECKPOINT bundle per episode:
        #    (a) Graphiti processed/completed (control), (b) linked NON-View KG entities (the exact
        #    binder candidate set), so "no entity" can be told apart from "never processed".
        eps = s.run(
            "MATCH (e:Episodic {group_id:$ns}) "
            "OPTIONAL MATCH (e)-[]-(n:Entity) "
            "  WHERE NOT coalesce(n.is_view,false) AND NOT coalesce(n.is_quantstate,false) "
            "        AND n.view_kind IS NULL "
            "WITH e, collect(DISTINCT {uuid:n.uuid, name:n.name}) AS linked "
            "RETURN e.uuid AS uuid, e.content AS content, "
            "       (e.content STARTS WITH 'user:') AS is_user, "
            "       toString(e.processing_completed_at) AS completed_at, "
            "       e.processing_steps_completed AS steps_done, e.processing_steps_total AS steps_total, "
            "       [x IN linked WHERE x.uuid IS NOT NULL] AS linked "
            "ORDER BY e.created_at",
            ns=ns,
        ).data()
        print(f"\n-- Episodic + Graphiti processing + linked KG entities ({len(eps)}) --")
        for e in eps:
            done = "COMPLETED" if e["completed_at"] else "NOT-COMPLETED"
            linked = e["linked"]
            names = [x["name"] for x in linked]
            print(f"  [{done} {e['steps_done']}/{e['steps_total']}] {e['content']!r}")
            print(f"       linked non-View entities: {names or '(none)'}")

        # 2. all entities (binding-target census; flag the plain KG ones)
        ents = s.run(
            "MATCH (n:Entity {group_id:$ns}) "
            "RETURN n.name AS name, n.view_kind AS view_kind, "
            "       (n.view_kind IS NULL AND NOT coalesce(n.is_view,false) "
            "        AND NOT coalesce(n.is_quantstate,false)) AS is_plain_kg "
            "ORDER BY is_plain_kg DESC, n.name",
            ns=ns,
        ).data()
        plain = [n for n in ents if n["is_plain_kg"]]
        print(f"\n-- Entity nodes ({len(ents)}; plain KG binding targets: {len(plain)}) --")
        for n in ents:
            tag = " <-- PLAIN KG (bindable)" if n["is_plain_kg"] else f" view_kind={n['view_kind']}"
            print(f"  {n['name']!r}{tag}")

        # 3. TypedAssertion rows in full
        tas = s.run(
            "MATCH (a:TypedAssertion) WHERE a.namespace=$ns OR a.group_id=$ns "
            "RETURN a.subject_uuid AS subject_uuid, a.subject_display AS subject_display, "
            "       a.attribute AS attribute, a.value_kind AS value_kind, a.value AS value, "
            "       a.evidence_tier AS tier, coalesce(a.binding_pending,false) AS pending, "
            "       coalesce(a.superseded,false) AS superseded, a.source_key AS source_key "
            "ORDER BY a.attribute",
            ns=ns,
        ).data()
        print(f"\n-- TypedAssertion ({len(tas)}) --")
        for a in tas:
            print(f"  attr={a['attribute']!r} kind={a['value_kind']} value={a['value']!r} "
                  f"pending={a['pending']} superseded={a['superseded']} tier={a['tier']}")
            print(f"       subject_uuid={a['subject_uuid']!r} subject_display={a['subject_display']!r} "
                  f"source_key={a['source_key']!r}")

        # 4. heads + watermark
        heads = s.run(
            "MATCH (h:TypedAssertionHead) WHERE h.namespace=$ns OR h.group_id=$ns RETURN count(h) AS c",
            ns=ns,
        ).single()["c"]
        wm = s.run(
            "MATCH (w:ScalarConsolidationWatermark {group_id:$ns}) "
            "RETURN w.perceiver_version AS pv, toString(w.cursor_at) AS cursor_at, "
            "       w.cursor_uuid AS cursor_uuid",
            ns=ns,
        ).data()
        print(f"\n-- TypedAssertionHead: {heads} --")
        print(f"-- ScalarConsolidationWatermark: {wm} --")

        # 5. current scalar_state Views
        views = s.run(
            "MATCH (v:Entity {view_kind:'scalar_state'}) "
            "WHERE (v.group_id=$ns) AND coalesce(v.view_current,true) "
            "RETURN v.ss_attribute AS attr, v.ss_kind AS kind, v.view_value AS value, "
            "       v.view_subject_uuid AS subject",
            ns=ns,
        ).data()
        print(f"\n-- current scalar_state Views ({len(views)}) --")
        for v in views:
            print(f"  attr={v['attr']!r} kind={v['kind']} value={v['value']!r} subject={v['subject']!r}")
    driver.close()


if __name__ == "__main__":
    main()
