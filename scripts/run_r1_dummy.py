"""Live R1 ladder against the DUMMY graph (prod clone, bolt 7687) in READ MODE.

This is the run that finally graduates (or fails) R1 on a NON-saturating corpus. Unlike
`run_r1_live.py` (which seeds a throwaway 7688 and saturates on the demo fixture), this
points menhir recall at the dummy — a full clone of the live graph — and scores against a
gold answer set MINED from that same graph (`mine_r1_gold.py`). Memory ids ARE node uuids,
so recalled uuids map straight to gold; no seed-episode grounding step.

It runs the standard R1 ladder via the shared `archolith_bench.r1.runner` scorer:
  A_current        today's fused recall (RetrievalTuningConfig() — the baseline to beat)
  E_hybrid_a{α}    attributed hybrid (enable_bm25=True), swept over hybrid_alpha
and applies the existing win gate (E must beat A on exact_string_recall AND symbol_recall
without regressing stale/scope). The graduating alpha that maximizes exact+symbol recall is
the recommended `hybrid_alpha` to set in `retrieval_tuning.py`.

=========================== SAFETY (read this) ===============================
- READ MODE: every recall is a read. No add_episode, no seeding, no writes.
- Hard-pinned to the DUMMY (bolt 7687). Refuses to run if NEO4J_URI is not the dummy. The
  dummy is a throwaway clone; prod is a different bolt host in menhir/.env and is never
  contacted by this script.
=============================================================================

Pre:  dummy up (clone of prod) on bolt 7687  — see scripts/_clone_to_dummy.py
      gold mined:  python scripts/mine_r1_gold.py
Run:  python scripts/run_r1_dummy.py [fixtures/r1_dummy_gold.json] [--k 5] [--candidate-k 50]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from time import perf_counter

REPO_ROOT = Path(__file__).resolve().parent.parent
MENHIR_DIR = Path(r"C:\Users\thron\IdeaProjects\projects\archolith\menhir")
MENHIR_FRONTIER_SRC = Path(r"C:\Users\thron\IdeaProjects\projects\archolith\menhir-frontier") / "src"
DUMMY_URI = "bolt://localhost:7687"
DUMMY_USER = "neo4j"
DUMMY_PASSWORD = "menhirdummy123"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _bootstrap_env() -> None:
    """Reuse menhir's openai config but FORCE the dummy Neo4j. Read-only; never prod."""
    from dotenv import dotenv_values

    cfg = dotenv_values(str(MENHIR_DIR / ".env"))
    for k, v in cfg.items():
        if v is not None and k not in os.environ:
            os.environ[k] = v
    os.environ["NEO4J_URI"] = DUMMY_URI
    os.environ["NEO4J_USER"] = DUMMY_USER
    os.environ["NEO4J_PASSWORD"] = DUMMY_PASSWORD
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
    # drop any ambient frontier toggles: the ladder sets tuning explicitly per condition.
    for k in list(os.environ):
        if k.startswith("MENHIR_FRONTIER_"):
            del os.environ[k]
    if os.environ["NEO4J_URI"] != DUMMY_URI:  # defense in depth
        sys.exit("refusing to run: NEO4J_URI is not the dummy (7687)")
    if not os.environ.get("OPENAI_API_KEY"):
        sys.exit("OPENAI_API_KEY not found in menhir/.env (needed for query embeddings)")
    sys.path.insert(0, str(MENHIR_FRONTIER_SRC))  # frontier src first (R0 trace + hybrid live here)


def _map_ids(uuids: list[str], gold_ids: set[str]) -> list[str]:
    """Recalled uuids ARE memory ids; keep order, dedup, restrict to graph uuids.

    We do NOT filter to gold_ids (that would hide wrong-scope/stale hits the metrics must
    see). The id space is the whole graph; the metrics only credit gold support ids but
    still penalize wrong-scope distractors that appear in top-k.
    """
    out: list[str] = []
    seen: set[str] = set()
    for u in uuids:
        if u and u not in seen:
            seen.add(u)
            out.append(u)
    return out


