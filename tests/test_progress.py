"""Offline tests for the reusable bench progress reporter."""

from __future__ import annotations

import io

from archolith_bench.progress import (
    ProgressReporter,
    format_duration,
    run_ladder,
    track,
)


# --- format_duration -------------------------------------------------------


def test_format_duration_scales() -> None:
    assert format_duration(4.2) == "4.2s"
    assert format_duration(63) == "1m03s"
    assert format_duration(2 * 3600 + 5 * 60) == "2h05m"
    assert format_duration(-5) == "0.0s"  # clamped, never negative


# --- ProgressReporter ------------------------------------------------------


def test_reporter_final_line_shows_completion() -> None:
    out = io.StringIO()
    rep = ProgressReporter(5, label="R1", stream=out, min_interval=0.0)
    for _ in range(5):
        rep.advance()
    rep.close()
    text = out.getvalue()
    assert "[R1]" in text
    assert "5/5" in text
    assert "100%" in text


def test_reporter_throttles_intermediate_updates() -> None:
    out = io.StringIO()
    # A huge interval suppresses every intermediate emit; only close() emits.
    rep = ProgressReporter(5, label="x", stream=out, min_interval=9999)
    for _ in range(5):
        rep.advance()
    rep.close()
    lines = [ln for ln in out.getvalue().splitlines() if ln.strip()]
    assert len(lines) == 1
    assert "5/5" in lines[0] and "100%" in lines[0]


def test_reporter_disabled_is_silent() -> None:
    out = io.StringIO()
    rep = ProgressReporter(3, stream=out, enabled=False, min_interval=0.0)
    for _ in range(3):
        rep.advance()
    rep.close()
    assert out.getvalue() == ""


def test_reporter_detail_and_rate_present() -> None:
    out = io.StringIO()
    rep = ProgressReporter(2, label="lad", stream=out, min_interval=0.0)
    rep.advance(detail="E_hybrid_a0")
    rep.advance(detail="E_hybrid_a0")
    rep.close()
    text = out.getvalue()
    assert "E_hybrid_a0" in text
    assert "/s" in text  # rate
    assert "eta" in text


def test_reporter_context_manager_closes() -> None:
    out = io.StringIO()
    with ProgressReporter(2, stream=out, min_interval=0.0) as rep:
        rep.advance()
        rep.advance()
    assert "2/2" in out.getvalue()


def test_reporter_zero_total_is_safe() -> None:
    out = io.StringIO()
    rep = ProgressReporter(0, stream=out, min_interval=0.0)
    rep.close()  # no division-by-zero
    assert "0/0" in out.getvalue()


def test_reporter_non_tty_emits_one_line_per_tick() -> None:
    out = io.StringIO()  # StringIO has no isatty -> treated as a pipe
    rep = ProgressReporter(3, stream=out, min_interval=0.0)
    for _ in range(3):
        rep.advance()
    rep.close()
    # newline-terminated lines (no bare carriage-return overwrite in pipe mode)
    assert "\r" not in out.getvalue()
    assert len([ln for ln in out.getvalue().splitlines() if ln.strip()]) >= 3


# --- track -----------------------------------------------------------------


def test_track_yields_all_items_and_reports() -> None:
    out = io.StringIO()
    seen = list(track([10, 20, 30], label="t", stream=out, min_interval=0.0))
    assert seen == [10, 20, 30]
    assert "3/3" in out.getvalue()


def test_track_infers_total_from_len() -> None:
    out = io.StringIO()
    list(track(["a", "b"], label="t", stream=out, min_interval=0.0))
    assert "2/2" in out.getvalue()


# --- run_ladder ------------------------------------------------------------


def test_run_ladder_structure_and_calls() -> None:
    out = io.StringIO()
    conditions = {"A": 1, "B": 10}
    items = [2, 3]
    calls: list[tuple[int, int]] = []

    def run_one(ctx: int, item: int) -> int:
        calls.append((ctx, item))
        return ctx * item

    results = run_ladder(
        conditions, items, run_one, label="lad", stream=out, min_interval=0.0
    )
    assert results == {"A": [2, 3], "B": [20, 30]}
    assert calls == [(1, 2), (1, 3), (10, 2), (10, 3)]  # condition-major order
    assert "4/4" in out.getvalue()  # total = 2 conditions x 2 items
