"""Live R1 ladder: seed a THROWAWAY graph, run menhir recall(trace=True), score.

This is the real R1 run the deferred-verification ladder calls for. It seeds the
fixture corpus into the throwaway Neo4j via menhir's own ingestion (nano
extraction), then runs today's fused recall (A_current) and the attributed hybrid
path swept over hybrid_alpha (E), scoring each with the shared R1 metrics + win
gate. Each recall carries the R0 trace.

=========================== SAFETY (read this) ===============================
- Hard-pinned to the THROWAWAY Neo4j (bolt 7688). It refuses to run if NEO4J_URI
  is not the throwaway. It NEVER touches prod. All writes (seeding) land on the
  throwaway only.
- Seeding calls the extraction LLM (gpt-4.1-nano) once per memory -> small cost.
=============================================================================

Pre:  throwaway neo4j up:
        docker compose -f menhir/docker-compose.benchmark.yml up -d   # bolt 7688
Run:  python scripts/run_r1_live.py [fixture.json] [--k 5] [--candidate-k 50]

Grounding caveat: retrieved graph node uuids are mapped back to fixture memory
ids by first-source episode (the memory whose ingestion first created the
entity). Entity de-dup across memories makes this approximate; it is the owed
pairing step the chain-handoff flags. Treat live numbers as a first real signal,
not a final promotion decision, until the mapping is hardened with a real fixture.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

REPO_ROOT = Path(__file__).resolve().parent.parent
MENHIR_FRONTIER_SRC = Path(r"C:\Users\thron\IdeaProjects\projects\archolith\menhir-frontier") / "src"
THROWAWAY_URI = "bolt://localhost:7688"
GROUP = "r1_bench"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _bootstrap_env() -> None:
    """Load Bench's provider config but FORCE the throwaway Neo4j. Never prod."""
    from dotenv import dotenv_values

    cfg = dotenv_values(str(REPO_ROOT / ".env"))
    for k, v in cfg.items():
        if v is not None and k not in os.environ:
            os.environ[k] = v
    # Hard overrides: throwaway neo4j only (R0/R1 writes must never hit prod).
    os.environ["NEO4J_URI"] = THROWAWAY_URI
    os.environ["NEO4J_USER"] = "neo4j"
    os.environ["NEO4J_PASSWORD"] = "benchthrowaway"
    os.environ["NEO4J_DATABASE"] = "neo4j"
    for k in ("GRAPHITI_LLM_PROVIDER", "MEMORY_GRAPHITI_PROVIDER", "LLM_CHAT_PROVIDER",
              "MEMORY_CHAT_PROVIDER", "GRAPHITI_EMBED_PROVIDER", "GRAPHITI_RERANKER_PROVIDER",
              "MEMORY_GRAPHITI_RERANKER_PROVIDER"):
        os.environ[k] = "openai"
    os.environ.setdefault("OPENAI_CHAT_MODEL", "gpt-4.1-nano")
    os.environ["OTEL_SDK_DISABLED"] = "true"
    os.environ["LANGFUSE_TRACING_ENABLED"] = "false"
    for k in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_HOST"):
        os.environ[k] = ""
    if os.environ["NEO4J_URI"] != THROWAWAY_URI:  # defense in depth
        sys.exit("refusing to run: NEO4J_URI is not the throwaway (7688)")
    if not os.environ.get("OPENAI_API_KEY"):
        sys.exit("OPENAI_API_KEY not found in archolith-bench/.env")
    # frontier src first (R0 trace lives there), then the main worktree.
    sys.path.insert(0, str(MENHIR_FRONTIER_SRC))


