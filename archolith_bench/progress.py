"""Reusable bench-run progress reporting.

The bench scripts (``run_r1_dummy``, ``run_facet_bench``, the ladder runners) loop
over hundreds of conditions x queries and, until now, printed nothing until they
finished — a live recall run looked hung for ten minutes. This module gives them a
sane, shared heartbeat. (Distinct from the ``archolith_bench.harness`` package, which
wraps *external* benchmark adapters; this is just the run-progress primitive.)

Design:

* **Progress goes to STDERR** so it stays visible when stdout is piped to a file /
  ``tee`` (the JSON artifact + result table stay clean on stdout).
* **Throttled + flushed** — at most one update per ``min_interval`` seconds, always
  flushed, so it is a heartbeat, not a flood, and shows up immediately.
* **TTY-aware** — a terminal gets a single ``\\r``-updated line; a pipe/redirect gets
  one line per tick (so ``tee`` / a logfile captures the trail).
* **Rate + ETA** — ``i/total pct%  elapsed  rate/s  eta`` plus an optional per-tick
  ``detail`` (e.g. the current condition).
* **Stdlib only** — imports in CI with no deps; drop-in for sync and async loops.

Primitives:

* :class:`ProgressReporter` — the engine; call ``advance()`` per unit (works in async
  loops too), or use it as a context manager.
* :func:`track` — wrap any iterable, tqdm-style, for a sync loop.
* :func:`run_ladder` — the common ``conditions x items`` bench loop with progress.
"""

from __future__ import annotations

import sys
import time
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from typing import TextIO, TypeVar

__all__ = ["ProgressReporter", "track", "run_ladder", "format_duration"]

C = TypeVar("C")
IT = TypeVar("IT")
R = TypeVar("R")


def format_duration(seconds: float) -> str:
    """Human-friendly duration: ``4.2s``, ``1m03s``, ``2h05m``."""
    seconds = max(0.0, float(seconds))
    if seconds < 60:
        return f"{seconds:.1f}s"
    if seconds < 3600:
        m, s = divmod(int(seconds), 60)
        return f"{m}m{s:02d}s"
    h, rem = divmod(int(seconds), 3600)
    m = rem // 60
    return f"{h}h{m:02d}m"


class ProgressReporter:
    """Throttled, flushed, stderr progress for long bench loops.

    Call :meth:`advance` once per completed unit of work; call :meth:`close` (or use
    the context manager) to emit the final 100% line. Safe in async loops — it does no
    I/O of its own beyond the throttled writes. Set ``enabled=False`` to make every
    call a no-op (quiet / CI).
    """

    def __init__(
        self,
        total: int,
        *,
        label: str = "bench",
        stream: TextIO | None = None,
        min_interval: float = 0.5,
        enabled: bool = True,
        logfile: str | None = None,
    ) -> None:
        self.total = max(0, int(total))
        self.label = label
        self.stream = stream if stream is not None else sys.stderr
        self.min_interval = max(0.0, float(min_interval))
        self.enabled = enabled
        self.logfile = logfile
        self.count = 0
        self._start = time.perf_counter()
        # Seed to _start (not 0.0): perf_counter's origin is arbitrary/large, so a 0.0
        # seed would make the first advance always exceed any interval. Seeding to _start
        # makes the throttle measure real elapsed time from construction.
        self._last_emit = self._start
        self._detail = ""
        self._pad = 0
        self._closed = False
        self._tty = bool(getattr(self.stream, "isatty", lambda: False)())

    # -- public API ---------------------------------------------------------
    def advance(self, n: int = 1, *, detail: str = "") -> None:
        """Record ``n`` completed units; emit a throttled update if due."""
        if not self.enabled:
            return
        self.count += n
        if detail:
            self._detail = detail
        now = time.perf_counter()
        # Intermediate emits only below 100%; close() owns the single final line
        # (prevents a duplicate final when the last advance coincides with a tick).
        if self.count < self.total and now - self._last_emit >= self.min_interval:
            self._emit(final=False)

    def close(self) -> None:
        """Emit the final line (100% if fully advanced) exactly once."""
        if not self.enabled or self._closed:
            return
        self._closed = True
        self._emit(final=True)

    def __enter__(self) -> ProgressReporter:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- internals ----------------------------------------------------------
    def _emit(self, *, final: bool) -> None:
        now = time.perf_counter()
        elapsed = now - self._start
        frac = (self.count / self.total) if self.total else 1.0
        rate = self.count / elapsed if elapsed > 0 else 0.0
        remaining = max(0, self.total - self.count)
        eta = (remaining / rate) if (rate > 0 and not final) else 0.0
        pct = int(frac * 100)
        line = (
            f"[{self.label}] {self.count}/{self.total} {pct:3d}%  "
            f"{format_duration(elapsed)}  {rate:.1f}/s  eta {format_duration(eta)}"
        )
        if self._detail:
            line += f"  {self._detail}"
        # Pad so a shorter line does not leave residue from a longer prior one.
        self._pad = max(self._pad, len(line))
        padded = line.ljust(self._pad)
        if self._tty:
            self.stream.write("\r" + padded + ("\n" if final else ""))
        else:
            self.stream.write(padded.rstrip() + "\n")
        self.stream.flush()
        if self.logfile:
            self._append_log(line)
        self._last_emit = now

    def _append_log(self, line: str) -> None:
        try:
            with open(self.logfile, "a", encoding="utf-8") as handle:
                ts = time.strftime("%Y-%m-%d %H:%M:%S")
                handle.write(f"[{ts}] {line}\n")
        except OSError:
            pass  # progress logging is best-effort; never break the run


def track(
    iterable: Iterable[IT],
    *,
    total: int | None = None,
    label: str = "bench",
    **kwargs: object,
) -> Iterator[IT]:
    """Yield items from ``iterable`` while reporting progress (tqdm-style, sync).

    ``total`` defaults to ``len(iterable)`` when available. Progress advances after
    each item is yielded (so it reflects *completed* work). Extra kwargs pass through
    to :class:`ProgressReporter` (``stream``, ``min_interval``, ``enabled``, ...).
    """
    if total is None:
        try:
            total = len(iterable)  # type: ignore[arg-type]
        except TypeError:
            total = 0
    reporter = ProgressReporter(total, label=label, **kwargs)  # type: ignore[arg-type]
    try:
        for item in iterable:
            yield item
            reporter.advance()
    finally:
        reporter.close()


def run_ladder(
    conditions: Mapping[str, C],
    items: Sequence[IT],
    run_one: Callable[[C, IT], R],
    *,
    label: str = "ladder",
    **kwargs: object,
) -> dict[str, list[R]]:
    """Run ``run_one(condition_ctx, item)`` for every (condition, item) with progress.

    Returns ``{condition_name: [R per item, in order]}``. The reporter's ``detail`` is
    the current condition name, so the heartbeat reads e.g.
    ``[ladder] 45/155  29%  12.3s  3.7/s  eta 29.7s  E_hybrid_a0``. ``run_one`` owns
    timing/metrics; this owns the loop + the heartbeat. For async work, drive
    :class:`ProgressReporter` directly inside your ``await`` loop instead.
    """
    total = len(conditions) * len(items)
    results: dict[str, list[R]] = {}
    with ProgressReporter(total, label=label, **kwargs) as reporter:  # type: ignore[arg-type]
        for name, ctx in conditions.items():
            row: list[R] = []
            for item in items:
                row.append(run_one(ctx, item))
                reporter.advance(detail=name)
            results[name] = row
    return results