async def _run(fixture, k: int, candidate_k: int) -> dict:
    from menhir.config.settings import MemorySettings
    from menhir.domain.retrieval_tuning import RetrievalTuningConfig
    from menhir.infrastructure.graphiti_client import GraphitiClient
    from menhir.infrastructure.memory_graph_adapter import MemoryGraphAdapter
    from menhir.infrastructure.neo4j import Neo4jRepository
    from menhir.services.recall_service import RecallService
    from menhir.services.scoring_service import ScoringService

    from archolith_bench.progress import ProgressReporter
    from archolith_bench.r1.runner import ALPHA_SWEEP, ConditionResult, aggregate_metrics, evaluate_win_gate

    settings = MemorySettings.from_env()
    gc = GraphitiClient.from_settings(settings)
    neo4j = Neo4jRepository(uri=DUMMY_URI, database="neo4j", user=DUMMY_USER, password=DUMMY_PASSWORD)
    adapter = MemoryGraphAdapter(neo4j=neo4j)
    recall_service = RecallService(graphiti_client=gc, graph_adapter=adapter, scoring_service=ScoringService())

    gold_ids = {m.id for m in fixture.memories}

    conditions: dict[str, object] = {"A_current": RetrievalTuningConfig()}
    for alpha in ALPHA_SWEEP:
        conditions[f"E_hybrid_a{alpha:g}"] = RetrievalTuningConfig(enable_bm25=True, hybrid_alpha=alpha)

    results: dict[str, ConditionResult] = {}
    # Live heartbeat on stderr: this loop is len(conditions) x len(queries) real recalls
    # (~10 min on the dummy), so without progress it looks hung.
    progress = ProgressReporter(len(conditions) * len(fixture.queries), label="R1 recall")
    for name, tuning in conditions.items():
        ranked_by_query: dict[str, list[str]] = {}
        latencies: list[float] = []
        for q in fixture.queries:
            t0 = perf_counter()
            result = await recall_service.recall(
                q.text, limit=candidate_k, candidate_k=candidate_k,
                namespace=None, tuning=tuning, trace=True,
            )
            latencies.append((perf_counter() - t0) * 1000.0)
            ranked_by_query[q.id] = _map_ids([r.uuid for r in result.results], gold_ids)
            progress.advance(detail=name)
        metrics = aggregate_metrics(fixture, ranked_by_query, latencies, k)
        results[name] = ConditionResult(condition=name, metrics=metrics, per_query=ranked_by_query)
    progress.close()

    neo4j.close()
    if hasattr(gc, "aclose"):
        await gc.aclose()

    gate = evaluate_win_gate(results)
    return {
        "fixture": fixture.name,
        "mode": "dummy_read",
        "config": {"k": k, "candidate_k": candidate_k,
                   "n_memories": len(fixture.memories), "n_queries": len(fixture.queries)},
        "conditions": {n: {"metrics": r.metrics, "per_query": r.per_query} for n, r in results.items()},
        "win_gate": gate,
    }


def _check_dummy() -> None:
    from menhir.infrastructure.neo4j import Neo4jRepository

    try:
        neo4j = Neo4jRepository(uri=DUMMY_URI, database="neo4j", user=DUMMY_USER, password=DUMMY_PASSWORD)
        n = neo4j.execute("MATCH (n:Entity) RETURN count(n) AS c")[0]["c"]
        neo4j.close()
    except Exception as exc:  # noqa: BLE001
        print(f"error: dummy Neo4j not reachable at {DUMMY_URI}: {exc.__class__.__name__}: {exc}", file=sys.stderr)
        print("  bring it up + clone:  python scripts/_clone_to_dummy.py", file=sys.stderr)
        sys.exit(2)
    if n < 1000:
        print(f"warning: dummy has only {n} Entity nodes — is the clone populated?", file=sys.stderr)


def _print_table(artifact: dict) -> None:
    keys = ("recall_at_5", "exact_string_recall", "symbol_recall", "stale_hit_rate", "wrong_scope_injection_rate", "latency_ms")
    print(f"\n=== R1 DUMMY ladder: {artifact['fixture']} ({artifact['config']['n_queries']} queries) ===")
    print(f"{'condition':16s} " + " ".join(f"{k[:12]:>13s}" for k in keys))
    for cond, res in artifact["conditions"].items():
        m = res["metrics"]
        print(f"{cond:16s} " + " ".join(f"{m[k]:>13.3f}" for k in keys))
    gate = artifact["win_gate"]
    print(f"\n  win gate (E vs A_current): {'GRADUATES' if gate['graduates'] else 'does not graduate'}")
    if gate["graduates"]:
        print(f"    recommended: {gate['recommended_condition']} "
              f"(set hybrid_alpha={gate['recommended_hybrid_alpha']} in retrieval_tuning.py)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the R1 ladder against the dummy graph (read mode).")
    parser.add_argument("fixture", nargs="?", default=str(REPO_ROOT / "fixtures" / "r1_dummy_gold.json"))
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--candidate-k", type=int, default=50)
    parser.add_argument("--out", default="results/r1_dummy_run.json")
    args = parser.parse_args(argv)

    fixture_path = Path(args.fixture)
    if not fixture_path.exists():
        print(f"error: fixture not found: {fixture_path}\n  mine it:  python scripts/mine_r1_gold.py", file=sys.stderr)
        return 1

    _bootstrap_env()
    _check_dummy()

    from archolith_bench.r1.models import R1Fixture

    fixture = R1Fixture.from_file(fixture_path)
    if not fixture.queries:
        print("error: fixture has no queries", file=sys.stderr)
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
