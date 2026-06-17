#!/usr/bin/env python3
"""2nd-corpus Phase D — COMBO fill recall confirm on bulletproof-react (the GATE).

Ports rung-3 Phase D (`../phase_d_combo.py`) to a SECOND template-convention corpus
to test whether the exemplar-aware combo (xfcombo) recall win generalizes or was
specific to yawn.frontend. Same controlled method: build the exact context each fill
strategy keeps at a frozen budget (re-reading denied), feed ONLY that to the model,
ask it to add a new list-feature, score the output with the bulletproof-react
contract. If xfcombo >= max(pure) here too, the win generalizes across corpora.

The only corpus-specific knob is the EXEMPLAR: yawn's recall-critical template is a
`*Page.tsx`; bulletproof-react's is the `features/<x>/api/get-*.ts` query file (it
carries the React-Query + api-client + types pattern a new feature must imitate).

5 strategies x 3 tasks = 15 DeepSeek calls (deepseek-chat, temp=0.2, seed=7). Reads
UPSTREAM_API_KEY from archolith-context/.env. STOPS on a 429 per protocol.
Set ARCHOLITH_CORPUS to the bulletproof-react react-vite src.
Reproduce: python bpr_phase_d.py
"""
from __future__ import annotations

import json
import re
import shutil
import sys
import urllib.error
import urllib.request
from itertools import zip_longest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))  # rung3/ for paths.py
from paths import context_root  # noqa: E402

sys.path.insert(0, str(context_root()))

from archolith_proxy.curator.briefing import SessionBriefing  # noqa: E402
from archolith_proxy.curator.deterministic_assembler import build_deterministic_context  # noqa: E402
from archolith_proxy.curator.scoring import score_files  # noqa: E402
from archolith_proxy.curator.dependency_graph import order_by_topology  # noqa: E402
from bpr_corpus import build_briefing  # noqa: E402
from bpr_contract import check_feature  # noqa: E402

_CTX = context_root()
BUDGET = 3000
STRATEGIES = ("fifo", "scored", "topological", "combo", "xfcombo")
OUT = HERE / "phaseD-output"

# (feature key, user-prompt noun phrase, scored query) — query varies WITH the task.
TASKS = [
    ("notifications", "a Notifications feature that lists the user's notifications, each showing its message and date",
     "notifications list feature message date"),
    ("projects", "a Projects feature that lists projects, each showing its name and status",
     "projects list feature name status"),
    ("tags", "a Tags feature that lists tags, each showing its label and color",
     "tags list feature label color"),
]

SYSTEM = (
    "You are a senior engineer adding a feature to an existing TypeScript React + Vite app under "
    "src/. It uses React Query (@tanstack/react-query) and a shared axios api-client. Below is the "
    "RELEVANT CONTEXT retrieved from the codebase — it is ALL you have; you cannot open other "
    "files. Study the conventions it shows and follow them exactly.\n\n{context}"
)


def _user_prompt(noun: str) -> str:
    return (
        f"Add {noun}, consistent with the rest of the app. Create the necessary files under "
        "src/features so it fits the app's existing patterns.\n\n"
        "Output EVERY file you create. For each file, emit a line exactly of the form:\n"
        "FILE: <relative/path/from/repo/root>\n"
        "immediately followed by a fenced code block with the file's full contents. Output nothing else."
    )


