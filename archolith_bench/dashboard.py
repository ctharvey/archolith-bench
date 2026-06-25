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
                       mtime=path.stat().st_mtime if path.exists() else 0.0)
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
    return snap


def scan_runs(results_dir: Path) -> list[RunSnapshot]:
    if not results_dir.exists():
        return []
    snaps = [read_checkpoint(p) for p in sorted(results_dir.glob(".checkpoint_*.jsonl"))]
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
        lines.append(f"  {s.benchmark}  variant={s.variant}  answer-model={s.model}")
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


def run_dashboard(
    results_dir: Path,
    *,
    menhir_url: str | None = None,
    interval: float = 5.0,
    once: bool = False,
    total_items: int | None = None,
) -> None:
    prev_done: int | None = None
    prev_t: float | None = None
    rate_per_min: float | None = None
    eta_min: float | None = None
    while True:
        snaps = scan_runs(results_dir)
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
