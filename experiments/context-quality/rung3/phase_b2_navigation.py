#!/usr/bin/env python3
"""Rung 3 — B2: does a CODE MAP improve NAVIGATION? (controlled agentic loop)

B1 showed the map is recall-neutral under frozen briefing — but recall is the wrong
axis: a map's job is navigation (knowing WHAT to go read). This is the genuine MAP
test, done controlled (the Phase-C move applied to Phase B): instead of a live
proxy/harness where re-reads are opaque, give the model a `read_file` tool over the
corpus and COUNT the reads. Re-reading is ALLOWED (the regime where MAP matters),
but every fetch is observed.

Contrast: map-OFF the agent gets only the user task + the tool (it must grope —
guess paths, read indexes, backtrack); map-ON it also gets the `=== CODE MAP ===`
(it should fetch fewer, sharper files and reach the exemplar faster).

Navigation metrics (per run, from the observed tool calls):
  reads        — total read_file calls
  misses       — reads for a path NOT in the corpus (groping)
  hit_exemplar — did it read a real *Page.tsx exemplar? (found the template)
  reads_to_exemplar — reads before the first exemplar read (lower = sharper)

map-ON x map-OFF x 2 tasks x 3 seeds. Capped at MAX_TURNS tool rounds per run.
Metered. STOPs on 429. Reproduce: python rung3/phase_b2_navigation.py
"""
from __future__ import annotations

import json
import statistics
import sys
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from paths import context_root, corpus_root  # noqa: E402

sys.path.insert(0, str(context_root()))

from phase_c_frozen_briefing import _api_key  # noqa: E402
from phase_a_foundation_survival import build_briefing  # noqa: E402
from archolith_proxy.curator.dependency_graph import render_code_map, render_task_map  # noqa: E402

SEEDS = [7, 8, 9]
MAX_TURNS = 8
TASKS = [
    ("decks", "a Decks browse screen that lists decks, each showing its total market value"),
    ("bundles", "a Bundles browse screen that lists product bundles, each showing its discount percent"),
]
SRC = corpus_root()

_READ_TOOL = {
    "type": "function",
    "function": {
        "name": "read_file",
        "description": "Read a source file from the repository by its path relative to src/.",
        "parameters": {"type": "object",
                       "properties": {"path": {"type": "string",
                                               "description": "path relative to src/, e.g. features/sealed/SealedPage.tsx"}},
                       "required": ["path"]},
    }}
_LIST_TOOL = {
    "type": "function",
    "function": {
        "name": "list_dir",
        "description": "List the files and subdirectories directly under a directory (path relative to src/, '' for the root).",
        "parameters": {"type": "object",
                       "properties": {"path": {"type": "string",
                                               "description": "directory path relative to src/, e.g. features"}},
                       "required": ["path"]},
    }}

SYSTEM_BASE = (
    "You are a senior engineer adding a screen to an existing TypeScript/Astro + React app under src/. "
    "Explore the codebase with the read_file tool to learn its conventions, then write the new feature. "
    "Read only what you need. When you have read enough, STOP calling tools and output the new files, "
    "each as `FILE: <path>` followed by a fenced code block."
)


def _corpus() -> dict[str, str]:
    """All source files keyed by path relative to src/ (the virtual filesystem)."""
    exts = {".ts", ".tsx", ".css", ".astro", ".js", ".mjs"}
    out: dict[str, str] = {}
    for p in SRC.rglob("*"):
        if p.suffix in exts and p.is_file():
            out[str(p.relative_to(SRC)).replace("\\", "/")] = p.read_text(
                encoding="utf-8", errors="replace")
    return out


def _post(messages, key, seed, tools):
    body = json.dumps({
        "model": "deepseek-chat", "messages": messages, "tools": tools,
        "tool_choice": "auto", "temperature": 0.2, "max_tokens": 2000, "seed": seed,
    }).encode("utf-8")
    # Retry transient network errors (IncompleteRead / connection resets); a 429 is
    # NOT transient — re-raise it so the caller STOPs per protocol.
    import time
    last = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(
                "https://api.deepseek.com/v1/chat/completions", data=body,
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=180) as r:
                return json.loads(r.read())["choices"][0]["message"]
        except urllib.error.HTTPError:
            raise  # includes 429 -> caller handles
        except Exception as e:  # IncompleteRead, URLError, timeout
            last = e
            time.sleep(2 * (attempt + 1))
    raise last


def _is_exemplar(path: str) -> bool:
    return path.endswith("Page.tsx")


def _list_dir(corpus, d: str) -> str:
    d = d.strip().strip("/")
    prefix = (d + "/") if d else ""
    entries: set[str] = set()
    for p in corpus:
        if p.startswith(prefix):
            rest = p[len(prefix):]
            entries.add(rest.split("/", 1)[0] + ("/" if "/" in rest else ""))
    return "\n".join(sorted(entries)) if entries else f"(empty or not found: {d})"


