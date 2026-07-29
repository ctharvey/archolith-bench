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


@dataclass
class IngestSnapshot:
    """Completed LongMemEval graph-ingest items recorded in a run manifest."""

    manifest: Path
    source: str
    items: list[dict] = field(default_factory=list)
    mtime: float = 0.0

    @property
    def completed(self) -> int:
        return len(self.items)


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


def read_ingest_manifest(path: Path) -> IngestSnapshot:
    snap = IngestSnapshot(
        manifest=path,
        source=path.parent.name,
        mtime=path.stat().st_mtime if path.exists() else 0.0,
    )
    if not path.exists():
        return snap
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return snap
    if isinstance(rows, list):
        snap.items = [row for row in rows if isinstance(row, dict)]
    return snap


def scan_ingests(results_dir: Path, *, active_within_s: float | None = None) -> list[IngestSnapshot]:
    if not results_dir.exists():
        return []
    paths = {p for p in results_dir.glob("manifest.json")}
    paths |= {p for p in results_dir.rglob("manifest.json")}
    snaps = [read_ingest_manifest(p) for p in sorted(paths)]
    if active_within_s:
        cutoff = time.time() - active_within_s
        snaps = [s for s in snaps if s.mtime >= cutoff]
    snaps.sort(key=lambda s: s.mtime, reverse=True)
    return snaps


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


def _slug_id(*parts: str) -> str:
    raw = "_".join(str(p) for p in parts)
    return "d_" + "".join(c if c.isalnum() else "_" for c in raw)[:80]


def _feed_rows_html(s: RunSnapshot, items_n: int) -> str:
    """Newest-first per-item feed (turn-by-turn) for one run."""
    if not items_n or not s.items:
        return ""
    runkey = f"{s.model}_{s.variant}_{s.source}"
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
            # Summary shows the QUESTION (visible at a glance); expanding reveals what was
            # retrieved, the gold answer, and the model's response.
            did = _slug_id(runkey, it["arm"], it["task_id"])
            snips = [ln for ln in recalled.split("\n") if ln.strip()]
            if snips:
                snip_html = "".join(
                    f"<div class='snip'><span class='snum'>{i + 1}</span>{_esc(ln)}</div>"
                    for i, ln in enumerate(snips)
                )
                recalled_block = (
                    f"<span class='lbl'>retrieved memory ({len(snips)})</span>"
                    f"<div id='{did}_pre' class='keepscroll snips'>{snip_html}</div>"
                )
            else:
                recalled_block = (
                    "<span class='lbl'>retrieved memory</span>"
                    "<div class='muted'><em>(nothing recalled)</em></div>"
                )
            detail = (
                f"<summary>{_esc(q) or _esc(full)}</summary>"
                f"<div class='blk'>{recalled_block}</div>"
                f"<div class='blk'><span class='lbl'>gold answer</span><div>{_esc(gold)}</div></div>"
                f"<div class='blk'><span class='lbl'>llm response</span><div>{_esc(full)}</div></div>"
            )
            ans_cell = f"<details id='{did}'>{detail}</details>"
        else:
            ans_cell = f"<span title='{_esc(full)}'>{_esc(full)}</span>"
        cells += (
            f"<tr><td class='muted'>{tstr}</td><td class='{cls}'>{mark}</td><td>{_esc(it['arm'])}</td>"
            f"<td class='muted'>{_esc(it['task_id'][:24])}</td>"
            f"<td class='ans'>{ans_cell}</td></tr>"
        )
    return (
        "<table class='feed'><thead><tr><th>time</th><th></th><th>arm</th><th>item</th>"
        "<th>question &middot; click to expand retrieval &rarr; gold &rarr; response</th>"
        "</tr></thead><tbody>" + cells + "</tbody></table>"
    )


