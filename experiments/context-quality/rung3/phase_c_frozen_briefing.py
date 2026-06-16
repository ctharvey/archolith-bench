#!/usr/bin/env python3
"""Rung 3 Phase C — frozen-briefing recall test (deny re-reading).

Phase B showed all arms tie because a tool-using agent RE-READS source, bypassing
the curated briefing. Phase C removes that confound: build the EXACT context each
fill strategy keeps at the budget, feed ONLY that to the model (no tools, no
filesystem), ask it to add the Decks feature, and score the output. This isolates
briefing-based recall — the variable Phase B could not.

Tests the pre-registered threat "foundation != recall-critical": topological keeps
the high-in-degree FOUNDATIONS (apiClient/models), but the files that actually show
the feature CONVENTION are the exemplar feature files (which FIFO keeps). So
topological may do WORSE on a structural recall metric.

One DeepSeek chat call per strategy (cheap). Reads UPSTREAM_API_KEY from
archolith-context/.env. Reproduce: python rung3/phase_c_frozen_briefing.py
"""
from __future__ import annotations

import json
import re
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from paths import context_root  # noqa: E402

_CTX = context_root()
sys.path.insert(0, str(_CTX))

from archolith_proxy.curator.deterministic_assembler import build_deterministic_context  # noqa: E402
from phase_a_foundation_survival import build_briefing, QUERY  # noqa: E402
from feature_contract import check_feature  # noqa: E402

BUDGET = 3000
STRATEGIES = {
    "fifo": dict(),
    "scored": dict(scored=True, query=QUERY),
    "topological": dict(topological=True),
}
OUT = HERE / "phaseC-output"

SYSTEM = (
    "You are a senior engineer adding a screen to an existing TypeScript/Astro + React app. "
    "Below is the RELEVANT CONTEXT retrieved from the codebase — it is ALL you have; you cannot "
    "open other files. Study the conventions it shows and follow them exactly.\n\n{context}"
)
USER = (
    "Add a Decks browse screen, consistent with the rest of the app. It lists decks, each showing "
    "its total market value. Create the necessary files under src/features so it fits the app's "
    "existing patterns.\n\n"
    "Output EVERY file you create. For each file, emit a line exactly of the form:\n"
    "FILE: <relative/path/from/repo/root>\n"
    "immediately followed by a fenced code block with the file's full contents. Output nothing else."
)


def _api_key() -> str:
    for line in (_CTX / ".env").read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("UPSTREAM_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("UPSTREAM_API_KEY not found in .env")


def call_deepseek(context_block: str, key: str) -> str:
    body = json.dumps({
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": SYSTEM.format(context=context_block)},
            {"role": "user", "content": USER},
        ],
        "temperature": 0.2,
        "max_tokens": 4000,
        "seed": 7,
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.deepseek.com/v1/chat/completions", data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=180) as r:
        data = json.loads(r.read())
    return data["choices"][0]["message"]["content"]


_FILE_BLOCK = re.compile(
    r"FILE:\s*(?P<path>[^\n`]+)\s*\n+```[^\n]*\n(?P<body>.*?)```", re.DOTALL)


def parse_and_write(text: str, dest_root: Path) -> list[str]:
    written: list[str] = []
    for m in _FILE_BLOCK.finditer(text):
        rel = m.group("path").strip().lstrip("/").replace("\\", "/")
        # only keep files under the decks feature for scoring cleanliness
        body = m.group("body")
        p = dest_root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")
        written.append(rel)
    return written


def _decks_dir(root: Path) -> Path | None:
    feats = root / "src" / "features"
    if not feats.exists():
        return None
    for d in feats.iterdir():
        if d.is_dir() and "deck" in d.name.lower():
            return d
    return None


def run() -> int:
    key = _api_key()
    briefing = build_briefing()
    print("Rung 3 Phase C — frozen-briefing recall (deny re-reading)")
    print(f"briefing: {len(briefing.files)} files, budget={BUDGET}\n")
    rows = []
    for strat, kw in STRATEGIES.items():
        ctx, selected = build_deterministic_context(briefing, BUDGET, **kw)
        kept = [s["path"] for s in selected]
        print(f"[{strat}] briefing kept {len(kept)} files in {len(ctx)} chars: {kept}")
        resp = call_deepseek(ctx, key)
        dest = OUT / strat
        if dest.exists():
            import shutil
            shutil.rmtree(dest)
        written = parse_and_write(resp, dest)
        ddir = _decks_dir(dest)
        if ddir is None:
            print(f"[{strat}] NO decks feature dir produced ({len(written)} files written)\n")
            rows.append((strat, kept, "n/a", "NO FEATURE"))
            continue
        rep = check_feature(ddir)
        by = {c.id: c.status for c in rep.checks}
        kr, tot = rep.recall_score
        line = " ".join(f"{i}:{('P' if by[i]=='PASS' else 'F' if by[i]=='FAIL' else '-')}"
                        for i in ("F1", "F2", "F3", "F4", "F5", "F6"))
        print(f"[{strat}] -> {ddir.name}: {line}  core={'OK' if rep.ok else 'FAIL'}  recall={kr}/{tot}\n")
        rows.append((strat, kept, f"{kr}/{tot}", "OK" if rep.ok else "FAIL"))

    print("=" * 64)
    print(f"{'strategy':<14}{'briefing-kept':<16}{'recall':<10}core")
    for strat, kept, recall, core in rows:
        print(f"{strat:<14}{len(kept) if isinstance(kept,list) else kept:<16}{recall:<10}{core}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