def run_one(corpus, *, code_map="", with_ls=False, task_noun, key, seed) -> dict:
    """One controlled navigation run. arms:
       map-ON   : code_map in prompt, read_file only
       ls       : no map, read_file + list_dir (the fair discovery baseline)
       blind    : no map, read_file only (the floor)
    """
    sys_prompt = SYSTEM_BASE
    if code_map:
        sys_prompt += ("\n\nHere is a structural overview of the repo to orient you:\n\n" + code_map)
    tools = [_READ_TOOL] + ([_LIST_TOOL] if with_ls else [])
    messages = [{"role": "system", "content": sys_prompt},
                {"role": "user", "content": f"Add {task_noun}, consistent with the app's patterns."}]
    reads: list[str] = []
    lists = 0
    misses = 0
    reads_to_exemplar = None
    for _turn in range(MAX_TURNS):
        m = _post(messages, key, seed, tools)
        tcs = m.get("tool_calls")
        if not tcs:
            break
        messages.append({"role": "assistant", "content": m.get("content") or "",
                         "tool_calls": tcs})
        for tc in tcs:
            fn = tc["function"]["name"]
            try:
                path = json.loads(tc["function"]["arguments"]).get("path", "").lstrip("/")
            except Exception:
                path = ""
            if fn == "list_dir":
                lists += 1
                result = _list_dir(corpus, path)
            else:
                # Conservative: accept a leading src/ prefix (a miss = genuinely wrong file).
                content = corpus.get(path)
                if content is None and path.startswith("src/"):
                    content = corpus.get(path[len("src/"):])
                    if content is not None:
                        path = path[len("src/"):]
                if content is None:
                    misses += 1
                    result = f"ERROR: {path} not found"
                else:
                    reads.append(path)
                    if _is_exemplar(path) and reads_to_exemplar is None:
                        reads_to_exemplar = len(reads)
                    result = content[:1500]
            messages.append({"role": "tool", "tool_call_id": tc["id"], "content": result})
    return {
        "reads": len(reads), "lists": lists, "misses": misses,
        "hit_exemplar": reads_to_exemplar is not None,
        "reads_to_exemplar": reads_to_exemplar if reads_to_exemplar is not None else MAX_TURNS,
        "read_paths": reads,
    }


def run() -> int:
    key = _api_key()
    corpus = _corpus()
    briefing_files = build_briefing().files
    code_map = render_code_map(briefing_files)
    # ARM_SPECS: (label, map-kind, with_ls) — map-kind: ""|"indeg"|"task"
    ARM_SPECS = [("map", "indeg", False), ("map-task", "task", False),
                 ("ls", "", True), ("blind", "", False)]
    print(f"B2 navigation — corpus {len(corpus)} files, indeg-map {len(code_map)//4} tok, "
          f"seeds={SEEDS}, tasks={[t[0] for t in TASKS]}, MAX_TURNS={MAX_TURNS}")
    print("arms: map (in-degree) / map-task (relevance-ranked) / ls (fair baseline) / blind (floor)")
    print(f"{len(ARM_SPECS)*len(TASKS)*len(SEEDS)} runs\n")
    agg: dict[str, list[dict]] = {a[0]: [] for a in ARM_SPECS}
    try:
        for seed in SEEDS:
            for tkey, noun in TASKS:
                task_map = render_task_map(briefing_files, noun, exemplar_suffixes=("Page.tsx",))
                for label, kind, ls in ARM_SPECS:
                    cm = {"indeg": code_map, "task": task_map, "": ""}[kind]
                    r = run_one(corpus, code_map=cm, with_ls=ls, task_noun=noun, key=key, seed=seed)
                    agg[label].append(r)
                    print(f"  seed{seed} {tkey:<8} {label:<9} "
                          f"reads={r['reads']} lists={r['lists']} miss={r['misses']} "
                          f"exemplar@{r['reads_to_exemplar'] if r['hit_exemplar'] else '-'}")
    except urllib.error.HTTPError as e:
        if e.code == 429:
            print("\n!! 429 RATE LIMIT — STOPPING per protocol. Partial; rerun later.")
            return 2
        raise

    print("\n" + "=" * 66)
    print(f"{'arm':<8}{'reads':<8}{'lists':<8}{'misses':<8}{'exemplar%':<11}{'reads->exmpl':<12}")
    print("-" * 66)
    for label, _kind, _ls in ARM_SPECS:
        rs = agg[label]
        print(f"{label:<9}{statistics.mean(r['reads'] for r in rs):<8.1f}"
              f"{statistics.mean(r['lists'] for r in rs):<8.1f}"
              f"{statistics.mean(r['misses'] for r in rs):<8.1f}"
              f"{100*sum(r['hit_exemplar'] for r in rs)/len(rs):<11.0f}"
              f"{statistics.mean(r['reads_to_exemplar'] for r in rs):<12.1f}")
    print("\nsample map-task reads (seed7 decks):", agg["map-task"][0]["read_paths"][:8])
    print("(lower misses/reads->exemplar = sharper; lists = discovery round-trips the map saves)")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
