"""Offline tests for the running-process / port index (pure functions; no PowerShell)."""

from __future__ import annotations

from archolith_bench.procindex import (
    KNOWN_PORTS,
    ProcEntry,
    _dedupe_by_port,
    _is_relevant,
    filter_relevant,
    label_for,
    render,
)


def test_label_for_known_port_wins():
    assert label_for(8101, "anything") == KNOWN_PORTS[8101]
    assert label_for(7688, "") == KNOWN_PORTS[7688]


def test_label_for_falls_back_to_cmdline():
    assert "serve-watch" in label_for(9999, "python -m menhir.cli serve-watch").lower()
    assert label_for(9999, "python -m menhir.cli serve") == "menhir serve"
    assert label_for(9999, "archolith-bench.exe dashboard --serve") == "archolith-bench dashboard"
    assert label_for(9999, "totally unrelated") == "?"


def test_dedupe_prefers_non_docker_owner():
    docker = ProcEntry(port=7688, pid=1, label="x", cmd="C:/.../com.docker.backend.exe")
    real = ProcEntry(port=7688, pid=2, label="x", cmd="java neo4j")
    out = _dedupe_by_port([docker, real])
    assert len(out) == 1
    assert out[0].pid == 2  # the non-docker owner won


def test_relevant_filter_excludes_unrelated():
    e_menhir = ProcEntry(port=9999, pid=1, label="menhir serve", cmd="python -m menhir.cli serve")
    e_other = ProcEntry(port=5555, pid=2, label="?", cmd="some-random-app.exe")
    assert _is_relevant(e_menhir.port, e_menhir.cmd)
    assert not _is_relevant(e_other.port, e_other.cmd)
    rel = filter_relevant([e_menhir, e_other])
    assert e_menhir in rel and e_other not in rel
    assert e_other in filter_relevant([e_menhir, e_other], show_all=True)


def test_render_smoke():
    entries = [ProcEntry(port=8101, pid=49020, label=KNOWN_PORTS[8101], cmd="menhir.exe serve --port 8101")]
    out = render(entries)
    assert "8101" in out
    assert "throwaway" in out
    assert "PORT" in out and "LABEL" in out
