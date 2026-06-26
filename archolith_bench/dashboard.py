"""Live benchmark dashboard for Mode-B memory runs.

A full run takes hours; tailing a log is not real tracking. This reads the same
append-only checkpoint the run writes (one record per completed (arm, item)) for
progress + running accuracy, and optionally probes the throwaway menhir for live
activity (queue depth, enrichment) so you can see it is actually working between
item completions. Read-only: it never touches the running benchmark or its store.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

# Known full-dataset item counts (per arm) so progress shows a % without a network
# load. Override with --total-items when running a subset.
_KNOWN_VARIANT_ITEMS = {"oracle": 500, "s": 500, "m": 500}

# First-seen wall-clock per (checkpoint, arm, task_id). Used when a checkpoint record has
# no `ts` (older runs predating the timestamped format): the dashboard stamps an item the
# first refresh it observes it, so a live run still gets per-item times.
_FIRST_SEEN: dict[tuple[str, str, str], float] = {}


@dataclass
class ArmAgg:
    n: int = 0
    correct: int = 0
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def score(self) -> float:
        return (self.correct / self.n) if self.n else 0.0


@dataclass
class RunSnapshot:
    checkpoint: Path
    benchmark: str
    variant: str
    model: str
    arms: dict[str, ArmAgg] = field(default_factory=dict)
    mtime: float = 0.0
    source: str = ""  # the checkpoint's folder, distinguishes same-named runs (e.g. ext-deepseek)
    items: list[dict] = field(default_factory=list)  # per-item feed in completion order

    @property
    def total_done(self) -> int:
        return sum(a.n for a in self.arms.values())

    @property
    def lift(self) -> float | None:
        """menhir_recall score minus the no_memory floor, when both arms are present."""
        base = self.arms.get("no_memory")
        mem = self.arms.get("menhir_recall")
        if base is None or mem is None or base.n == 0 or mem.n == 0:
            return None
        return mem.score - base.score


def _parse_checkpoint_name(path: Path) -> tuple[str, str, str]:
    """`.checkpoint_<benchmark>_<variant>_<model>.jsonl` -> (benchmark, variant, model)."""
    stem = path.name
    if stem.startswith(".checkpoint_"):
        stem = stem[len(".checkpoint_"):]
    if stem.endswith(".jsonl"):
        stem = stem[: -len(".jsonl")]
    parts = stem.split("_")
    if len(parts) >= 3:
        # benchmark may itself contain no underscore (longmemeval-menhir); variant is
        # the second-to-last segment, model the last, benchmark the rest.
        model = parts[-1]
        variant = parts[-2]
        benchmark = "_".join(parts[:-2])
        return benchmark, variant, model
    return stem, "?", "?"


def read_checkpoint(path: Path) -> RunSnapshot:
    benchmark, variant, model = _parse_checkpoint_name(path)
    snap = RunSnapshot(checkpoint=path, benchmark=benchmark, variant=variant, model=model,
                       mtime=path.stat().st_mtime if path.exists() else 0.0,
                       source=path.parent.name)
    if not path.exists():
        return snap
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                arm = str(rec["arm"])
                res = rec["result"]
            except (json.JSONDecodeError, KeyError, TypeError):
                continue  # tolerate a torn final line
            agg = snap.arms.setdefault(arm, ArmAgg())
            agg.n += 1
            agg.correct += 1 if res.get("correct") else 0
            agg.input_tokens += int(res.get("input_tokens") or 0)
            agg.output_tokens += int(res.get("output_tokens") or 0)
            task_id = str(res.get("task_id") or rec.get("task_id") or "")
            ts = rec.get("ts")
            if ts is None:
                key = (str(path), arm, task_id)
                ts = _FIRST_SEEN.setdefault(key, time.time())
            snap.items.append({
                "arm": arm,
                "task_id": task_id,
                "correct": bool(res.get("correct")),
                "resp": (res.get("response_text") or "").strip().replace("\n", " "),
                "out_tok": int(res.get("output_tokens") or 0),
                "ts": float(ts),
                "question": (res.get("question") or "").strip(),
                "recalled": (res.get("recalled") or "").strip(),
                "gold": (res.get("gold") or "").strip(),
            })
    return snap


def scan_runs(results_dir: Path, *, active_within_s: float | None = None) -> list[RunSnapshot]:
    if not results_dir.exists():
        return []
    # rglob so isolated per-config runs in subfolders (results/ext-deepseek/...) show too.
    paths = {p for p in results_dir.glob(".checkpoint_*.jsonl")}
    paths |= {p for p in results_dir.rglob(".checkpoint_*.jsonl")}
    snaps = [read_checkpoint(p) for p in sorted(paths)]
    if active_within_s:
        # "Active" = checkpoint written within the window (a run currently producing items).
        cutoff = time.time() - active_within_s
        snaps = [s for s in snaps if s.mtime >= cutoff]
    snaps.sort(key=lambda s: s.mtime, reverse=True)
    return snaps


def probe_menhir(url: str, timeout: float = 3.0) -> dict | None:
    """Best-effort live menhir state (health + queue/enrichment). None if unreachable."""
    try:
        import httpx
    except ImportError:
        return None
    base = url.rstrip("/")
    out: dict = {}
    try:
        with httpx.Client(timeout=timeout) as c:
            h = c.get(f"{base}/api/health")
            out["health"] = h.status_code == 200
            try:
                s = c.get(f"{base}/api/stats", params={"since_hours": 1})
                if s.status_code == 200:
                    d = s.json()
                    out["queue_depth"] = d.get("queue_depth")
                    out["startup_mode"] = d.get("startup_mode")
                    enr = d.get("enrichment") or {}
                    out["enrichment"] = enr
            except httpx.HTTPError:
                pass
    except httpx.HTTPError:
        return None
    return out


def _bar(done: int, total: int | None, width: int = 28) -> str:
    if not total or total <= 0:
        return f"[{'?' * width}] {done}"
    frac = min(1.0, done / total)
    filled = int(frac * width)
    return f"[{'#' * filled}{'-' * (width - filled)}] {done}/{total} ({frac * 100:.1f}%)"


def render(
    snaps: list[RunSnapshot],
    menhir: dict | None,
    *,
    total_items: int | None,
    rate_per_min: float | None,
    eta_min: float | None,
) -> str:
    lines: list[str] = []
    lines.append("=" * 64)
    lines.append(f"  archolith-bench memory dashboard   {time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("=" * 64)
    if not snaps:
        lines.append("  (no checkpoints found -- start a run with --resume)")
        return "\n".join(lines)

    for s in snaps:
        per_arm_total = total_items or _KNOWN_VARIANT_ITEMS.get(s.variant)
        n_arms = max(1, len(s.arms))
        grand_total = per_arm_total * n_arms if per_arm_total else None
        lines.append("")
        src = f"  [{s.source}]" if s.source and s.source != "results" else ""
        lines.append(f"  {s.benchmark}{src}  variant={s.variant}  answer-model={s.model}")
        lines.append(f"  progress {_bar(s.total_done, grand_total)}")
        if rate_per_min:
            eta_txt = f"  ETA ~{eta_min:.0f} min" if eta_min is not None else ""
            lines.append(f"  rate {rate_per_min:.1f} items/min{eta_txt}")
        lines.append(f"  {'arm':<16}{'done':>6}{'acc':>9}{'in_tok':>12}{'out_tok':>10}")
        for arm in sorted(s.arms):
            a = s.arms[arm]
            done_txt = f"{a.n}/{per_arm_total}" if per_arm_total else str(a.n)
            lines.append(f"  {arm:<16}{done_txt:>6}{a.score:>9.3f}{a.input_tokens:>12,}{a.output_tokens:>10,}")
        if s.lift is not None:
            lines.append(f"  memory lift (menhir_recall - no_memory): {s.lift:+.3f}")

    lines.append("")
    if menhir is not None:
        if menhir.get("health"):
            qd = menhir.get("queue_depth")
            mode = menhir.get("startup_mode")
            enr = menhir.get("enrichment") or {}
            rate = enr.get("episodes_per_min") or enr.get("rate") or enr.get("per_min")
            extra = f"  enrich~{rate}/min" if rate else ""
            lines.append(f"  menhir: UP  mode={mode}  queue_depth={qd}{extra}")
        else:
            lines.append("  menhir: probe returned non-200 (starting or degraded)")
    else:
        lines.append("  menhir: not probed (pass --menhir-url for live activity)")
    lines.append("  note: token/cost columns are ANSWER-model only; menhir ingestion")
    lines.append("        (OpenAI extraction+embedding) spend is not tracked by the bench.")
    lines.append("=" * 64)
    return "\n".join(lines)


def _esc(s: object) -> str:
    import html
    return html.escape(str(s))


def _feed_rows_html(s: RunSnapshot, items_n: int) -> str:
    """Newest-first per-item feed (turn-by-turn) for one run."""
    if not items_n or not s.items:
        return ""
    recent = list(reversed(s.items))[:items_n]
    cells = ""
    for it in recent:
        mark = "&#10003;" if it["correct"] else "&#10007;"
        cls = "ok" if it["correct"] else "no"
        ts = it.get("ts")
        tstr = time.strftime("%H:%M:%S", time.localtime(ts)) if ts else ""
        full = it["resp"]
        q = it.get("question", "")
        recalled = it.get("recalled", "")
        gold = it.get("gold", "")
        # If we captured question/retrieval (newer runs), make the answer cell expandable
        # to show question -> retrieved memory -> gold -> response. Older runs (no capture)
        # just show the answer text.
        if q or recalled:
            recall_html = (
                "<div class='blk'><span class='lbl'>retrieved memory</span>"
                f"<pre>{_esc(recalled) or '<em>(none)</em>'}</pre></div>"
            )
            detail = (
                f"<summary>{_esc(full)}</summary>"
                f"<div class='blk'><span class='lbl'>question</span><div>{_esc(q)}</div></div>"
                f"{recall_html}"
                f"<div class='blk'><span class='lbl'>gold</span><div>{_esc(gold)}</div></div>"
                f"<div class='blk'><span class='lbl'>llm response</span><div>{_esc(full)}</div></div>"
            )
            ans_cell = f"<details>{detail}</details>"
        else:
            ans_cell = f"<span title='{_esc(full)}'>{_esc(full)}</span>"
        cells += (
            f"<tr><td class='muted'>{tstr}</td><td class='{cls}'>{mark}</td><td>{_esc(it['arm'])}</td>"
            f"<td class='muted'>{_esc(it['task_id'][:24])}</td>"
            f"<td class='ans'>{ans_cell}</td></tr>"
        )
    return (
        "<table class='feed'><thead><tr><th>time</th><th></th><th>arm</th><th>item</th>"
        f"<th>answer</th></tr></thead><tbody>{cells}</tbody></table>"
    )


def render_html(
    snaps: list[RunSnapshot],
    menhir: dict | None,
    *,
    total_items: int | None,
    refresh_s: int = 5,
    items_n: int = 20,
) -> str:
    """Self-contained auto-refreshing HTML page for the same data as render()."""
    rows: list[str] = []
    for s in snaps:
        per_arm_total = total_items or _KNOWN_VARIANT_ITEMS.get(s.variant)
        n_arms = max(1, len(s.arms))
        grand_total = per_arm_total * n_arms if per_arm_total else None
        pct = (s.total_done / grand_total * 100.0) if grand_total else None
        bar = (
            f'<div class="bar"><div class="fill" style="width:{min(100.0, pct):.1f}%"></div></div>'
            f'<span class="muted">{s.total_done}{"/" + str(grand_total) if grand_total else ""}'
            f'{f" ({pct:.1f}%)" if pct is not None else ""}</span>'
        ) if True else ""
        arm_rows = ""
        for arm in sorted(s.arms):
            a = s.arms[arm]
            done = f"{a.n}/{per_arm_total}" if per_arm_total else str(a.n)
            arm_rows += (
                f"<tr><td>{_esc(arm)}</td><td class='num'>{_esc(done)}</td>"
                f"<td class='num'>{a.score:.3f}</td><td class='num'>{a.input_tokens:,}</td>"
                f"<td class='num'>{a.output_tokens:,}</td></tr>"
            )
        lift = f"<span class='lift'>memory lift: {s.lift:+.3f}</span>" if s.lift is not None else ""
        src = f" <span class='src'>[{_esc(s.source)}]</span>" if s.source and s.source != "results" else ""
        feed = _feed_rows_html(s, items_n)
        feed_block = f"<details open><summary class='muted'>turn-by-turn (latest {items_n})</summary>{feed}</details>" if feed else ""
        rows.append(
            f"<div class='run'><h2>{_esc(s.benchmark)}{src} "
            f"<span class='muted'>variant={_esc(s.variant)} &middot; answer-model={_esc(s.model)}</span></h2>"
            f"<div class='prog'>{bar}</div>"
            f"<table><thead><tr><th>arm</th><th>done</th><th>acc</th><th>in_tok</th><th>out_tok</th></tr></thead>"
            f"<tbody>{arm_rows}</tbody></table>{lift}{feed_block}</div>"
        )
    body = "".join(rows) or "<p class='muted'>No checkpoints yet — start a run with --resume.</p>"

    if menhir is None:
        mh = "<span class='muted'>menhir: not probed</span>"
    elif menhir.get("health"):
        enr = menhir.get("enrichment") or {}
        rate = enr.get("episodes_per_min") or enr.get("rate") or enr.get("per_min")
        mh = (f"<span class='up'>&#9679; menhir UP</span> "
              f"<span class='muted'>mode={_esc(menhir.get('startup_mode'))} &middot; "
              f"queue_depth={_esc(menhir.get('queue_depth'))}"
              f"{f' &middot; enrich~{_esc(rate)}/min' if rate else ''}</span>")
    else:
        mh = "<span class='down'>&#9679; menhir starting/degraded</span>"

    return f"""<!doctype html><html><head><meta charset="utf-8">
