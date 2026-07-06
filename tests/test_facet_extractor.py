"""Tests for the deterministic facet extractor."""

from __future__ import annotations

from archolith_bench.facet.extractor import ExtractorConfig, FacetExtractor
from archolith_bench.facet.models import Memory, MemoryFacetSet


def test_extract_files_symbols_tests() -> None:
    ex = FacetExtractor()
    fs = ex.extract("Fixed recall_service.py so RetrievalConfig works; see test_recall_floor.")
    assert "recall_service.py" in fs.file
    assert "RetrievalConfig" in fs.symbol
    assert "test_recall_floor" in fs.test
    # test names are not double-counted as symbols
    assert "test_recall_floor" not in fs.symbol


def test_extract_snake_and_screaming_symbols() -> None:
    # snake_case + SCREAMING_SNAKE identifiers mentioned bare (not only as `foo(` calls)
    # are recovered — the common case in prose about code that PascalCase/call rules miss.
    ex = FacetExtractor()
    fs = ex.extract(
        "The source_aware_floor uses weighted_rrf; FLOOR_EXEMPT_SOURCES bypasses it."
    )
    assert "source_aware_floor" in fs.symbol
    assert "weighted_rrf" in fs.symbol
    assert "FLOOR_EXEMPT_SOURCES" in fs.symbol


def test_extract_operations_lemmatized() -> None:
    ex = FacetExtractor()
    assert "fix" in ex.extract("we fixed the bug").operation
    assert "add" in ex.extract("added a new path").operation
    assert "rename" in ex.extract("renamed the symbol").operation


def test_extract_belief_bucket_markers() -> None:
    ex = FacetExtractor()
    assert ex.extract("this is the old approach we used to take").belief_bucket == "historical"
    assert ex.extract("currently the floor is source-aware").belief_bucket == "current"
    assert ex.extract("a neutral statement about code").belief_bucket is None


def test_extract_scope_from_vocab() -> None:
    ex = FacetExtractor(ExtractorConfig(repos=("menhir", "archolith-bench")))
    assert ex.extract("the menhir recall path").repo == "menhir"
    assert ex.extract("a generic sentence").repo is None


def test_extract_iso_valid_time_and_objects() -> None:
    ex = FacetExtractor()
    fs = ex.extract("On 2026-06-20 we changed the `cosine threshold` behavior")
    assert fs.valid_time == "2026-06-20"
    assert "cosine threshold" in fs.object


def test_extract_is_deterministic() -> None:
    ex = FacetExtractor(ExtractorConfig(repos=("menhir",)))
    text = "Fixed menhir recall_service.py RetrievalConfig on 2026-06-20"
    assert ex.extract(text).to_dict() == ex.extract(text).to_dict()


def test_extract_memory_preserves_provenance_facets() -> None:
    ex = FacetExtractor()
    gold = Memory("m1", "fixed recall_service.py", MemoryFacetSet(source_id="commit:abc", learned_time="2026-06-01"))
    out = ex.extract_memory(gold)
    # source_id / learned_time are carried from gold, not invented by extraction.
    assert out.facets.source_id == "commit:abc"
    assert out.facets.learned_time == "2026-06-01"
    assert "recall_service.py" in out.facets.file


def test_hybrid_reads_deterministic_from_gold_interpretive_from_text() -> None:
    ex = FacetExtractor()
    gold = MemoryFacetSet(
        file={"a.py"}, symbol={"Foo"}, repo="menhir", valid_time="2026-01-01",
        object={"goldobj"}, operation={"add"},
    )
    mem = Memory("m1", "we refactored `realobj` in unrelated.py", gold)
    hy = ex.extract_memory_hybrid(mem).facets
    # deterministic facets come from gold (structure/Git), NOT regex over prose
    assert hy.file == {"a.py"}
    assert hy.symbol == {"Foo"}
    assert hy.repo == "menhir"
    assert hy.valid_time == "2026-01-01"
    # interpretive facets come from extraction (text), NOT gold
    assert "realobj" in hy.object
    assert "goldobj" not in hy.object
    assert "refactor" in hy.operation
    assert "add" not in hy.operation