def _ingest_rows_html(ingests: list[IngestSnapshot], total_items: int | None) -> str:
    rows: list[str] = []
    for ingest in ingests:
        done = ingest.completed
        pct = (done / total_items * 100.0) if total_items else None
        progress = (
            f'<div class="bar"><div class="fill" style="width:{min(100.0, pct):.1f}%"></div></div>'
            f'<span class="muted">{done}/{total_items} ({pct:.1f}%)</span>'
            if pct is not None
            else f'<span class="muted">{done} completed</span>'
        )
        ready = sum(int(item.get("ready") or 0) for item in ingest.items)
        failed = sum(int(item.get("failed_remaining") or 0) for item in ingest.items)
        turn_evidence = sum(int(item.get("turn_evidence") or 0) for item in ingest.items)
        scalar_views = sum(int(item.get("scalar_views") or 0) for item in ingest.items)
        latest = ingest.items[-1] if ingest.items else {}
        latest_question = latest.get("question") or latest.get("question_id") or "none yet"
        if total_items and done >= total_items:
            phase_note = "Graph ingest complete; recall/QA scoring should begin next."
        else:
            phase_note = "Graph ingest is active; accuracy appears after recall/QA checkpointing begins."
        rows.append(
            f"<div class='run'><h2>LongMemEval graph ingest "
            f"<span class='src'>[{_esc(ingest.source)}]</span></h2>"
            f"<div class='prog'>{progress}</div>"
            "<table><thead><tr><th>completed</th><th>ready episodes</th><th>failed</th>"
            "<th>turn evidence</th><th>scalar views</th></tr></thead>"
            f"<tbody><tr><td>{done}</td><td>{ready}</td><td>{failed}</td>"
            f"<td>{turn_evidence}</td><td>{scalar_views}</td></tr></tbody></table>"
            f"<div class='muted'>latest completed: {_esc(latest_question)}</div>"
            f"<div class='muted'>{phase_note}</div></div>"
        )
    return "".join(rows)


