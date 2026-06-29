"""Dump REAL prod menhir memories into a GITIGNORED local R1 corpus.

Why: the committed r1_demo.json is synthetic and its baseline saturates. A corpus
drawn from real memory text is the honest fixture. This script produces that
corpus LOCALLY ONLY.

=========================== SAFETY (read this) ===============================
- Output goes to fixtures/local/ which is GITIGNORED. DO NOT COMMIT prod memory
  text — this repo is on the open-source (archolith) track; committing real
  memories leaks private/operational data into git history.
- READ-ONLY. It talks to the prod menhir HTTP service over its read API using the
  MENHIR_READONLY_KEY credential (never the operator/agent write keys). It never
  connects to a Neo4j directly and never writes.
- It only produces the CORPUS (memory text + scope). The R1 gold labels
  (per-query support_ids / target_symbol / target_exact_string / stale) are NOT
  in raw memories — author them by hand on top, in the same gitignored file.
- The live R1 run re-ingests this corpus into the THROWAWAY Neo4j (bolt 7688),
  never prod. See archolith_bench/r1/retriever.py.
=============================================================================

Usage:
    python scripts/dump_prod_fixture.py [--limit 200] [--out fixtures/local/r1_prod.json]

Requires menhir/.env to contain MENHIR_BACKEND_URL and MENHIR_READONLY_KEY.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MENHIR_DIR = Path(r"C:\Users\thron\IdeaProjects\projects\archolith\menhir")
DEFAULT_OUT = REPO_ROOT / "fixtures" / "local" / "r1_prod.json"


def _bootstrap_env() -> str:
    """Load menhir/.env, FORCE the read-only key, return the backend URL."""
    from dotenv import dotenv_values

    cfg = dotenv_values(str(MENHIR_DIR / ".env"))
    for k, v in cfg.items():
        if v is not None and k not in os.environ:
            os.environ[k] = v

    backend_url = os.environ.get("MENHIR_BACKEND_URL", "").strip()
    readonly_key = os.environ.get("MENHIR_READONLY_KEY", "").strip()
    if not backend_url:
        sys.exit("MENHIR_BACKEND_URL not set (menhir/.env) — cannot reach the prod read API")
    if not readonly_key:
        sys.exit("MENHIR_READONLY_KEY not set (menhir/.env) — refusing to use a write-capable key")

    # Defense in depth: every request authenticates with the read-only key only.
    os.environ["MENHIR_API_KEY"] = readonly_key
    sys.path.insert(0, str(MENHIR_DIR / "src"))
    return backend_url


def _to_corpus_memory(row: dict) -> dict:
    """Map a menhir memory row to an R1 corpus memory (text + scope only).

    Gold labels (symbols/exact_strings/stale/support) are left for hand-authoring;
    namespace is captured as project so wrong-scope queries have something to bind.
    """
    text = (row.get("content") or row.get("summary") or row.get("name") or "").strip()
    return {
        "id": str(row.get("uuid") or row.get("id") or ""),
        "text": text,
        "project": row.get("namespace") or None,
        "_scope": row.get("scope"),
        "_type": row.get("type"),
        "symbols": [],
        "exact_strings": [],
        "stale": False,
    }


async def _dump(backend_url: str, limit: int) -> list[dict]:
    from menhir.config.settings import MemorySettings
    from menhir.core.backend_impl import BackendClient

    client = BackendClient(backend_url, settings=MemorySettings.from_env())
    try:
        rows = await client.fetch_recent_memories(limit=limit)
    finally:
        await client.aclose()
    return [_to_corpus_memory(r) for r in rows if (r.get("content") or r.get("summary") or r.get("name"))]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Dump prod menhir memories to a gitignored R1 corpus.")
    parser.add_argument("--limit", type=int, default=200, help="max memories to fetch (read-only)")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="gitignored output path (must be under fixtures/local/)")
    args = parser.parse_args(argv)

    out_path = Path(args.out)
    if "local" not in out_path.parts:
        sys.exit("refusing to write outside fixtures/local/ (the gitignored area) — prod text must not be committed")

    backend_url = _bootstrap_env()
    print(f"reading prod menhir (READ-ONLY) at {backend_url} limit={args.limit} ...")
    memories = asyncio.run(_dump(backend_url, args.limit))

    fixture = {
        "name": "r1_prod_local",
        "description": (
            "LOCAL-ONLY corpus dumped from prod menhir memories (read-only). "
            "GITIGNORED — DO NOT COMMIT. Corpus text only; add queries + gold labels "
            "(support_ids/target_symbol/target_exact_string/stale) by hand before running the ladder."
        ),
        "memories": memories,
        "queries": [],
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as handle:
        json.dump(fixture, handle, indent=2, ensure_ascii=False)
    print(f"wrote {len(memories)} memories -> {out_path}  (GITIGNORED; do not commit)")
    print("next: author queries + gold labels in that file, then run the live ladder against the throwaway graph.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
