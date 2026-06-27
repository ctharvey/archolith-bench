"""Tests for the facet fixture validator."""

from __future__ import annotations

from pathlib import Path

from archolith_bench.facet.models import FacetFixture, Memory, MemoryFacetSet, Query
from archolith_bench.facet.validate import validate_fixture

DRAFT = Path(__file__).resolve().parent.parent / "fixtures" / "facet_r2_draft.json"
DEMO = Path(__file__).resolve().parent.parent / "fixtures" / "facet_demo.json"


def _mem(mid: str, text: str = "t", **facets) -> Memory:
    superseded = facets.pop("superseded", False)
    return Memory(mid, text, MemoryFacetSet(**facets), superseded=superseded)


def test_missing_support_id_is_error() -> None:
    fx = FacetFixture(name="x", description="", memories=[_mem("m1")],
                      queries=[Query("q1", "q", support_ids=["m2"])])
    report = validate_fixture(fx)
    assert not report.ok
    assert any("missing support id" in e for e in report.errors)


def test_duplicate_ids_and_bad_bucket_are_errors() -> None:
    fx = FacetFixture(name="x", description="",
                      memories=[_mem("m1"), _mem("m1", belief_bucket="bogus")],
                      queries=[Query("q1", "q", support_ids=["m1"])])
    report = validate_fixture(fx)
    assert not report.ok
    assert any("duplicate memory id" in e for e in report.errors)
    assert any("unknown belief_bucket" in e for e in report.errors)


def test_clean_fixture_warns_on_missing_families() -> None:
    # all-current, single-repo, no rename, no vague, no paraphrase, no stale
    fx = FacetFixture(
        name="clean", description="",
        memories=[_mem("m1", repo="menhir", symbol={"a"}, belief_bucket="current"),
                  _mem("m2", repo="menhir", symbol={"b"}, belief_bucket="current")],
        queries=[Query("q1", "q", MemoryFacetSet(repo="menhir", symbol={"a"}), support_ids=["m1"])],
    )
    report = validate_fixture(fx)
    assert report.ok  # runnable
    warns = " ".join(report.warnings)
    assert "no stale" in warns
    assert "symbol-rename case missing" in warns
    assert "vague query" in warns


def test_abstention_query_not_warned_for_empty_support() -> None:
    fx = FacetFixture(name="x", description="",
                      memories=[_mem("m1")],
                      queries=[Query("q1", "q", support_ids=[], note="abstention case")])
    report = validate_fixture(fx)
    assert not any("no support_ids" in w for w in report.warnings)


def test_demo_fixture_is_runnable() -> None:
    report = validate_fixture(FacetFixture.from_file(DEMO))
    assert report.ok


def test_draft_fixture_passes_and_has_required_families() -> None:
    report = validate_fixture(FacetFixture.from_file(DRAFT))
    assert report.ok, report.errors
    stats = report.stats
    assert stats["memories"] == 50
    assert stats["queries"] == 20
    assert stats["stale_memories"] >= 1
    assert set(stats["repos"]) == {"menhir", "archolith-bench"}
    assert stats["vague_queries"], "draft must include the embedding-should-win vague case"
    assert stats["multi_support_queries"], "draft must exercise support_sufficiency"
    assert "historical" in stats["query_intents"]
    # no 'too clean' / missing-family warnings except the tolerated uncontested-query note
    for warn in report.warnings:
        assert "uncontested" in warn, f"unexpected quality warning: {warn}"
