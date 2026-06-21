"""Temporary directory hardening tests."""

from __future__ import annotations

from archolith_bench.harness.tempfiles import secure_temporary_directory


def test_secure_temporary_directory_is_writable_and_ephemeral():
    with secure_temporary_directory() as path:
        assert path.exists()
        marker = path / "marker.txt"
        marker.write_text("ok", encoding="utf-8")
        assert marker.read_text(encoding="utf-8") == "ok"

    assert not path.exists()
