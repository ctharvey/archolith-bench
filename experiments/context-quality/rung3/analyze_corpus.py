#!/usr/bin/env python3
"""Rung 3 corpus characterization — does a real codebase have the structure the
topological-fill experiment needs? Offline, no API calls.

Runs the Layer-2 dependency extractor (archolith-context
``archolith_proxy/curator/dependency_graph.py``) over a real source tree and
reports: total size vs the assembler token budget (does it force eviction?), how
many edges the MECHANICAL extractor finds (extraction coverage = the honest
caveat), and the in-degree gradient (are there genuine high-in-degree foundations
for topological order to protect?).

Usage:
    python analyze_corpus.py <src-root> [--budget 6000] [--top 25]

Requires the archolith-context package importable (add its repo root to sys.path
or run from there). Default corpus path is the forked yawn.frontend clone.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure local modules are importable.
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from paths import context_root, corpus_root  # noqa: E402

# Make the archolith-context package importable without installing it.
_CTX_ROOT = context_root()
if _CTX_ROOT.exists():
    sys.path.insert(0, str(_CTX_ROOT))

from archolith_proxy.curator.briefing import PreFetchedFile  # noqa: E402
from archolith_proxy.curator.dependency_graph import (  # noqa: E402
    compute_indegree,
    extract_dependencies,
)

_DEFAULT_ROOT = corpus_root()
_EXTS = {".ts", ".tsx", ".js", ".jsx", ".css", ".html", ".astro", ".mjs", ".vue",
         ".svelte", ".py", ".kt", ".java", ".go", ".rs"}
_CHARS_PER_TOKEN = 4  # matches the assembler's estimate


def load_corpus(root: Path) -> tuple[list[PreFetchedFile], int]:
    files: list[PreFetchedFile] = []
    total_chars = 0
    for p in sorted(root.rglob("*")):
        if p.suffix.lower() in _EXTS and p.is_file():
            text = p.read_text(encoding="utf-8", errors="replace")
            total_chars += len(text)
            rel = str(p.relative_to(root)).replace("\\", "/")
            files.append(PreFetchedFile(
                path=rel, outline="",
                sections=[(1, text.count("\n") + 1, text)], relevance="r"))
    return files, total_chars


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Rung 3 corpus characterization")
    ap.add_argument("root", nargs="?", type=Path, default=_DEFAULT_ROOT)
    ap.add_argument("--budget", type=int, default=6000,
                    help="assembler_token_budget to compare against")
    ap.add_argument("--top", type=int, default=25, help="foundations to list")
    args = ap.parse_args(argv)

    if not args.root.exists():
        print(f"corpus root not found: {args.root}", file=sys.stderr)
        return 2

    files, total_chars = load_corpus(args.root)
    n = len(files)
    total_tok = total_chars // _CHARS_PER_TOKEN

    deps = extract_dependencies(files)
    edges = sum(len(v) for v in deps.values())
    with_edges = sum(1 for v in deps.values() if v)
    indeg = compute_indegree(files)
    depended = sum(1 for v in indeg.values() if v > 0)

    print(f"# Corpus: {args.root}")
    print(f"files                : {n}")
    print(f"total size           : {total_chars:,} chars (~{total_tok:,} tok)")
    print(f"assembler budget     : {args.budget:,} tok  "
          f"-> corpus is ~{total_tok // max(1, args.budget)}x budget "
          f"({'EVICTION FORCED' if total_tok > args.budget else 'fits, no pressure'})")
    print(f"edges extracted      : {edges}")
    print(f"files w/ outgoing edge: {with_edges}/{n} ({100 * with_edges // n}%)  "
          f"<- extraction coverage (honest caveat: rest are leaves OR missed refs)")
    print(f"files depended-upon  : {depended}/{n}")
    print()
    print(f"## Top {args.top} foundations (in-degree)")
    for path, v in sorted(indeg.items(), key=lambda kv: (-kv[1], kv[0]))[:args.top]:
        print(f"  {v:3d}  {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