def _map_ids(uuids: list[str], uuid_to_id: dict[str, str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for u in uuids:
        mid = uuid_to_id.get(u)
        if mid is not None and mid not in seen:
            seen.add(mid)
            out.append(mid)
    return out


async def _run(fixture, k: int, candidate_k: int) -> dict:
    from menhir.config.settings import MemorySettings
    from menhir.domain.retrieval_tuning import RetrievalTuningConfig
    from menhir.infrastructure.graphiti_client import GraphitiClient
    from menhir.infrastructure.memory_graph_adapter import MemoryGraphAdapter
    from menhir.infrastructure.neo4j import Neo4jRepository
    from menhir.services.recall_service import RecallService
    from menhir.services.scoring_service import ScoringService

    from archolith_bench.r1.runner import ALPHA_SWEEP, ConditionResult, aggregate_metrics, evaluate_win_gate

    settings = MemorySettings.from_env()
    gc = GraphitiClient.from_settings(settings)
    neo4j = Neo4jRepository(uri=THROWAWAY_URI, database="neo4j", user="neo4j", password="benchthrowaway")
    adapter = MemoryGraphAdapter(neo4j=neo4j)
    recall_service = RecallService(graphiti_client=gc, graph_adapter=adapter, scoring_service=ScoringService())

    print("bootstrapping throwaway schema ...")
    await gc.build_indices_and_constraints()
    adapter.bootstrap_phase_one()

    # clean any prior r1_bench seed (throwaway only)
    neo4j.execute("MATCH (n) WHERE n.group_id = $g DETACH DELETE n", params={"g": GROUP})

    print(f"seeding {len(fixture.memories)} memories via gpt-4.1-nano (one extraction each) ...")
    now = datetime.now(timezone.utc)
    uuid_to_id: dict[str, str] = {}
    grounded = 0
    for i, m in enumerate(fixture.memories):
        res = await gc.add_episode(
            name=f"r1::{m.id}", episode_body=m.text, source_description="r1_bench",
            reference_time=now, group_id=GROUP,
        )
        nodes = getattr(res, "nodes", None) or []
        if nodes:
            grounded += 1
        for node in nodes:
            uuid_to_id.setdefault(node.uuid, m.id)
        print(f"  + seeded {i + 1}/{len(fixture.memories)} ({len(nodes)} entities)")
    print(f"grounding: {len(uuid_to_id)} entity uuids -> {grounded}/{len(fixture.memories)} memories produced entities")

    conditions: dict[str, object] = {"A_current": RetrievalTuningConfig()}
    for alpha in ALPHA_SWEEP:
        conditions[f"E_hybrid_a{alpha:g}"] = RetrievalTuningConfig(enable_bm25=True, hybrid_alpha=alpha)

    results: dict[str, ConditionResult] = {}
    for name, tuning in conditions.items():
        ranked_by_query: dict[str, list[str]] = {}
        latencies: list[float] = []
        for q in fixture.queries:
            t0 = perf_counter()
            # namespace=None: throwaway holds only our seed, and raw-seeded nodes
            # lack the menhir namespace property the namespace filter checks.
            result = await recall_service.recall(
                q.text, limit=candidate_k, candidate_k=candidate_k,
                namespace=None, tuning=tuning, trace=True,
            )
            latencies.append((perf_counter() - t0) * 1000.0)
            ranked_by_query[q.id] = _map_ids([r.uuid for r in result.results], uuid_to_id)
        metrics = aggregate_metrics(fixture, ranked_by_query, latencies, k)
        results[name] = ConditionResult(condition=name, metrics=metrics, per_query=ranked_by_query)
        print(f"  ran {name}")

    neo4j.close()
    await gc.aclose() if hasattr(gc, "aclose") else None

    gate = evaluate_win_gate(results)
    return {
        "fixture": fixture.name,
        "mode": "live",
        "config": {"k": k, "candidate_k": candidate_k, "group": GROUP,
                   "n_memories": len(fixture.memories), "n_queries": len(fixture.queries)},
        "conditions": {n: {"metrics": r.metrics, "per_query": r.per_query} for n, r in results.items()},
        "win_gate": gate,
    }


def _check_throwaway() -> None:
    from menhir.infrastructure.neo4j import Neo4jRepository

    try:
        neo4j = Neo4jRepository(uri=THROWAWAY_URI, database="neo4j", user="neo4j", password="benchthrowaway")
        neo4j.execute("RETURN 1 AS ok")
        neo4j.close()
    except Exception as exc:  # noqa: BLE001
        print(f"error: throwaway Neo4j not reachable at {THROWAWAY_URI}: {exc.__class__.__name__}: {exc}", file=sys.stderr)
        print("  bring it up:  docker compose -f menhir/docker-compose.benchmark.yml up -d", file=sys.stderr)
        sys.exit(2)


def _print_table(artifact: dict) -> None:
    keys = ("recall_at_5", "exact_string_recall", "symbol_recall", "stale_hit_rate", "wrong_scope_injection_rate", "latency_ms")
    print(f"\n=== R1 LIVE ladder: {artifact['fixture']} ===")
    print(f"{'condition':16s} " + " ".join(f"{k[:12]:>12s}" for k in keys))
    for cond, res in artifact["conditions"].items():
        m = res["metrics"]
        print(f"{cond:16s} " + " ".join(f"{m[k]:>12.3f}" for k in keys))
    gate = artifact["win_gate"]
    print(f"\n  win gate (E vs A_current): {'GRADUATES' if gate['graduates'] else 'does not graduate'}")
    if gate["graduates"]:
        print(f"    recommended: {gate['recommended_condition']} (hybrid_alpha={gate['recommended_hybrid_alpha']})")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the LIVE R1 ladder against the throwaway graph.")
    parser.add_argument("fixture", nargs="?", default=str(REPO_ROOT / "fixtures" / "r1_demo.json"),
                        help="R1 fixture JSON (needs queries + gold labels)")
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--candidate-k", type=int, default=50)
    parser.add_argument("--out", default="results/r1_live_run.json")
    args = parser.parse_args(argv)

    fixture_path = Path(args.fixture)
    if not fixture_path.exists():
        print(f"error: fixture not found: {fixture_path}", file=sys.stderr)
        return 1

    _bootstrap_env()
    _check_throwaway()

    from archolith_bench.r1.models import R1Fixture

    fixture = R1Fixture.from_file(fixture_path)
    if not fixture.queries:
        print("error: fixture has no queries — author queries + gold labels first", file=sys.stderr)
        return 1

    artifact = asyncio.run(_run(fixture, args.k, args.candidate_k))
    _print_table(artifact)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as handle:
        json.dump(artifact, handle, indent=2, sort_keys=True)
    print(f"\nwrote artifact: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
