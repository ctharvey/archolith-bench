"""Tests for anchor-noise + hygiene corpus transforms (gate-b regime)."""

from __future__ import annotations

from archolith_bench.facet.anchor_noise import (
    BOILERPLATE_FILES,
    AnchorHygieneConfig,
    AnchorNoiseConfig,
    apply_anchor_hygiene,
    inject_anchor_noise,
)
from archolith_bench.facet.models import Memory, MemoryFacetSet


def _mem(mid: str, text: str, files=(), symbols=(), repo="menhir", bucket="current") -> Memory:
    return Memory(
        id=mid, text=text,
        facets=MemoryFacetSet(file=set(files), symbol=set(symbols), repo=repo, belief_bucket=bucket),
    )


def _corpus() -> list[Memory]:
    return [
        _mem("m1", "fixed the recall_service floor via source_aware_floor",
             files=["src/menhir/services/recall_service.py"], symbols=["source_aware_floor"]),
        _mem("m2", "added weighted_rrf rank fusion in hybrid_retrieval",
             files=["src/menhir/services/hybrid_retrieval.py"], symbols=["weighted_rrf"]),
        _mem("m3", "belief gate suppresses stale memories",
             files=["src/menhir/domain/belief.py"], symbols=["AnergicBeliefGate"]),
    ]


def test_inject_raises_anchor_count_toward_target_and_preserves_true() -> None:
    corpus = _corpus()
    out = inject_anchor_noise(corpus, AnchorNoiseConfig(target_anchors=9, seed=1))
    for orig, noised in zip(corpus, out):
        orig_total = len(orig.facets.file) + len(orig.facets.symbol)
        total = len(noised.facets.file) + len(noised.facets.symbol)
        # spurious added (the tiny 3-file/3-symbol pool saturates via dedup, so the
        # count lands below target here; the 52-memory fixture reaches ~8.7 as measured).
        assert total > orig_total
        # true anchors preserved (drop=0)
        assert orig.facets.file <= noised.facets.file
        assert orig.facets.symbol <= noised.facets.symbol


def test_inject_is_deterministic() -> None:
    a = inject_anchor_noise(_corpus(), AnchorNoiseConfig(seed=7))
    b = inject_anchor_noise(_corpus(), AnchorNoiseConfig(seed=7))
    assert [m.facets.to_dict() for m in a] == [m.facets.to_dict() for m in b]


def test_inject_does_not_mutate_input_or_scope() -> None:
    corpus = _corpus()
    before = [m.facets.to_dict() for m in corpus]
    out = inject_anchor_noise(corpus, AnchorNoiseConfig())
    assert [m.facets.to_dict() for m in corpus] == before  # input untouched
    for m in out:
        assert m.facets.repo == "menhir"                    # scope untouched by noise
        assert m.facets.belief_bucket == "current"


def test_true_drop_removes_true_anchors() -> None:
    corpus = _corpus()
    out = inject_anchor_noise(corpus, AnchorNoiseConfig(true_drop_frac=1.0, seed=3))
    # every original true file/symbol is gone (only spurious remain)
    for orig, noised in zip(corpus, out):
        assert not (orig.facets.file & noised.facets.file)
        assert not (orig.facets.symbol & noised.facets.symbol)


def test_hygiene_text_support_keeps_supported_drops_unsupported() -> None:
    m = _mem("m1", "fixed the recall_service floor via source_aware_floor",
             files=["src/menhir/services/recall_service.py", "pyproject.toml"],
             symbols=["source_aware_floor", "UnrelatedThing"])
    out = apply_anchor_hygiene([m], AnchorHygieneConfig(mode="text_support"))[0]
    assert "src/menhir/services/recall_service.py" in out.facets.file  # 'recall_service' in text
    assert "pyproject.toml" not in out.facets.file                     # boilerplate, unsupported
    assert "source_aware_floor" in out.facets.symbol
    assert "UnrelatedThing" not in out.facets.symbol


def test_hygiene_boilerplate_drops_boilerplate_files() -> None:
    m = _mem("m1", "some text", files=["real/thing.py", BOILERPLATE_FILES[0]])
    out = apply_anchor_hygiene([m], AnchorHygieneConfig(mode="boilerplate"))[0]
    assert "real/thing.py" in out.facets.file
    assert BOILERPLATE_FILES[0] not in out.facets.file


def test_hygiene_cap_limits_anchor_count() -> None:
    m = _mem("m1", "text", files=[f"f{i}.py" for i in range(8)])
    out = apply_anchor_hygiene([m], AnchorHygieneConfig(mode="cap", cap_k=3))[0]
    assert len(out.facets.file) == 3
