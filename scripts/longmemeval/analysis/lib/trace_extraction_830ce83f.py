"""One-off debug trace: why did the 830ce83f session-1 episode ("Rachel moved back to the
suburbs") produce zero MENTIONS edges, when the equivalent session-0 episode about Rachel in
Chicago produced entities correctly?

Calls graphiti-core's extraction/resolution functions DIRECTLY (extract_nodes ->
resolve_extracted_nodes), not the full add_episode() write path, so nothing is written to the
graph. Read-only against the real episode content already in the LME graph.
"""
import asyncio
import os
import sys

# CORRECTNESS-CRITICAL: apply menhir's own graphiti-core monkey-patches BEFORE importing
# anything from graphiti_core's prompt/node-operations modules, exactly as
# GraphitiClient.from_settings() does in production (infrastructure/graphiti_client.py:138-146).
# Without this, graphiti-core's own known DateTime-serialization bug (Issue #606) fires and
# produces a false-positive crash that looks like a real bug but is actually just an artifact
# of not replicating production's initialization. Confirmed by the user 2026-07-15 that this
# exact bug was patched months ago (~March) -- first version of this script skipped this step.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "..", "menhir", "src"))
from menhir.infrastructure.graphiti_patches import (  # noqa: E402
    _patch_graphiti_dedupe_resolutions,
    _patch_graphiti_edge_none_fields,
    _patch_graphiti_entity_extraction,
    _patch_graphiti_entity_record_group_id,
    _patch_graphiti_node_summary_none,
    _patch_graphiti_none_replace,
    _patch_graphiti_prompt_json,
    _patch_graphiti_summarize,
)
from graphiti_core.llm_client.openai_generic_client import OpenAIGenericClient as _OAGC  # noqa: E402
from menhir.infrastructure.graphiti_patches import _patch_graphiti_openai_generic_client  # noqa: E402

_patch_graphiti_prompt_json()
_patch_graphiti_entity_extraction()
_patch_graphiti_dedupe_resolutions()
_patch_graphiti_openai_generic_client(_OAGC)
_patch_graphiti_summarize()
_patch_graphiti_none_replace()
_patch_graphiti_entity_record_group_id()
_patch_graphiti_node_summary_none()
_patch_graphiti_edge_none_fields()

from graphiti_core import Graphiti  # noqa: E402
from graphiti_core.driver.neo4j_driver import Neo4jDriver  # noqa: E402
from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig  # noqa: E402
from graphiti_core.llm_client.config import LLMConfig  # noqa: E402
from graphiti_core.nodes import EpisodicNode, EpisodeType  # noqa: E402
from graphiti_core.utils.datetime_utils import utc_now  # noqa: E402
from graphiti_core.utils.maintenance.node_operations import extract_nodes, resolve_extracted_nodes  # noqa: E402
from graphiti_core.utils.maintenance.edge_operations import extract_edges, resolve_extracted_edges  # noqa: E402
from graphiti_core.utils.bulk_utils import resolve_edge_pointers  # noqa: E402

KEY = os.environ["OPENAI_API_KEY"]
BOLT = "bolt://localhost:7689"
PW = "lmedata123"
NAMESPACE = "lme-830ce83f"


async def main():
    driver = Neo4jDriver(uri=BOLT, user="neo4j", password=PW, database="neo4j")
    embedder = OpenAIEmbedder(config=OpenAIEmbedderConfig(api_key=KEY, embedding_model="text-embedding-3-small", embedding_dim=1536))
    import os as _os
    _model = _os.environ.get("TRACE_MODEL", "gpt-4.1-nano")
    print(f"[extraction model: {_model}]\n")
    llm_client = _OAGC(config=LLMConfig(api_key=KEY, model=_model))
    g = Graphiti(uri=BOLT, user="neo4j", password=PW, graph_driver=driver, embedder=embedder, llm_client=llm_client)
    clients = g.clients

    # The actual failing episode, verbatim, as already ingested.
    target = EpisodicNode(
        name="episode-answer-trace",
        group_id=NAMESPACE,
        labels=[],
        source=EpisodeType.message,
        content="user: Miami Beach sounds fun, but I've been there before. I'm thinking of "
                "somewhere more relaxed. My friend Rachel actually just moved back to the "
                "suburbs again, so I was thinking of somewhere not too far from a major city. "
                "Any suggestions?",
        source_description="test",
        created_at=utc_now(),
        valid_at=utc_now(),
    )
    # SCHEMA_LIMIT=0 TEST (2026-07-15c): zero previous-episode context, simulating what
    # extraction sees once the real conversation has moved past graphiti-core's
    # RELEVANT_SCHEMA_LIMIT=10 lookback window and the Chicago-establishing episode has
    # fallen out of view entirely.
    previous: list[EpisodicNode] = []

    try:
        print("=== STEP 1: extract_nodes (raw LLM candidate proposal) ===")
        extracted_nodes, index_map = await extract_nodes(clients, target, previous, None, None, None)
        for n in extracted_nodes:
            print(f"  proposed: name={n.name!r} uuid={n.uuid} labels={n.labels}")
        if not extracted_nodes:
            print("  (NOTHING proposed by extraction)")

        print("\n=== STEP 2: resolve_extracted_nodes (dedup against existing graph) ===")
        nodes, uuid_map, duplicates = await resolve_extracted_nodes(
            clients, extracted_nodes, target, previous, None,
        )
        for n in nodes:
            print(f"  resolved: name={n.name!r} uuid={n.uuid}")
        print(f"  uuid_map (extracted->resolved): {uuid_map}")
        print(f"  duplicate pairs: {[(a.name, b.name) for a, b in duplicates]}")
        if not nodes:
            print("  (NOTHING survived resolution)")

        print("\n=== STEP 3: extract_edges (raw LLM fact/edge proposal) ===")
        edge_type_map = {("Entity", "Entity"): []}
        extracted_edges = await extract_edges(
            clients, target, extracted_nodes, previous, edge_type_map, group_id=NAMESPACE,
        )
        for e in extracted_edges:
            print(f"  proposed: fact={e.fact!r} source={e.source_node_uuid} target={e.target_node_uuid}")
        if not extracted_edges:
            print("  (NOTHING proposed by edge extraction)")

        print("\n=== STEP 4: resolve_extracted_edges (dedup/invalidate against existing graph) ===")
        edges = resolve_edge_pointers(extracted_edges, uuid_map)
        resolved_edges, invalidated_edges, new_edges = await resolve_extracted_edges(
            clients, edges, target, nodes, {}, edge_type_map,
        )
        print(f"  resolved_edges ({len(resolved_edges)}):")
        for e in resolved_edges:
            print(f"    fact={e.fact!r} uuid={e.uuid} valid_at={e.valid_at} invalid_at={e.invalid_at}")
        print(f"  invalidated_edges ({len(invalidated_edges)}):")
        for e in invalidated_edges:
            print(f"    fact={e.fact!r} uuid={e.uuid} invalid_at={e.invalid_at}")
        print(f"  new_edges ({len(new_edges)}):")
        for e in new_edges:
            print(f"    fact={e.fact!r} uuid={e.uuid}")
        if not resolved_edges and not new_edges:
            print("  (NOTHING survived edge resolution)")
    finally:
        await g.close()


if __name__ == "__main__":
    asyncio.run(main())