def _api_key() -> str:
    for line in (_CTX / ".env").read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("UPSTREAM_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("UPSTREAM_API_KEY not found in .env")


def call_deepseek(context_block: str, user: str, key: str) -> str:
    body = json.dumps({
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": SYSTEM.format(context=context_block)},
            {"role": "user", "content": user},
        ],
        "temperature": 0.2, "max_tokens": 4000, "seed": 7,
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.deepseek.com/v1/chat/completions", data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return json.loads(r.read())["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as e:
        if e.code == 429:
            raise SystemExit("STOP: DeepSeek returned 429 (rate limit) — halting per protocol.")
        raise


_FILE_BLOCK = re.compile(
    r"FILE:\s*(?P<path>[^\n`]+)\s*\n+```[^\n]*\n(?P<body>.*?)```", re.DOTALL)


def parse_and_write(text: str, dest_root: Path) -> list[str]:
    written: list[str] = []
    for m in _FILE_BLOCK.finditer(text):
        rel = m.group("path").strip().lstrip("/").replace("\\", "/")
        p = dest_root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(m.group("body"), encoding="utf-8")
        written.append(rel)
    return written


def _find_feature(root: Path, fkey: str) -> Path | None:
    """Locate the generated feature dir. Robust to the model omitting the `src/`
    prefix: search any `features/<stem>` directory anywhere under the output root."""
    stem = fkey.rstrip("s").lower()
    candidates = []
    for feats in root.rglob("features"):
        if not feats.is_dir():
            continue
        for d in sorted(feats.iterdir()):
            if d.is_dir() and stem in d.name.lower():
                candidates.append(d)
    if not candidates:
        return None
    # Prefer the shallowest match (the feature dir itself, not a nested one).
    return min(candidates, key=lambda p: len(p.parts))


def _is_exemplar(path: str) -> bool:
    """bulletproof-react's recall-critical template = a feature api query file."""
    return bool(re.search(r"features/[^/]+/api/get-[^/]*\.ts$", path))


def _combo_order(files, query):
    scored = [f for _s, f in score_files(files, query)]
    topo = order_by_topology(files)
    seen, out = set(), []
    for a, b in zip_longest(scored, topo):
        for f in (a, b):
            if f is not None and f.path not in seen:
                seen.add(f.path)
                out.append(f)
    return out


def _xf_combo_order(files, query):
    """Exemplar-aware combo: GUARANTEE the top-scored api/get-*.ts query template
    survives first, then interleave scored x topological (the yawn xfcombo, with the
    bulletproof-react exemplar marker)."""
    scored = [f for _s, f in score_files(files, query)]
    topo = order_by_topology(files)
    out, seen = [], set()
    exemplar = next((f for f in scored if _is_exemplar(f.path)), None)
    if exemplar is not None:
        out.append(exemplar)
        seen.add(exemplar.path)
    for a, b in zip_longest(scored, topo):
        for f in (a, b):
            if f is not None and f.path not in seen:
                seen.add(f.path)
                out.append(f)
    return out


def _context(briefing, strat, query):
    if strat in ("combo", "xfcombo"):
        order = (_combo_order if strat == "combo" else _xf_combo_order)(briefing.files, query)
        b2 = SessionBriefing(session_id="bpr-d", source_turn=5,
                             session_goal=briefing.session_goal, files=order)
        return build_deterministic_context(b2, BUDGET)  # FIFO over the combo order
    kw = {"fifo": {}, "scored": dict(scored=True, query=query),
          "topological": dict(topological=True)}[strat]
    return build_deterministic_context(briefing, BUDGET, **kw)


def _score_grid() -> tuple[dict, dict, dict]:
    """Score whatever is in OUT (no API calls) — used by both run() and --rescore."""
    recall: dict[str, list[int]] = {s: [] for s in STRATEGIES}
    core_ok: dict[str, int] = {s: 0 for s in STRATEGIES}
    grid: dict[tuple[str, str], str] = {}
    for fkey, _n, _q in TASKS:
        for strat in STRATEGIES:
            dest = OUT / fkey / strat
            ddir = _find_feature(dest, fkey) if dest.exists() else None
            if ddir is None:
                grid[(fkey, strat)] = "NOFEAT"
                continue
            rep = check_feature(ddir)
            kr, tot = rep.recall_score
            recall[strat].append(kr)
            core_ok[strat] += 1 if rep.ok else 0
            grid[(fkey, strat)] = f"{kr}/{tot}{'*' if rep.ok else ''}"
    return recall, core_ok, grid


def _report(recall, core_ok, grid) -> None:
    print(f"{'task':<14}" + "".join(f"{s:<14}" for s in STRATEGIES))
    print("-" * 84)
    for fkey, _n, _q in TASKS:
        print(f"{fkey:<14}" + "".join(f"{grid.get((fkey,s),'-'):<14}" for s in STRATEGIES))
    print("-" * 84)
    print("(* = core PASS: query+api-client+react-query+list-component all present)\n")
    print(f"{'strategy':<14}{'mean recall':<16}{'core-OK':<10}")
    for s in STRATEGIES:
        v = recall[s]
        print(f"{s:<14}{(sum(v)/len(v) if v else 0):.2f}/6{'':<8}{core_ok[s]}/{len(TASKS)}")


def rescore() -> int:
    """Re-score the persisted phaseD-output offline (no API calls)."""
    print("bulletproof-react Phase D — RE-SCORE of persisted outputs (no API calls)\n")
    _report(*_score_grid())
    return 0


def run() -> int:
    key = _api_key()
    briefing = build_briefing()
    if not briefing.files:
        raise SystemExit("empty briefing — set ARCHOLITH_CORPUS to the bulletproof-react react-vite src")
    if OUT.exists():
        shutil.rmtree(OUT)
    recall: dict[str, list[int]] = {s: [] for s in STRATEGIES}
    core_ok: dict[str, int] = {s: 0 for s in STRATEGIES}
    grid: dict[tuple[str, str], str] = {}

    print("bulletproof-react Phase D — COMBO vs pure fills, frozen-briefing recall (re-reading denied)")
    print(f"tasks={[t[0] for t in TASKS]}  strategies={STRATEGIES}  budget={BUDGET}\n")
    for fkey, noun, query in TASKS:
        user = _user_prompt(noun)
        for strat in STRATEGIES:
            ctx, _sel = _context(briefing, strat, query)
            resp = call_deepseek(ctx, user, key)
            dest = OUT / fkey / strat
            parse_and_write(resp, dest)
            ddir = _find_feature(dest, fkey)
            if ddir is None:
                grid[(fkey, strat)] = "NOFEAT"
                continue
            rep = check_feature(ddir)
            kr, tot = rep.recall_score
            recall[strat].append(kr)
            core_ok[strat] += 1 if rep.ok else 0
            grid[(fkey, strat)] = f"{kr}/{tot}{'*' if rep.ok else ''}"
        print(f"  [{fkey}] " + "  ".join(f"{s}={grid.get((fkey,s),'-')}" for s in STRATEGIES))

    print()
    print(f"{'task':<14}" + "".join(f"{s:<14}" for s in STRATEGIES))
    print("-" * 84)
    for fkey, _n, _q in TASKS:
        print(f"{fkey:<14}" + "".join(f"{grid.get((fkey,s),'-'):<14}" for s in STRATEGIES))
    print("-" * 84)
    print("(* = core PASS: query+api-client+react-query+list-component all present)\n")
    print(f"{'strategy':<14}{'mean recall':<16}{'core-OK':<10}")
    for s in STRATEGIES:
        v = recall[s]
        print(f"{s:<14}{(sum(v)/len(v) if v else 0):.2f}/6{'':<8}{core_ok[s]}/{len(TASKS)}")
    return 0


if __name__ == "__main__":
    if "--rescore" in sys.argv:
        raise SystemExit(rescore())
    raise SystemExit(run())