def _scalar_viewer_shell(default_namespace: str | None) -> str:
    """Interactive shell; task data is loaded on demand from read-only JSON routes."""
    default_json = (
        json.dumps(default_namespace or "")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )
    return """
<section id="scalar-viewer" class="viewer">
  <div class="viewer-head">
    <div>
      <div class="eyebrow">READ-ONLY GRAPH EXPLORER</div>
      <h2>How one scalar view is made</h2>
      <p class="muted viewer-copy">Walk one completed task from transcript evidence through the
      k-sample vote, durable assertions, deterministic fold, and benchmark answer.</p>
    </div>
    <div class="viewer-picker">
      <label for="scalar-task">completed task</label>
      <select id="scalar-task"></select>
      <button id="scalar-load" type="button">inspect task</button>
    </div>
  </div>
  <div id="scalar-status" class="muted">Loading completed tasks…</div>
  <div id="scalar-body"></div>
</section>
<script>
(() => {
  const preferred = __DEFAULT_NAMESPACE__;
  const state = {data: null, stage: 0, onlyFounded: false};
  const stageMeta = [
    ["1", "Evidence", "preserved source turns"],
    ["2", "2-of-3 gate", "stochastic extraction vote"],
    ["3", "Assertions", "durable typed events"],
    ["4", "Scalar view", "deterministic fold"],
    ["5", "Answer path", "recall and scoring"],
  ];
  const h = value => String(value == null ? "" : value)
    .replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;").replaceAll("'", "&#039;");
  const when = value => value ? h(String(value).replace("T", " ").replace("Z", " UTC")) : "—";
  const list = value => Array.isArray(value) ? value : [];
  const status = document.getElementById("scalar-status");
  const body = document.getElementById("scalar-body");
  const picker = document.getElementById("scalar-task");

  function currentViews() {
    return list(state.data && state.data.views).filter(v => v.current);
  }

  function stageCounts() {
    const d = state.data || {};
    const gates = list(d.audit).filter(x => x.event === "gate");
    const scores = list(d.scoring);
    return [
      list(d.evidence).filter(x => list(x.founds).length).length + "/" + list(d.evidence).length,
      gates.length,
      list(d.assertions).length,
      currentViews().length + " current",
      scores.length ? scores.length + " scored" : "pending",
    ];
  }

  function renderNav() {
    const counts = stageCounts();
    return `<div class="stage-nav">${stageMeta.map((s, i) =>
      `<button type="button" class="stage ${i === state.stage ? "active" : ""}"
        onclick="window.scalarStage(${i})"><span class="stage-num">${s[0]}</span>
        <span><strong>${s[1]}</strong><small>${h(counts[i])}</small></span></button>`
    ).join('<span class="stage-arrow">→</span>')}</div>`;
  }

  function renderEvidence(d) {
    const assertions = new Map(list(d.assertions).map(a => [a.id, a]));
    const rows = list(d.evidence).filter(t => !state.onlyFounded || list(t.founds).length);
    const transcript = rows.map((t, i) => {
      const founded = list(t.founds).map(id => assertions.get(id)).filter(Boolean);
      return `<article class="turn ${founded.length ? "founded" : ""}">
        <div class="turn-meta"><span>${i + 1}</span><b>${h(t.role)}</b>
          <span>${t.occurred_at ? "source " + when(t.occurred_at) : "source time unavailable"}</span>
          <span>ingested ${when(t.recorded_at)}</span></div>
        <div class="turn-text">${h(t.text)}</div>
        ${founded.length ? `<div class="founds">FOUNDS ${founded.map(a =>
          `<span>${h(a.attribute)} = ${h(a.value)}${a.unit ? " " + h(a.unit) : ""}</span>`
        ).join("")}</div>` : ""}
      </article>`;
    }).join("");
    const facts = list(d.facts).map(f =>
      `<li><b>${h(f.subject)}</b> → ${h(f.object)}<span>${h(f.fact)}</span></li>`
    ).join("");
    return `<div class="stage-panel"><div class="stage-intro">
      <div><h3>Source boundary</h3><p>Every user turn is preserved as <code>TurnEvidence</code>.
      Source time says when it happened; ingested time says when Menhir recorded it. A
      <code>FOUNDS</code> edge marks the exact turn that grounded a committed assertion. Older
      graphs may show source time as unavailable because that field was not captured yet.</p></div>
      <label class="toggle"><input type="checkbox" ${state.onlyFounded ? "checked" : ""}
        onchange="window.scalarFounded(this.checked)"> only founding turns</label></div>
      <div class="transcript">${transcript || '<p class="empty">No evidence rows in this graph.</p>'}</div>
      <details><summary>Context graph facts (${list(d.facts).length})</summary>
        <p class="muted">These aid ordinary recall, but they are not the typed assertion log folded
        into the scalar view.</p><ul class="fact-list">${facts}</ul></details></div>`;
  }

  function voteDistribution(details) {
    const dist = details.distribution || {};
    const k = Number(details.k || 0);
    return Object.entries(dist).map(([label, votes]) => {
      const n = Number(votes || 0);
      const pct = k ? (n / k * 100) : 0;
      return `<div class="vote-row"><div><span>${h(label)}</span><b>${n}/${k || "?"}</b></div>
        <div class="vote-bar"><i style="width:${pct}%"></i></div></div>`;
    }).join("");
  }

  function renderGate(d) {
    const gates = list(d.audit).filter(x => x.event === "gate");
    const cards = gates.map(g => {
      const x = g.details || {};
      const accepted = g.state === "commit";
      return `<article class="gate-card ${accepted ? "accepted" : "rejected"}">
        <div class="gate-title"><span class="pill">${accepted ? "ACCEPTED" : "ABSTAINED"}</span>
          <b>${Math.round(Number(x.agreement || 0) * 100)}% agreement</b>
          <span>${h(x.reason || g.state)}</span></div>
        ${voteDistribution(x)}
        <div class="mono-id">source ${h(String(x.source_key || "").slice(0, 16))}…</div>
      </article>`;
    }).join("");
    const warning = d.audit_warning ? `<div class="warning">${h(d.audit_warning)}</div>` : "";
    return `<div class="stage-panel"><div class="stage-intro"><div><h3>Probabilistic boundary</h3>
      <p>The extractor runs <em>k</em> times. Each sample gets one vote per grounded source claim.
      At a 2-of-3 threshold, two matching readings commit; scattered readings abstain.</p></div>
      <div class="receipt">${d.audit_pass_id ? "receipt " + h(d.audit_pass_id) : "no receipt"}</div>
      </div>${warning}${cards || '<p class="empty">No matching gate receipt.</p>'}</div>`;
  }

  function renderAssertions(d) {
    const cards = list(d.assertions).map((a, i) =>
      `<article class="assertion">
        <div class="assertion-num">${i + 1}</div><div>
          <div class="assertion-value"><b>${h(a.subject)}</b><span>→</span>
            <b>${h(a.attribute)}</b><span>=</span><strong>${h(a.value)}${a.unit ? " " + h(a.unit) : ""}</strong></div>
          <blockquote>“${h(a.stated_span)}”</blockquote>
          <div class="chips"><span>${h(a.value_kind)}</span><span>${h(a.operation)}</span>
            <span>${h(a.evidence_tier)} evidence</span><span>${a.binding_pending ? "binding pending" : "subject bound"}</span></div>
          <div class="muted">world time ${when(a.valid_at)} · learned ${when(a.learned_at)}</div>
        </div>
      </article>`
    ).join("");
    return `<div class="stage-panel"><div class="stage-intro"><div><h3>Durable event log</h3>
      <p>A winning interpretation becomes an immutable <code>TypedAssertion</code>. It records
      subject, slot, typed value, world time, source quote, and binding state.</p></div></div>
      <div class="assertions">${cards || '<p class="empty">No TypedAssertions were emitted.</p>'}</div></div>`;
  }

  function renderViews(d) {
    const views = list(d.views);
    const cards = views.map((v, i) =>
      `<article class="view-card ${v.current ? "current" : "history"}">
        <div class="view-state">${v.current ? "CURRENT" : "SUPERSEDED"}</div>
        <div class="view-value">${h(v.display || v.value)}${v.unit ? " " + h(v.unit) : ""}</div>
        <div><b>${h(v.subject)}</b> · ${h(v.attribute)}${v.scope ? " · " + h(v.scope) : ""}</div>
        <p>${h(v.summary)}</p>
        <div class="chips"><span>${h(v.value_kind)}</span><span>${h(v.effective_tier)} effective tier</span>
          <span>${list(v.contributor_ids).length} contributor</span></div>
        <div class="muted">valid ${when(v.valid_at)}</div>
      </article>${i < views.length - 1 ? '<div class="supersede">→ later world time →</div>' : ""}`
    ).join("");
    return `<div class="stage-panel"><div class="stage-intro"><div><h3>Deterministic projection</h3>
      <p>The fold replays assertions by slot and world time. Views are rebuildable projections:
      old values remain visible for provenance, while exactly one value is current.</p></div></div>
      <div class="views">${cards || '<p class="empty">No scalar_state view materialized.</p>'}</div></div>`;
  }

  function renderAnswer(d) {
    const task = d.task || {};
    const views = currentViews();
    const scores = list(d.scoring);
    const viewRows = views.map(v =>
      `<div class="answer-source"><span>current scalar view</span><b>${h(v.attribute)} = ${h(v.display || v.value)}${v.unit ? " " + h(v.unit) : ""}</b></div>`
    ).join("");
    const scoring = scores.length ? scores.map(s =>
      `<article class="score ${s.correct ? "okbox" : "nobox"}"><b>${h(s.arm)}</b>
       <span>${s.correct ? "correct" : "incorrect"}</span><p>${h(s.response)}</p>
       <details><summary>recalled memory</summary><pre>${h(s.recalled)}</pre></details></article>`
    ).join("") : `<div class="pending">Recall/QA has not written a checkpoint for this task yet.
      The graph build can be inspected now; the final answer path becomes measurable during scoring.</div>`;
    return `<div class="stage-panel answer-grid">
      <div class="answer-question"><span>BENCHMARK QUESTION</span><h3>${h(task.question)}</h3>
        <div class="gold"><span>gold answer</span><b>${h(task.answer)}</b></div></div>
      <div><h3>Available state</h3>${viewRows || '<p class="empty">No current scalar view.</p>'}</div>
      <div class="score-wrap"><h3>Recall → model answer → scorer</h3>${scoring}</div></div>`;
  }

  function render() {
    const d = state.data;
    if (!d) return;
    const task = d.task || {};
    const panels = [renderEvidence, renderGate, renderAssertions, renderViews, renderAnswer];
    body.innerHTML = `<div class="task-hero"><div><span>${h(task.question_type || "task")}</span>
      <h3>${h(task.question || d.namespace)}</h3></div><div class="task-id">${h(d.namespace)}</div></div>
      ${renderNav()}${panels[state.stage](d)}
      <div class="stage-controls"><button type="button" onclick="window.scalarStage(${Math.max(0, state.stage - 1)})"
        ${state.stage === 0 ? "disabled" : ""}>← previous</button>
      <span>${state.stage + 1} / ${stageMeta.length}</span>
      <button type="button" onclick="window.scalarStage(${Math.min(stageMeta.length - 1, state.stage + 1)})"
        ${state.stage === stageMeta.length - 1 ? "disabled" : ""}>next →</button></div>`;
  }

  window.scalarStage = i => { state.stage = Number(i); render(); body.scrollIntoView({behavior: "smooth", block: "start"}); };
  window.scalarFounded = checked => { state.onlyFounded = Boolean(checked); render(); };

  async function loadTask() {
    const namespace = picker.value;
    if (!namespace) return;
    status.textContent = "Reading " + namespace + "…";
    body.innerHTML = "";
    try {
      const response = await fetch("/api/scalar-task?namespace=" + encodeURIComponent(namespace), {cache: "no-store"});
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "viewer request failed");
      state.data = data;
      state.stage = 0;
      status.textContent = "Loaded from Neo4j" + (data.audit_pass_id ? " + vote receipt" : "");
      render();
    } catch (error) {
      status.textContent = "Could not load task: " + error.message;
    }
  }

  async function init() {
    try {
      const response = await fetch("/api/scalar-tasks", {cache: "no-store"});
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "task catalog failed");
      picker.replaceChildren(...data.tasks.map(task => {
        const option = document.createElement("option");
        option.value = task.namespace;
        option.textContent = task.question_id + " · " + (task.question || task.namespace);
        return option;
      }));
      const wanted = preferred || data.default_namespace;
      if (wanted && data.tasks.some(task => task.namespace === wanted)) picker.value = wanted;
      document.getElementById("scalar-load").addEventListener("click", loadTask);
      if (picker.value) await loadTask();
      else status.textContent = "No completed manifest tasks are available.";
    } catch (error) {
      status.textContent = "Scalar viewer unavailable: " + error.message;
    }
  }
  init();
})();
</script>
""".replace("__DEFAULT_NAMESPACE__", default_json)


