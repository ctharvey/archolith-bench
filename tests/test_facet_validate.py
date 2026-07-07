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
    assert stats["memories"] >= 50  # grows as distractors are added during hardening
    assert stats["queries"] >= 20
    assert stats["stale_memories"] >= 1
    assert set(stats["repos"]) == {"menhir", "archolith-bench"}
    assert stats["vague_queries"], "draft must include the embedding-should-win vague case"
    assert stats["multi_support_queries"], "draft must exercise support_sufficiency"
    assert "historical" in stats["query_intents"]
    # the draft is intentionally left for manual hardening, so it SHOULD carry quality
    # warnings; they must all be the hardening categories, never a malformed-structure error.
    assert not report.errors


def test_uncontested_warning_names_query_and_missing_family() -> None:
    fx = FacetFixture(
        name="x", description="",
        memories=[_mem("good", repo="menhir", symbol={"unique_sym"}, belief_bucket="current")],
        queries=[Query("q1", "q", MemoryFacetSet(repo="menhir", symbol={"unique_sym"}),
                       support_ids=["good"], intent="current")],
    )
    warns = " ".join(validate_fixture(fx).warnings)
    assert "uncontested current query q1" in warns
    assert "stale" in warns and "wrong-repo" in warns  # names the missing families


def test_contested_query_not_flagged_uncontested() -> None:
    fx = FacetFixture(
        name="x", description="",
        memories=[_mem("good", repo="menhir", symbol={"s"}, belief_bucket="current"),
                  _mem("distractor", repo="archolith-bench", symbol={"s"}, belief_bucket="current")],
        queries=[Query("q1", "q", MemoryFacetSet(repo="menhir", symbol={"s"}),
                       support_ids=["good"], intent="current")],
    )
    assert not any("uncontested" in w for w in validate_fixture(fx).warnings)


def test_paraphrase_near_copy_warns_but_real_paraphrase_does_not() -> None:
    support = _mem("s", "menhir source aware floor gates only vector candidates exempting bm25", repo="menhir")
    fake = Query("qf", "menhir source aware floor gates only vector candidates", support_ids=["s"], paraphrase_group="g")
    real = Query("qr", "why do weak results get dropped from ranking", support_ids=["s"], paraphrase_group="g")
    fx = FacetFixture(name="x", description="", memories=[support], queries=[fake, real])
    warns = validate_fixture(fx).warnings
    assert any("paraphrase query qf" in w and "near-copy" in w for w in warns)
    assert not any("paraphrase query qr" in w for w in warns)


def test_labelled_vague_with_facets_warns() -> None:
    fx = FacetFixture(
        name="x", description="",
        memories=[_mem("m1", repo="menhir", symbol={"s"})],
        queries=[Query("q1", "q", MemoryFacetSet(repo="menhir", symbol={"s"}),
                       support_ids=["m1"], note="vague: embedding should win")],
    )
    warns = " ".join(validate_fixture(fx).warnings)
    assert "labelled vague" in warns and "repo" in warns and "symbol" in warns


def test_multi_support_domination_and_redundancy() -> None:
    # one support facet-dominates -> warn
    dom = FacetFixture(
        name="x", description="",
        memories=[_mem("s1", "alpha", symbol={"a"}), _mem("s2", "beta", symbol={"b"})],
        queries=[Query("q1", "q", MemoryFacetSet(symbol={"a"}), support_ids=["s1", "s2"])],
    )
    assert any("one support already covers" in w for w in validate_fixture(dom).warnings)

    # differentiated facets, distinct text -> no multi-support warning
    diff = FacetFixture(
        name="x", description="",
        memories=[_mem("s1", "alpha text about ingest scanning", symbol={"a"}),
                  _mem("s2", "beta text about anchoring links", symbol={"b"})],
        queries=[Query("q1", "q", MemoryFacetSet(symbol={"a", "b"}), support_ids=["s1", "s2"])],
    )
    assert not any("multi-support query q1" in w for w in validate_fixture(diff).warnings)

    # differentiated facets but near-duplicate text -> redundancy warn
    dup = FacetFixture(
        name="x", description="",
        memories=[_mem("s1", "identical body text here", symbol={"a"}),
                  _mem("s2", "identical body text here", symbol={"b"})],
        queries=[Query("q1", "q", MemoryFacetSet(symbol={"a", "b"}), support_ids=["s1", "s2"])],
    )
    assert any("near-duplicate text" in w for w in validate_fixture(dup).warnings)