<meta http-equiv="refresh" content="{refresh_s}">
<title>archolith-bench dashboard</title>
<style>
 body{{font:14px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace;background:#0d1117;color:#c9d1d9;margin:0;padding:24px}}
 h1{{font-size:18px;margin:0 0 4px}} h2{{font-size:15px;margin:18px 0 8px}}
 .muted{{color:#8b949e;font-weight:normal}} .up{{color:#3fb950}} .down{{color:#f85149}}
 .src{{color:#d29922}}
 .lift{{color:#58a6ff}} table{{border-collapse:collapse;margin:6px 0}}
 th,td{{padding:4px 14px 4px 0;text-align:left}} th{{color:#8b949e;font-weight:normal;border-bottom:1px solid #30363d}}
 td.num{{text-align:right;font-variant-numeric:tabular-nums}}
 .bar{{display:inline-block;width:320px;height:12px;background:#21262d;border-radius:6px;overflow:hidden;vertical-align:middle;margin-right:8px}}
 .fill{{height:100%;background:linear-gradient(90deg,#1f6feb,#3fb950)}}
 .run{{border:1px solid #30363d;border-radius:8px;padding:10px 16px;margin:12px 0;max-width:900px}}
 .ok{{color:#3fb950;font-weight:bold}} .no{{color:#f85149;font-weight:bold}}
 details{{margin-top:8px}} summary{{cursor:pointer}}
 table.feed{{width:100%}}
 table.feed td{{vertical-align:top}}
 table.feed td.ans{{white-space:normal;overflow-wrap:anywhere;color:#c9d1d9;max-width:0;width:99%}}
 table.feed td:nth-child(1),table.feed td:nth-child(2),table.feed td:nth-child(3),table.feed td:nth-child(4){{white-space:nowrap}}
 td.ans details summary{{cursor:pointer;color:#c9d1d9}}
 td.ans details[open] summary{{color:#58a6ff;margin-bottom:6px}}
 .blk{{margin:5px 0 5px 10px;border-left:2px solid #30363d;padding-left:10px}}
 .lbl{{display:block;font-size:11px;text-transform:uppercase;letter-spacing:.05em;color:#8b949e}}
 .blk pre{{margin:2px 0;white-space:pre-wrap;overflow-wrap:anywhere;color:#79c0ff;font-size:12.5px;max-height:220px;overflow:auto}}
 footer{{color:#8b949e;margin-top:18px;max-width:900px}}
</style></head><body>
<h1>archolith-bench &mdash; memory benchmark</h1>
<div class="muted">{time.strftime('%Y-%m-%d %H:%M:%S')} &middot; auto-refresh {refresh_s}s</div>
<div style="margin:10px 0">{mh}</div>
{body}
<footer>Token columns are ANSWER-model only; menhir ingestion (OpenAI extraction+embedding)
spend is not tracked by the bench. Progress is by item-count across arms.</footer>
</body></html>"""


def serve_dashboard(
    results_dir: Path,
    *,
    menhir_url: str | None = None,
    host: str = "127.0.0.1",
    port: int = 8200,
    total_items: int | None = None,
    refresh_s: int = 5,
    items_n: int = 20,
    active_within_s: float | None = None,
) -> None:
    """Serve the dashboard as an auto-refreshing web page until interrupted."""
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):  # silence access logs
            pass

        def do_GET(self):  # noqa: N802
            snaps = scan_runs(results_dir, active_within_s=active_within_s)
            menhir = probe_menhir(menhir_url) if menhir_url else None
            page = render_html(snaps, menhir, total_items=total_items, refresh_s=refresh_s, items_n=items_n)
            data = page.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    server = ThreadingHTTPServer((host, port), Handler)
    print(f"dashboard serving at http://{host}:{port}  (Ctrl-C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n(dashboard stopped)")
        server.shutdown()


def run_dashboard(
    results_dir: Path,
    *,
    menhir_url: str | None = None,
    interval: float = 5.0,
    once: bool = False,
    total_items: int | None = None,
    active_within_s: float | None = None,
) -> None:
    prev_done: int | None = None
    prev_t: float | None = None
    rate_per_min: float | None = None
    eta_min: float | None = None
    while True:
        snaps = scan_runs(results_dir, active_within_s=active_within_s)
        menhir = probe_menhir(menhir_url) if menhir_url else None

        active = snaps[0] if snaps else None
        if active is not None:
            now = time.time()
            done = active.total_done
            if prev_done is not None and prev_t is not None and now > prev_t:
                delta = done - prev_done
                dt_min = (now - prev_t) / 60.0
                if delta > 0 and dt_min > 0:
                    rate_per_min = delta / dt_min
                    per_arm_total = total_items or _KNOWN_VARIANT_ITEMS.get(active.variant)
                    grand = (per_arm_total * max(1, len(active.arms))) if per_arm_total else None
                    if grand:
                        eta_min = max(0.0, (grand - done) / rate_per_min)
            prev_done, prev_t = done, now

        out = render(snaps, menhir, total_items=total_items, rate_per_min=rate_per_min, eta_min=eta_min)
        if once:
            print(out)
            return
        # clear screen + repaint
        print("\033[2J\033[H" + out, flush=True)
        time.sleep(interval)
