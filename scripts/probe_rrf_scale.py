"""Bench-side research harness: confirm menhir's recall score scale live.

Question (R1 deferred-verification, "open scale question"): `search_scored` returns
graphiti RRF `node_reranker_scores`, but `scoring_service.MIN_SIMILARITY_THRESHOLD = 0.15`
+ its comment assume a COSINE scale. Code analysis said: graphiti `rrf()` uses the default
`rank_const=1` => score = sum_methods 1/(rank0 + 1), so a dual-method top hit ~= 2.0 and the
0.15 floor behaves as a RANK cut (~top 6 single / ~13 dual), not a similarity cut.

This script confirms that LIVE: it imports menhir's GraphitiClient as a library (no menhir
source change), points it at the THROWAWAY neo4j (bolt 7688, never prod), ingests a handful
of memories via gpt-4.1-nano, then logs the real node_reranker_scores distribution.

Run:  python scripts/probe_rrf_scale.py
Pre:  throwaway neo4j up (docker compose -f menhir/docker-compose.benchmark.yml up -d)
"""
from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MENHIR_DIR = REPO_ROOT.parent / "menhir"


def _bootstrap_env() -> None:
    # Load Bench's provider config (LLM/embed/reranker = openai, gpt-4.1-nano),
    # then OVERRIDE neo4j to the throwaway. Telemetry/scheduler off to avoid event-loop stalls.
    from dotenv import dotenv_values

    cfg = dotenv_values(str(REPO_ROOT / ".env"))
    for k, v in cfg.items():
        if v is not None and k not in os.environ:
            os.environ[k] = v
    # Hard overrides: throwaway neo4j only.
    os.environ["NEO4J_URI"] = "bolt://localhost:7688"
    os.environ["NEO4J_USER"] = "neo4j"
    os.environ["NEO4J_PASSWORD"] = "benchthrowaway"
    os.environ["NEO4J_DATABASE"] = "neo4j"
    # cloud openai path (no local-llama scheduler), nano extraction
    for k in ("GRAPHITI_LLM_PROVIDER", "MEMORY_GRAPHITI_PROVIDER", "LLM_CHAT_PROVIDER",
              "MEMORY_CHAT_PROVIDER", "GRAPHITI_EMBED_PROVIDER", "GRAPHITI_RERANKER_PROVIDER",
              "MEMORY_GRAPHITI_RERANKER_PROVIDER"):
        os.environ[k] = "openai"
    os.environ.setdefault("OPENAI_CHAT_MODEL", "gpt-4.1-nano")
    os.environ["OTEL_SDK_DISABLED"] = "true"
    os.environ["LANGFUSE_TRACING_ENABLED"] = "false"
    for k in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_HOST"):
        os.environ[k] = ""
    if not os.environ.get("OPENAI_API_KEY"):
        sys.exit("OPENAI_API_KEY not found in archolith-bench/.env")
    # import menhir from the main worktree's editable install
    sys.path.insert(0, str(MENHIR_DIR / "src"))


GROUP = "rrf_probe"

# Short memories that overlap on retrieval/scoring vocabulary so one query pulls many
# candidates at descending relevance -> a real RRF rank distribution.
MEMORIES = [
    "The cosine similarity floor in the recall scoring service was set to 0.15.",
    "Reciprocal rank fusion combines BM25 and cosine search results into one score.",
    "The source-aware floor exempts BM25 and file-linked candidates from the threshold.",
    "Graphiti's search_scored returns node reranker scores from RRF reranking.",
    "The hybrid retrieval path blends vector and lexical search on rank, not raw score.",
    "Recall ranks candidates by similarity, recency, prominence, and adjacency.",
    "The throwaway Neo4j for benchmarks runs on bolt port 7688, isolated from prod.",
    "A high relevance score can buy back currentness in a naive linear combiner.",
    "The willow texture patch caused a load-order issue in the modded game.",
    "Marigold seeds arrived in March while tomatoes were started indoors in February.",
]


async def main() -> None:
    from menhir.config.settings import MemorySettings
    from menhir.infrastructure.graphiti_client import GraphitiClient

    settings = MemorySettings.from_env()
    client = GraphitiClient.from_settings(settings)

    print("building indices/constraints on throwaway...")
    await client.build_indices_and_constraints()

    print(f"ingesting {len(MEMORIES)} memories via gpt-4.1-nano (inline extraction)...")
    now = datetime.now(timezone.utc)
    for i, text in enumerate(MEMORIES):
        await client.add_episode(
            name=f"probe-{i}",
            episode_body=text,
            source_description="rrf_probe",
            reference_time=now,
            group_id=GROUP,
        )
        print(f"  + ingested {i+1}/{len(MEMORIES)}")

    queries = [
        "what is the similarity floor in recall scoring",
        "how does RRF reranking combine search results",
    ]
    for q in queries:
        scored = await client.search_scored(q, num_results=50, group_ids=[GROUP])
        vals = sorted((s for _, _, s in scored), reverse=True)
        print("\n" + "=" * 72)
        print(f"QUERY: {q!r}")
        print(f"  candidates returned: {len(scored)}")
        if vals:
            print(f"  RRF score range: max={vals[0]:.4f}  min={vals[-1]:.4f}")
            print(f"  top scores: {[round(v, 4) for v in vals[:12]]}")
            below = sum(1 for v in vals if v < 0.15)
            print(f"  below the 0.15 floor: {below}/{len(vals)} candidates")
            print(f"  -> floor behaves as a RANK cut: keeps {len(vals)-below}, drops {below}")
        for uuid, name, s in sorted(scored, key=lambda x: -x[2])[:8]:
            print(f"      {s:.4f}  {name[:55]}")


if __name__ == "__main__":
    _bootstrap_env()
    asyncio.run(main())
