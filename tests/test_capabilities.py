"""Tests for the capability evidence registry."""

from __future__ import annotations

import json

from archolith_bench.core.capabilities import CAPABILITIES, STATUS_VALUES, capabilities_json, write_capabilities


def test_capability_registry_covers_required_products() -> None:
    products = {c.product for c in CAPABILITIES}

    assert {
        "menhir",
        "archolith-context",
        "archolith-filter",
        "archolith-mcp-audit",
        "archolith-security",
    }.issubset(products)


def test_capability_registry_covers_menhir_ladders() -> None:
    abilities = {c.ability for c in CAPABILITIES if c.product == "menhir"}

    assert {
        "persistent memory QA",
        "belief/currentness",
        "facet retrieval",
        "oracle combiner",
        "intent-aware retrieval",
        "institutional artifact memory",
        "structure-temporal blast radius",
    }.issubset(abilities)


def test_capability_statuses_are_valid() -> None:
    assert all(c.status in STATUS_VALUES for c in CAPABILITIES)


def test_capabilities_json_filter() -> None:
    data = capabilities_json(product="menhir")

    assert data["total"] >= 1
    assert {row["product"] for row in data["capabilities"]} == {"menhir"}


def test_write_capabilities_json(tmp_path) -> None:
    out = write_capabilities(tmp_path / "capabilities.json", product="menhir")
    data = json.loads(out.read_text(encoding="utf-8"))

    assert data["suite"] == "capabilities"
    assert data["total"] >= 1
