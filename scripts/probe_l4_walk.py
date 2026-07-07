"""Bench-side research harness: L4 commit-6 live-graph walk for menhir's artifact port.

Executes the checklist in menhir/.agent/plans/l4-commit6-live-verification.md against a
REAL (throwaway) Neo4j — the step the remote sandbox could not run. Imports menhir's
ArtifactRepository / ArtifactService / MemoryOracleService as libraries (menhir src is
never modified). No LLM: artifacts are written via direct Cypher.

Confirms the 9 invariants materialize in the graph: Evidence is first-class, an LLM artifact
is never born trusted, promote is fail-closed (incl. agent_inference-only), supersede marks
historical + never deletes, a historical artifact can't be resurrected by re-capture, the
oracle ranks anchor>topic and never writes, and the 5 artifact indexes come online.

Run:  python scripts/probe_l4_walk.py     (throwaway neo4j up on bolt 7688)
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# L4 artifact code lives on the frontier branch -> use the frontier worktree's src,
# not the main worktree (which the venv's editable install points at).
MENHIR_SRC = Path(r"C:\Users\thron\IdeaProjects\projects\archolith\menhir-frontier") / "src"
sys.path.insert(0, str(MENHIR_SRC))

PASS = "PASS"
FAIL = "FAIL"
_results: list[tuple[str, str, str]] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    _results.append((PASS if ok else FAIL, label, detail))
    mark = "[PASS]" if ok else "[FAIL]"
    print(f"  {mark} {label}" + (f"  -- {detail}" if detail and not ok else ""))


async def main() -> None:
    from menhir.infrastructure.neo4j import Neo4jRepository
    from menhir.infrastructure.memory_graph_adapter import MemoryGraphAdapter
    from menhir.services.artifact_service import ArtifactService
    from menhir.services.memory_oracle_service import MemoryOracleService
    from menhir.domain.artifacts import ArtifactType, ArtifactSource, Evidence

    neo4j = Neo4jRepository(
        uri="bolt://localhost:7688", database="neo4j", user="neo4j", password="benchthrowaway"
    )
    adapter = MemoryGraphAdapter(neo4j=neo4j)
    svc = ArtifactService(graph_adapter=adapter)
    oracle = MemoryOracleService(graph_adapter=adapter)

    def q(cypher: str, **params):
        return neo4j.execute(cypher, params)

    # pre-clean any stale lv_ from a prior run
    q("MATCH (e:Evidence) WHERE e.artifact_id STARTS WITH 'lv_' DETACH DELETE e")
    q("MATCH (a:Entity) WHERE a.artifact_id STARTS WITH 'lv_' DETACH DELETE a")

    # ---- schema: bootstrap + the 5 artifact indexes online ----
    print("\n== schema bootstrap ==")
    adapter.bootstrap_phase_one()
    check("phase_one_schema_ready() True after bootstrap", adapter.phase_one_schema_ready())
    idx = {r.get("name") for r in q("SHOW INDEXES YIELD name, state WHERE state='ONLINE' RETURN name")}
    for name in ("entity_artifact_id_idx", "entity_is_artifact_idx", "entity_artifact_status_idx",
                 "evidence_artifact_id_idx", "evidence_uuid_idx"):
        check(f"index ONLINE: {name}", name in idx, f"have={sorted(n for n in idx if 'artifact' in n or 'evidence' in n)}")

    # ---- 6b.1 TRUSTED human failure + first-class git evidence ----
    print("\n== 6b.1 create TRUSTED human failure ==")
    adapter.create_artifact(artifact_id="lv_floor_fail", artifact_type="failure",
        summary="fixed cosine floor dropped facet candidates", source="human",
        status="trusted", evidence=[{"kind": "git", "ref": "e8da67d"}], anchors=["scoring_service.py"])
    r = q("MATCH (a:Entity {artifact_id:'lv_floor_fail'}) RETURN a.scope AS s, a.type AS t, "
          "a.artifact_type AS at, a.artifact_status AS st, a.artifact_source AS src, a.artifact_anchors AS an")[0]
    check("scope=PERSISTENT type=SEMANTIC", r["s"] == "PERSISTENT" and r["t"] == "SEMANTIC", str(dict(r)))
    check("artifact_type=failure status=trusted source=human", r["at"] == "failure" and r["st"] == "trusted" and r["src"] == "human", str(dict(r)))
    check("anchors=['scoring_service.py']", list(r["an"]) == ["scoring_service.py"], str(r["an"]))
    e = q("MATCH (:Entity {artifact_id:'lv_floor_fail'})-[:SUPPORTED_BY]->(e:Evidence) "
          "RETURN count(e) AS c, collect(e.kind+':'+e.ref) AS refs, max(e.is_structural) AS st")[0]
    check("first-class Evidence via SUPPORTED_BY: count=1 git:e8da67d is_structural", e["c"] == 1 and e["refs"] == ["git:e8da67d"] and e["st"], str(dict(e)))

    # ---- 6b.2 idempotency ----
    print("\n== 6b.2 idempotent re-emit ==")
    adapter.create_artifact(artifact_id="lv_floor_fail", artifact_type="failure",
        summary="fixed cosine floor dropped facet candidates", source="human",
        status="trusted", evidence=[{"kind": "git", "ref": "e8da67d"}], anchors=["scoring_service.py"])
    check("artifact count still 1", q("MATCH (a:Entity {artifact_id:'lv_floor_fail'}) RETURN count(a) AS c")[0]["c"] == 1)
    check("evidence count still 1 (no dup)", q("MATCH (:Entity {artifact_id:'lv_floor_fail'})-[:SUPPORTED_BY]->(e:Evidence) RETURN count(e) AS c")[0]["c"] == 1)

    # ---- 6b.3 CANDIDATE llm in review tier ----
    print("\n== 6b.3 CANDIDATE (llm) ==")
    adapter.create_artifact(artifact_id="lv_guess", artifact_type="failure",
        summary="maybe recency interacts with the floor", source="llm", status="candidate",
        evidence=[{"kind": "agent_inference", "ref": "scoring_service.py", "directness": 0.3}], anchors=["scoring_service.py"])
    r = q("MATCH (a:Entity {artifact_id:'lv_guess'}) RETURN a.scope AS s, a.artifact_status AS st")[0]
    check("scope=CANDIDATE status=candidate", r["s"] == "CANDIDATE" and r["st"] == "candidate", str(dict(r)))

    # ---- 6b.4 promote fail-closed without evidence ----
    print("\n== 6b.4 promote refused (no evidence) ==")
    adapter.create_artifact(artifact_id="lv_hunch", artifact_type="decision",
        summary="consider lowering the floor", source="human", status="candidate")
    check("promote_artifact returns False (no evidence)", adapter.promote_artifact("lv_hunch") is False)
    r = q("MATCH (a:Entity {artifact_id:'lv_hunch'}) RETURN a.scope AS s, a.artifact_status AS st")[0]
    check("still CANDIDATE/candidate", r["s"] == "CANDIDATE" and r["st"] == "candidate", str(dict(r)))

    # ---- 6b.4b promote refuses agent_inference-only ----
    print("\n== 6b.4b promote refused (agent_inference only) ==")
    check("promote_artifact('lv_guess') False", adapter.promote_artifact("lv_guess") is False)
    r = q("MATCH (a:Entity {artifact_id:'lv_guess'}) RETURN a.scope AS s, a.artifact_status AS st")[0]
    check("lv_guess still CANDIDATE/candidate", r["s"] == "CANDIDATE" and r["st"] == "candidate", str(dict(r)))

    # ---- 6b.5 promote succeeds with promotable evidence ----
    print("\n== 6b.5 promote succeeds (test evidence) ==")
    adapter.create_artifact(artifact_id="lv_cand", artifact_type="failure",
        summary="floor interacts with recency", source="llm", status="candidate",
        evidence=[{"kind": "test", "ref": "test_scoring_service::test_recency"}], anchors=["scoring_service.py"])
    check("promote_artifact('lv_cand', 0.9) True", adapter.promote_artifact("lv_cand", trusted_confidence=0.9) is True)
    r = q("MATCH (a:Entity {artifact_id:'lv_cand'}) RETURN a.scope AS s, a.artifact_status AS st, a.source_confidence AS c, a.promoted_at AS p")[0]
    check("PERSISTENT/trusted conf=0.9 promoted_at set", r["s"] == "PERSISTENT" and r["st"] == "trusted" and abs(float(r["c"]) - 0.9) < 1e-6 and r["p"] is not None, str(dict(r)))

    # ---- 6b.6 supersede marks historical, links, never deletes ----
    print("\n== 6b.6 supersede ==")
    adapter.create_artifact(artifact_id="lv_floor_fix", artifact_type="decision",
        summary="rank candidates, source-aware floor after ranking", source="human",
        status="trusted", evidence=[{"kind": "git", "ref": "e8da67d"}], anchors=["scoring_service.py"])
    check("supersede_artifact True", adapter.supersede_artifact("lv_floor_fail", "lv_floor_fix") is True)
    r = q("MATCH (old:Entity {artifact_id:'lv_floor_fail'}) RETURN old.artifact_status AS st, old.superseded_by AS by")[0]
    check("old historical + superseded_by=lv_floor_fix", r["st"] == "historical" and r["by"] == "lv_floor_fix", str(dict(r)))
    r = q("MATCH (new:Entity {artifact_id:'lv_floor_fix'})-[:SUPERSEDES]->(old:Entity {artifact_id:'lv_floor_fail'}) RETURN new.supersedes AS s")
    check("SUPERSEDES edge exists + new.supersedes set", bool(r) and r[0]["s"] == "lv_floor_fail")
    check("old NOT deleted", q("MATCH (a:Entity {artifact_id:'lv_floor_fail'}) RETURN count(a) AS c")[0]["c"] == 1)

    # ---- 6b.7 find_artifacts reads back, status intact, evidence collected ----
    print("\n== 6b.7 find_artifacts ==")
    rows = adapter.find_artifacts(tokens=["floor"], anchors=["scoring_service.py"], limit=10)
    by_id = {r.get("artifact_id"): r for r in rows}
    for aid, exp in (("lv_floor_fix", "trusted"), ("lv_floor_fail", "historical"), ("lv_cand", "trusted"), ("lv_guess", "candidate"), ("lv_hunch", "candidate")):
        got = by_id.get(aid, {})
        check(f"find returns {aid} status={exp}", got.get("status") == exp or got.get("artifact_status") == exp, f"got={got.get('status') or got.get('artifact_status')}")

    # ---- 6b.8 no resurrection by re-capture ----
    print("\n== 6b.8 historical cannot be resurrected ==")
    adapter.create_artifact(artifact_id="lv_floor_fail", artifact_type="failure",
        summary="re-asserted floor failure", source="human", status="trusted",
        evidence=[{"kind": "git", "ref": "e8da67d"}], anchors=["scoring_service.py"])
    r = q("MATCH (a:Entity {artifact_id:'lv_floor_fail'}) RETURN a.artifact_status AS st, a.scope AS s")[0]
    check("status STILL historical, scope STILL PERSISTENT (not re-trusted)", r["st"] == "historical" and r["s"] == "PERSISTENT", str(dict(r)))

    # ---- 6c.1 service capture forges nothing ----
    print("\n== 6c.1 ArtifactService.capture forges nothing ==")
    r1 = await svc.capture(artifact_id="lv_s_llm", artifact_type=ArtifactType.FAILURE, summary="x",
                           source=ArtifactSource.LLM, evidence=[Evidence(kind="git", ref="abc")])
    check("llm+evidence -> candidate (inv.4)", r1["status"] == "candidate", str(r1))
    r2 = await svc.capture(artifact_id="lv_s_hum", artifact_type=ArtifactType.FAILURE, summary="x",
                           source=ArtifactSource.HUMAN, evidence=[Evidence(kind="git", ref="abc")])
    check("human+evidence -> trusted (inv.5)", r2["status"] == "trusted", str(r2))
    r = q("MATCH (a:Entity) WHERE a.artifact_id IN ['lv_s_llm','lv_s_hum'] RETURN a.artifact_id AS id, a.artifact_status AS st, a.source_confidence AS c")
    conf = {x["id"]: (x["st"], float(x["c"])) for x in r}
    check("lv_s_llm candidate conf=0.4", conf.get("lv_s_llm") == ("candidate", 0.4), str(conf.get("lv_s_llm")))
    check("lv_s_hum trusted conf=0.9", conf.get("lv_s_hum") == ("trusted", 0.9), str(conf.get("lv_s_hum")))

    # ---- 6c.2 promote refusal reasons surface, no mutation ----
    print("\n== 6c.2 promote refusal reasons ==")
    await svc.capture(artifact_id="lv_s_noev", artifact_type=ArtifactType.DECISION, summary="x", source=ArtifactSource.HUMAN)
    p1 = await svc.promote("lv_s_noev")
    check("no-evidence promote refused", p1.get("status") == "refused" and p1.get("reason") == "no_promotable_evidence", str(p1))
    await svc.capture(artifact_id="lv_s_ai", artifact_type=ArtifactType.FAILURE, summary="x",
                      source=ArtifactSource.LLM, evidence=[Evidence(kind="agent_inference", ref="x")])
    p2 = await svc.promote("lv_s_ai")
    check("agent_inference-only promote refused", p2.get("status") == "refused" and p2.get("reason") == "no_promotable_evidence", str(p2))
    p3 = await svc.supersede("lv_s_hum", "lv_s_hum")
    check("self-supersede refused", p3.get("status") == "refused" and p3.get("reason") == "self_supersede", str(p3))
    r = q("MATCH (a:Entity) WHERE a.artifact_id IN ['lv_s_noev','lv_s_ai'] RETURN a.artifact_id AS id, a.artifact_status AS st")
    check("both still candidate (no mutation on refusal)", all(x["st"] == "candidate" for x in r), str([dict(x) for x in r]))

    # ---- 6c.3 oracle ranks anchor>topic, status intact, never writes ----
    print("\n== 6c.3 MemoryOracleService.find ==")
    hits = await oracle.find(text="tighten the similarity floor", anchors=["scoring_service.py"], limit=10)
    check("oracle returns hits", len(hits) > 0)
    if hits:
        check("top hit matched_on includes 'anchor'", "anchor" in hits[0].matched_on, str(hits[0].matched_on))
    hist = [h for h in hits if h.artifact.get("artifact_id") == "lv_floor_fail"]
    check("historical lv_floor_fail present with status intact", bool(hist) and (hist[0].artifact.get("status") == "historical" or hist[0].artifact.get("artifact_status") == "historical"))
    check("oracle has no write methods", not any(hasattr(oracle, m) for m in ("create_artifact", "promote", "supersede")))

    # ---- cleanup ----
    print("\n== cleanup ==")
    q("MATCH (e:Evidence) WHERE e.artifact_id STARTS WITH 'lv_' DETACH DELETE e")
    q("MATCH (a:Entity) WHERE a.artifact_id STARTS WITH 'lv_' DETACH DELETE a")
    left = q("MATCH (a:Entity) WHERE a.artifact_id STARTS WITH 'lv_' RETURN count(a) AS c")[0]["c"]
    check("lv_ nodes cleaned up", left == 0)

    neo4j.close()

    # ---- summary ----
    n_fail = sum(1 for s, _, _ in _results if s == FAIL)
    n_pass = sum(1 for s, _, _ in _results if s == PASS)
    print("\n" + "=" * 72)
    print(f"L4 commit-6 live walk: {n_pass} PASS, {n_fail} FAIL")
    if n_fail:
        for s, label, detail in _results:
            if s == FAIL:
                print(f"  FAIL: {label}  -- {detail}")
        sys.exit(1)
    print("ALL INVARIANTS CONFIRMED LIVE.")


if __name__ == "__main__":
    asyncio.run(main())
