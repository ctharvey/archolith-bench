"""Overnight A/B orchestrator (detached).

1. Wait for the in-flight gpt-4o-mini run to finish its menhir_recall arm (30 items).
2. Wait for its throwaway stack (menhir :8101) to tear down.
3. Launch the agentic arm (menhir_agentic_recall) against the SAME gpt-4o-mini
   checkpoint via the run script (--resume adds the arm; reuses dotenv keys + stack
   lifecycle), recall-limit 25, llm-judge (gpt-4o).
4. Write a 3-way comparison (floor vs single-query vs agentic) + the items agentic
   fixed/regressed, with retrieval counts, to AB_RESULTS.md.

Launched detached so it survives the session. Read results/ext-openai/AB_RESULTS.md
and _overnight.log in the morning.
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import time
from collections import defaultdict

BENCH = r"C:\Users\thron\IdeaProjects\projects\archolith\archolith-bench"
CK = BENCH + r"\results\ext-openai\.checkpoint_longmemeval-menhir_oracle_gpt-4o-mini.jsonl"
LOG = BENCH + r"\results\ext-openai\_overnight.log"
SUMMARY = BENCH + r"\results\ext-openai\AB_RESULTS.md"
AGENTIC_LOG = BENCH + r"\results\ext-openai\run_agentic.log"
BASH = r"C:\Program Files\Git\bin\bash.exe"
TARGET = 30


def log(msg: str) -> None:
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}  {msg}\n")


def arm_count(arm: str) -> int:
    try:
        with open(CK, encoding="utf-8") as f:
            return sum(1 for line in f if line.strip() and f'"{arm}"' in line)
    except FileNotFoundError:
        return 0


def port_open(host: str, port: int) -> bool:
    s = socket.socket()
    s.settimeout(1)
    try:
        s.connect((host, port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def load_dedup() -> list[dict]:
    best: dict[tuple, dict] = {}
    try:
        with open(CK, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                best[(r["arm"], r["result"]["task_id"])] = r
    except FileNotFoundError:
        pass
    return list(best.values())


def main() -> None:
    log("=== overnight A/B orchestrator start ===")

    # 1. wait for the 4o run's menhir_recall to finish
    deadline = time.time() + 4 * 3600
    while arm_count("menhir_recall") < TARGET:
        if time.time() > deadline:
            log(f"TIMEOUT waiting for 4o menhir_recall (stuck at {arm_count('menhir_recall')})")
            break
        time.sleep(30)
    log(f"4o menhir_recall={arm_count('menhir_recall')}; waiting for :8101 to free")

    # 2. wait for the throwaway stack to tear down
    for _ in range(60):
        if not port_open("127.0.0.1", 8101):
            break
        time.sleep(3)
    time.sleep(10)

    # 3. launch the agentic arm via the run script (resume adds it to the same checkpoint)
    env = dict(os.environ)
    env.update(
        ANSWER_PROVIDER="openai", OPENAI_ANSWER_MODEL="gpt-4o-mini", RECALL_LIMIT="25",
        SCORER="llm-judge", LONGMEMEVAL_VARIANT="oracle",
    )
    cmd = [BASH, "scripts/run_longmemeval_modeb.sh", "--limit", "30",
           "--arms", "menhir_agentic_recall", "--resume"]
    log(f"launching agentic run: {' '.join(cmd)}")
    with open(AGENTIC_LOG, "w", encoding="utf-8") as out:
        rc = subprocess.run(cmd, cwd=BENCH, env=env, stdout=out, stderr=subprocess.STDOUT).returncode
    log(f"agentic run exited rc={rc}; agentic items={arm_count('menhir_agentic_recall')}")

    # 4. analyze + write summary
    rows = load_dedup()
    agg: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    by_item: dict[str, dict[str, dict]] = defaultdict(dict)
    for r in rows:
        a, res = r["arm"], r["result"]
        agg[a][1] += 1
        agg[a][0] += 1 if res["correct"] else 0
        by_item[res["task_id"]][a] = res

    def acc(a: str) -> float:
        c, t = agg.get(a, [0, 0])
        return c / t if t else 0.0

    arms = ("no_memory", "menhir_recall", "menhir_agentic_recall")
    out = [
        "# LongMemEval oracle (temporal) - 3-way A/B",
        "",
        f"Generated {time.strftime('%Y-%m-%d %H:%M:%S')}  .  answer=gpt-4o-mini . recall-limit=25 . judge=gpt-4o",
        "",
        "| arm | n | correct | acc |",
        "|---|--:|--:|--:|",
    ]
    for a in arms:
        c, t = agg.get(a, [0, 0])
        out.append(f"| {a} | {t} | {c} | {c / t:.3f} |" if t else f"| {a} | 0 | 0 | n/a |")
    out += [
        "",
        f"- single-query lift (menhir_recall - floor): {acc('menhir_recall') - acc('no_memory'):+.3f}",
        f"- agentic lift (menhir_agentic_recall - floor): {acc('menhir_agentic_recall') - acc('no_memory'):+.3f}",
        f"- **agentic vs single delta: {acc('menhir_agentic_recall') - acc('menhir_recall'):+.3f}**",
        "",
    ]

    def nsnip(res: dict) -> int:
        return len([x for x in (res.get("recalled") or "").split("\n") if x.strip()])

    fixed, regressed = [], []
    for tid, d in by_item.items():
        s, a = d.get("menhir_recall"), d.get("menhir_agentic_recall")
        if not s or not a:
            continue
        if not s["correct"] and a["correct"]:
            fixed.append((tid, s, a))
        elif s["correct"] and not a["correct"]:
            regressed.append((tid, s, a))

    out.append(f"## Agentic fixed {len(fixed)} item(s) the single-query arm missed")
    out.append("")
    for tid, s, a in fixed:
        out += [
            f"### {a.get('question', tid)[:120]}",
            f"- gold: `{a.get('gold','')[:60]}`",
            f"- single-query ({nsnip(s)} snippets): {s.get('response_text','')[:140]!r}",
            f"- agentic ({nsnip(a)} snippets): {a.get('response_text','')[:140]!r}",
            "",
        ]
    out.append(f"## Agentic regressed {len(regressed)} item(s) the single-query arm got right")
    out.append("")
    for tid, s, a in regressed:
        out += [
            f"### {a.get('question', tid)[:120]}",
            f"- gold: `{a.get('gold','')[:60]}`",
            f"- single-query ({nsnip(s)} snippets): {s.get('response_text','')[:140]!r}",
            f"- agentic ({nsnip(a)} snippets): {a.get('response_text','')[:140]!r}",
            "",
        ]

    with open(SUMMARY, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    log(f"wrote {SUMMARY}")
    log("=== DONE ===")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # never die silently
        log(f"FATAL: {exc.__class__.__name__}: {exc}")
        raise