def render_html(
    snaps: list[RunSnapshot],
    menhir: dict | None,
    *,
    total_items: int | None,
    refresh_s: int = 5,
    items_n: int = 20,
    ingests: list[IngestSnapshot] | None = None,
    scalar_viewer_enabled: bool = False,
    scalar_default_namespace: str | None = None,
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
        feed_wrap_id = _slug_id(s.model, s.variant, s.source, "feedwrap")
        feed_block = (
            f"<details open id='{feed_wrap_id}'><summary class='muted'>turn-by-turn (latest {items_n})</summary>{feed}</details>"
            if feed else ""
        )
        rows.append(
            f"<div class='run'><h2>{_esc(s.benchmark)}{src} "
            f"<span class='muted'>variant={_esc(s.variant)} &middot; answer-model={_esc(s.model)}</span></h2>"
            f"<div class='prog'>{bar}</div>"
            f"<table><thead><tr><th>arm</th><th>done</th><th>acc</th><th>in_tok</th><th>out_tok</th></tr></thead>"
            f"<tbody>{arm_rows}</tbody></table>{lift}{feed_block}</div>"
        )
    ingest_rows = _ingest_rows_html(ingests or [], total_items)
    body = ingest_rows + "".join(rows)
    if not body:
        body = "<p class='muted'>No ingest manifest or scoring checkpoints yet.</p>"

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
 .snips{{max-height:260px;overflow:auto;margin-top:3px}}
 .snip{{padding:4px 8px;margin:3px 0;border-left:3px solid #2f5a8f;background:#0f1620;border-radius:3px;
   font-size:12.5px;color:#adbac7;white-space:pre-wrap;overflow-wrap:anywhere}}
 .snip:nth-child(even){{background:#131c28}}
 .snum{{display:inline-block;min-width:22px;color:#d29922;font-weight:bold}}
 .viewer{{border:1px solid #30363d;border-radius:12px;padding:18px;margin:28px 0 12px;max-width:1060px;
   background:linear-gradient(145deg,#101722,#0d1117 48%);box-shadow:0 12px 40px #0005}}
 .viewer-head{{display:flex;justify-content:space-between;gap:28px;align-items:end}}
 .viewer-head h2{{font-size:20px;margin:2px 0 4px}} .viewer-copy{{max-width:650px;margin:0}}
 .eyebrow{{color:#58a6ff;font-size:11px;letter-spacing:.12em;font-weight:bold}}
 .viewer-picker{{display:grid;grid-template-columns:auto auto;gap:6px;min-width:390px}}
 .viewer-picker label{{grid-column:1/-1;color:#8b949e;font-size:11px;text-transform:uppercase}}
 select,button{{font:inherit;color:#c9d1d9;background:#161b22;border:1px solid #30363d;border-radius:6px;padding:7px 9px}}
 button{{cursor:pointer}} button:hover:not(:disabled){{border-color:#58a6ff;background:#1b2636}}
 button:disabled{{cursor:default;opacity:.4}} .viewer-picker select{{min-width:280px;max-width:420px}}
 #scalar-status{{margin:14px 0 8px}} .task-hero{{display:flex;justify-content:space-between;gap:20px;
   align-items:start;padding:14px;border:1px solid #30363d;border-radius:8px;background:#0d1117}}
 .task-hero span,.answer-question>span,.gold span,.answer-source span{{display:block;color:#8b949e;
   font-size:10px;letter-spacing:.09em;text-transform:uppercase}}
 .task-hero h3{{font:600 17px/1.4 ui-sans-serif,system-ui;margin:4px 0}} .task-id{{color:#d29922;white-space:nowrap}}
 .stage-nav{{display:flex;align-items:stretch;margin:16px 0;overflow-x:auto}}
 .stage{{display:flex;text-align:left;gap:8px;align-items:center;flex:1;min-width:118px;padding:10px;border-radius:8px}}
 .stage.active{{border-color:#58a6ff;background:#12233a;box-shadow:inset 0 0 0 1px #58a6ff44}}
 .stage-num{{display:grid;place-items:center;width:24px;height:24px;border-radius:50%;background:#21262d;color:#58a6ff}}
 .stage strong,.stage small{{display:block}} .stage small{{color:#8b949e;margin-top:2px}} .stage-arrow{{padding:15px 4px;color:#484f58}}
 .stage-panel{{min-height:300px;border-top:1px solid #30363d;padding-top:14px}}
 .stage-intro{{display:flex;justify-content:space-between;gap:20px;align-items:start;margin-bottom:12px}}
 .stage-intro h3,.answer-grid h3{{margin:0 0 4px;font-size:15px}} .stage-intro p{{margin:0;max-width:720px;color:#8b949e}}
 code{{color:#79c0ff}} .toggle{{white-space:nowrap;color:#8b949e}} .toggle input{{accent-color:#1f6feb}}
 .transcript{{display:grid;gap:7px;max-height:520px;overflow:auto;padding-right:5px}}
 .turn{{border:1px solid #21262d;border-left:3px solid #30363d;border-radius:6px;padding:8px 10px;background:#0d1117}}
 .turn.founded{{border-left-color:#3fb950;background:#0e1b15}} .turn-meta{{display:flex;gap:10px;color:#8b949e;font-size:11px}}
 .turn-meta b{{color:#d2a8ff;text-transform:uppercase}} .turn-text{{font:13px/1.5 ui-sans-serif,system-ui;margin-top:3px}}
 .founds{{margin-top:7px;color:#3fb950;font-size:10px;letter-spacing:.06em}} .founds span{{margin-left:8px;
   padding:2px 6px;border:1px solid #2ea04366;border-radius:10px;letter-spacing:0}}
 .fact-list{{max-height:260px;overflow:auto;padding-left:20px}} .fact-list li{{margin:5px 0}}
 .fact-list span{{display:block;color:#8b949e}} .receipt,.mono-id{{color:#8b949e;font-size:11px}}
 .gate-card{{border:1px solid #30363d;border-left:4px solid #f85149;border-radius:8px;padding:12px;margin:8px 0;background:#0d1117}}
 .gate-card.accepted{{border-left-color:#3fb950}} .gate-title{{display:flex;gap:10px;align-items:center;margin-bottom:9px}}
 .gate-title>span:last-child{{color:#8b949e}} .pill{{font-size:9px;letter-spacing:.08em;padding:2px 6px;border-radius:10px;background:#21262d}}
 .accepted .pill{{color:#3fb950}} .rejected .pill{{color:#f85149}} .vote-row{{max-width:760px;margin:7px 0}}
 .vote-row>div:first-child{{display:flex;justify-content:space-between;gap:12px}} .vote-bar{{height:5px;background:#21262d;border-radius:3px;overflow:hidden}}
 .vote-bar i{{display:block;height:100%;background:#58a6ff}} .warning,.pending{{border:1px solid #d2992266;background:#2d220d;
   color:#e3b341;border-radius:6px;padding:10px}} .assertions{{display:grid;gap:9px}}
 .assertion{{display:grid;grid-template-columns:34px 1fr;gap:8px;border:1px solid #30363d;border-radius:8px;padding:12px;background:#0d1117}}
 .assertion-num{{display:grid;place-items:center;width:26px;height:26px;border-radius:50%;background:#1f6feb;color:white}}
 .assertion-value{{display:flex;gap:8px;align-items:center;flex-wrap:wrap}} .assertion-value strong{{color:#79c0ff;font-size:16px}}
 blockquote{{margin:7px 0;color:#e6edf3;font:italic 14px/1.5 ui-serif,Georgia}} .chips{{display:flex;gap:5px;flex-wrap:wrap;margin:7px 0}}
 .chips span{{font-size:10px;padding:2px 6px;border:1px solid #30363d;border-radius:10px;color:#8b949e}}
 .views{{display:flex;align-items:stretch;overflow-x:auto;padding-bottom:6px}} .view-card{{min-width:240px;flex:1;border:1px solid #30363d;
   border-top:4px solid #6e7681;border-radius:8px;padding:14px;background:#0d1117}} .view-card.current{{border-top-color:#3fb950;background:#0e1b15}}
 .view-state{{color:#8b949e;font-size:10px;letter-spacing:.1em}} .current .view-state{{color:#3fb950}}
 .view-value{{font-size:34px;color:#79c0ff;font-weight:bold;margin:4px 0}} .view-card p{{color:#8b949e}}
 .supersede{{display:grid;place-items:center;min-width:135px;color:#d29922;text-align:center}}
 .answer-grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px}} .answer-question{{border:1px solid #30363d;border-radius:8px;padding:16px;background:#0d1117}}
 .answer-question h3{{font:600 19px/1.5 ui-sans-serif,system-ui;margin:6px 0 16px}} .gold{{border-top:1px solid #30363d;padding-top:10px}}
 .gold b{{font-size:22px;color:#3fb950}} .answer-source{{border:1px solid #2ea04366;border-radius:7px;padding:10px;margin:6px 0;background:#0e1b15}}
 .answer-source b{{display:block;color:#79c0ff;margin-top:3px}} .score-wrap{{grid-column:1/-1}} .score{{border:1px solid #30363d;border-radius:7px;padding:10px}}
 .score.okbox{{border-left:4px solid #3fb950}} .score.nobox{{border-left:4px solid #f85149}} .score pre{{white-space:pre-wrap}}
 .empty{{color:#8b949e;font-style:italic}} .stage-controls{{display:flex;justify-content:space-between;align-items:center;margin-top:12px}}
 @media (max-width:800px){{.viewer-head,.stage-intro{{display:block}}.viewer-picker{{margin-top:12px;min-width:0}}
   .stage-arrow{{display:none}}.answer-grid{{grid-template-columns:1fr}}.viewer-picker select{{min-width:0}}}}
 footer{{color:#8b949e;margin-top:18px;max-width:900px}}
</style></head><body>
<h1>archolith-bench &mdash; memory benchmark</h1>
<div id="content">
<div class="muted">{time.strftime('%Y-%m-%d %H:%M:%S')} &middot; live (every {refresh_s}s, in place)</div>
<div style="margin:10px 0">{mh}</div>
{body}
</div>
{_scalar_viewer_shell(scalar_default_namespace) if scalar_viewer_enabled else ""}
<footer>Token columns are ANSWER-model only; menhir ingestion (OpenAI extraction+embedding)
spend is not tracked by the bench. Progress is by item-count across arms.</footer>
<script>
// In-place refresh: fetch the page, swap only #content, and preserve which <details>
// are open plus the scroll position -- so expanding a question is NOT reset every tick.
const RS = {refresh_s} * 1000;
async function tick() {{
  try {{
    const html = await (await fetch(location.href, {{cache: 'no-store'}})).text();
    const fresh = new DOMParser().parseFromString(html, 'text/html').getElementById('content');
    if (!fresh) return;
    // preserve: which questions are open, page scroll, and each retrieved-memory box's scroll
    const openIds = new Set(
      Array.from(document.querySelectorAll('details[open]')).map(d => d.id).filter(Boolean)
    );
    const innerScroll = {{}};
    document.querySelectorAll('.keepscroll[id]').forEach(el => {{
      if (el.scrollTop > 0) innerScroll[el.id] = el.scrollTop;
    }});
    const sy = window.scrollY;
    document.getElementById('content').replaceWith(fresh);
    fresh.querySelectorAll('details[id]').forEach(d => {{ d.open = openIds.has(d.id); }});
    fresh.querySelectorAll('.keepscroll[id]').forEach(el => {{
      if (innerScroll[el.id] != null) el.scrollTop = innerScroll[el.id];
    }});
    window.scrollTo(0, sy);
  }} catch (e) {{ /* transient fetch error; try again next tick */ }}
}}
setInterval(tick, RS);
</script>
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
    scalar_reader: object | None = None,
    scalar_default_namespace: str | None = None,
) -> None:
    """Serve the dashboard as an auto-refreshing web page until interrupted."""
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from urllib.parse import parse_qs, urlparse

    from .scalar_viewer import scoring_rows, task_catalog

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):  # silence access logs
            pass

        def _send(self, status: int, data: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(data)

        def _json(self, status: int, payload: dict) -> None:
            self._send(
                status,
                json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8"),
                "application/json; charset=utf-8",
            )

        def do_GET(self):  # noqa: N802
            route = urlparse(self.path)
            snaps = scan_runs(results_dir, active_within_s=active_within_s)
            ingests = scan_ingests(results_dir, active_within_s=active_within_s)
            catalog = task_catalog(ingests)
            if route.path == "/api/scalar-tasks":
                graph_warning = None
                if scalar_reader is not None:
                    try:
                        available = scalar_reader.available_namespaces()
                        catalog = [
                            item for item in catalog if item["namespace"] in available
                        ]
                    except Exception as exc:  # noqa: BLE001 - catalog remains useful if graph is down
                        graph_warning = f"Could not filter tasks against the scalar graph: {exc}"
                default = scalar_default_namespace
                namespaces = {item["namespace"] for item in catalog}
                if default not in namespaces:
                    default = catalog[0]["namespace"] if catalog else None
                self._json(200, {
                    "tasks": catalog,
                    "default_namespace": default,
                    "reader_enabled": scalar_reader is not None,
                    "graph_warning": graph_warning,
                })
                return
            if route.path == "/api/scalar-task":
                if scalar_reader is None:
                    self._json(503, {"error": "The dashboard was not started with scalar graph access."})
                    return
                namespace = (parse_qs(route.query).get("namespace") or [""])[0]
                task = next((item for item in catalog if item["namespace"] == namespace), None)
                if task is None:
                    self._json(404, {"error": "Unknown or incomplete manifest namespace."})
                    return
                try:
                    payload = scalar_reader.read(namespace)
                except Exception as exc:  # noqa: BLE001 - read-only explorer must return a useful error
                    self._json(502, {"error": f"Could not read the scalar graph: {exc}"})
                    return
                payload["task"] = task
                payload["scoring"] = scoring_rows(snaps, task["question_id"])
                self._json(200, payload)
                return
            if route.path not in ("/", ""):
                self._json(404, {"error": "Not found."})
                return
            menhir = probe_menhir(menhir_url) if menhir_url else None
            page = render_html(
                snaps,
                menhir,
                total_items=total_items,
                refresh_s=refresh_s,
                items_n=items_n,
                ingests=ingests,
                scalar_viewer_enabled=scalar_reader is not None,
                scalar_default_namespace=scalar_default_namespace,
            )
            data = page.encode("utf-8")
            self._send(200, data, "text/html; charset=utf-8")

    server = ThreadingHTTPServer((host, port), Handler)
    print(f"dashboard serving at http://{host}:{port}  (Ctrl-C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n(dashboard stopped)")
        server.shutdown()
    finally:
        close = getattr(scalar_reader, "close", None)
        if close:
            close()


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
