"""Tests for the write-sensitive graph fingerprint (no live Neo4j; a stub session)."""

from __future__ import annotations

import pytest

from archolith_bench.r1.graph_fingerprint import (
    WRITE_SENSITIVE_PROBES,
    GraphWriteFingerprint,
    assert_no_writes,
    graph_write_fingerprint,
)


class _StubSession:
    """Returns canned rows per probe name, keyed by a substring of its cypher."""

    def __init__(self, rows_by_probe: dict[str, list[dict]]) -> None:
        self.rows_by_probe = rows_by_probe

    def run(self, cypher: str):
        for name, cypher_text in WRITE_SENSITIVE_PROBES:
            if cypher_text == cypher:
                return list(self.rows_by_probe.get(name, []))
        raise AssertionError(f"unexpected cypher: {cypher}")


def _rows(**overrides) -> dict[str, list[dict]]:
    base = {
        "node_last_accessed": [
            {"k": "u1", "v": "2026-07-14T10:00:00Z"},
            {"k": "u2", "v": "2026-07-14T11:00:00Z"},
        ],
        "node_edge_count": [{"k": "u1", "v": "5"}, {"k": "u2", "v": "3"}],
        "node_freshness": [{"k": "u1", "v": "ACTIVE"}, {"k": "u2", "v": "ACTIVE"}],
        "node_rehydration_count": [{"k": "u1", "v": "0"}, {"k": "u2", "v": "0"}],
        "edge_weight": [{"k": "e1", "v": "1.0"}],
    }
    base.update(overrides)
    return base


def test_identical_graph_yields_identical_fingerprint() -> None:
    before = graph_write_fingerprint(_StubSession(_rows()))
    after = graph_write_fingerprint(_StubSession(_rows()))
    assert before.drift(after) == []
    assert_no_writes(before, after)  # must not raise


def test_last_accessed_touch_is_detected() -> None:
    """The exact mutation update_access=True performs: SET n.last_accessed = datetime()."""
    before = graph_write_fingerprint(_StubSession(_rows()))
    after = graph_write_fingerprint(
        _StubSession(
            _rows(
                node_last_accessed=[
                    {"k": "u1", "v": "2026-07-14T12:00:00Z"},  # touched
                    {"k": "u2", "v": "2026-07-14T11:00:00Z"},
                ]
            )
        )
    )
    assert before.drift(after) == ["node_last_accessed"]
    with pytest.raises(AssertionError, match="MUTATED the graph"):
        assert_no_writes(before, after)


def test_edge_weight_increment_is_detected() -> None:
    """The other update_access mutation: SET r.weight on traversed edges."""
    before = graph_write_fingerprint(_StubSession(_rows()))
    after = graph_write_fingerprint(_StubSession(_rows(edge_weight=[{"k": "e1", "v": "2.0"}])))
    assert before.drift(after) == ["edge_weight"]
    with pytest.raises(AssertionError):
        assert_no_writes(before, after)


def test_edge_count_resync_is_detected() -> None:
    """Catches prepare_memory_runtime() being called on the clone (it runs sync_edge_counts)."""
    before = graph_write_fingerprint(_StubSession(_rows()))
    after = graph_write_fingerprint(
        _StubSession(_rows(node_edge_count=[{"k": "u1", "v": "0"}, {"k": "u2", "v": "0"}]))
    )
    assert before.drift(after) == ["node_edge_count"]
    with pytest.raises(AssertionError, match="sync_edge_counts"):
        assert_no_writes(before, after)


def test_offsetting_changes_are_detected_where_a_sum_would_miss_them() -> None:
    """The reason this is a hash and not sum(last_accessed).

    One node moves +1h and another -1h. The SUM of the timestamps is unchanged, so a
    sum-based fingerprint would report "no writes" while the graph was in fact mutated.
    A per-entity hash catches it.
    """
    before = graph_write_fingerprint(
        _StubSession(
            _rows(
                node_last_accessed=[
                    {"k": "u1", "v": "2026-07-14T10:00:00Z"},
                    {"k": "u2", "v": "2026-07-14T12:00:00Z"},
                ]
            )
        )
    )
    after = graph_write_fingerprint(
        _StubSession(
            _rows(
                node_last_accessed=[
                    {"k": "u1", "v": "2026-07-14T11:00:00Z"},  # +1h
                    {"k": "u2", "v": "2026-07-14T11:00:00Z"},  # -1h  (sum unchanged)
                ]
            )
        )
    )
    assert before.drift(after) == ["node_last_accessed"]


def test_value_swap_between_nodes_is_detected() -> None:
    """Identity is part of the hash: swapping two nodes' values is still a mutation."""
    before = graph_write_fingerprint(_StubSession(_rows()))
    after = graph_write_fingerprint(
        _StubSession(
            _rows(
                node_last_accessed=[
                    {"k": "u1", "v": "2026-07-14T11:00:00Z"},  # u1 and u2 swapped
                    {"k": "u2", "v": "2026-07-14T10:00:00Z"},
                ]
            )
        )
    )
    assert before.drift(after) == ["node_last_accessed"]


def test_null_is_distinct_from_the_literal_string_none() -> None:
    """A NULL property must not collide with a caller-written 'None' string."""
    with_null = graph_write_fingerprint(
        _StubSession(_rows(node_freshness=[{"k": "u1", "v": None}, {"k": "u2", "v": "ACTIVE"}]))
    )
    with_none_str = graph_write_fingerprint(
        _StubSession(_rows(node_freshness=[{"k": "u1", "v": "None"}, {"k": "u2", "v": "ACTIVE"}]))
    )
    assert with_null.hashes["node_freshness"] != with_none_str.hashes["node_freshness"]


def test_multiple_surfaces_drift_together() -> None:
    before = graph_write_fingerprint(_StubSession(_rows()))
    after = graph_write_fingerprint(
        _StubSession(
            _rows(
                node_last_accessed=[{"k": "u1", "v": "X"}, {"k": "u2", "v": "Y"}],
                edge_weight=[{"k": "e1", "v": "9.0"}],
            )
        )
    )
    assert before.drift(after) == ["edge_weight", "node_last_accessed"]


def test_fingerprint_covers_every_update_access_write_surface() -> None:
    """Guard: update_access=True writes last_accessed, edge weight, and rehydration state.
    prepare_memory_runtime additionally writes edge_count. All must be probed."""
    probed = {name for name, _ in WRITE_SENSITIVE_PROBES}
    assert {
        "node_last_accessed",
        "edge_weight",
        "node_rehydration_count",
        "node_freshness",
        "node_edge_count",
    } <= probed


def test_absent_surface_counts_as_drift() -> None:
    a = GraphWriteFingerprint(hashes={"node_last_accessed": "abc", "edge_weight": "def"})
    b = GraphWriteFingerprint(hashes={"node_last_accessed": "abc"})
    assert b.drift(a) == ["edge_weight"]
