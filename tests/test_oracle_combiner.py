"""Tests for the one-pass oracle combiners (weighted E and log-space F)."""

from __future__ import annotations

from archolith_bench.oracle.combiner import (
    MAX_FAMILY_CONTRIBUTION,
    LogSpaceOracleCombiner,
    WeightedOracleCombiner,
)
from archolith_bench.oracle.executor import OracleExecutor
from archolith_bench.oracle.models import (
    OracleMemory,
    OraclePolarity,
    OracleResult,
    OracleTarget,
    QueryContext,
)
from archolith_bench.oracle.oracles import default_oracles


def _grouped(query: QueryContext, memories: list[OracleMemory]):
    ex = OracleExecutor(default_oracles())
    return ex.evaluate(query, [m.to_candidate() for m in memories])


def _support(probability=1.0, family="semantic", target=OracleTarget.RELEVANCE):
    return OracleResult("o", probability=probability, source_family=family, target=target,
                        polarity=OraclePolarity.SUPPORT)


def _rank_index(ranked: list[str], cid: str) -> int:
    return ranked.index(cid)


def test_logspace_suppresses_wrong_scope_below_in_scope() -> None:
    q = QueryContext(text="reciprocal rank fusion bm25", intent="current", as_of_time="2026-06-01", repo="menhir")
    in_scope = OracleMemory("good", text="reciprocal rank fusion bm25", repo="menhir", evidence_kinds={"git"})
    wrong_scope = OracleMemory("bad", text="reciprocal rank fusion bm25", repo="other", evidence_kinds={"git"})
    ranked, _ = LogSpaceOracleCombiner().rank(q, _grouped(q, [in_scope, wrong_scope]))
    assert _rank_index(ranked, "good") < _rank_index(ranked, "bad")


def test_logspace_suppresses_stale_under_current_intent() -> None:
    q = QueryContext(text="similarity floor value", intent="current", as_of_time="2026-06-01", repo="menhir")
    live = OracleMemory("live", text="similarity floor value", repo="menhir", belief_bucket="current", evidence_kinds={"git"})
    stale = OracleMemory("stale", text="similarity floor value", repo="menhir", superseded=True, evidence_kinds={"git"})
    ranked, _ = LogSpaceOracleCombiner().rank(q, _grouped(q, [live, stale]))
    assert _rank_index(ranked, "live") < _rank_index(ranked, "stale")


def test_logspace_preserves_historical_under_historical_intent() -> None:
    q = QueryContext(text="old project name", intent="historical", as_of_time="2026-06-01", repo="menhir")
    hist = OracleMemory("hist", text="old project name", repo="menhir", belief_bucket="historical", evidence_kinds={"git"})
    noise = OracleMemory("noise", text="unrelated tree config", repo="menhir", belief_bucket="current")
    ranked, _ = LogSpaceOracleCombiner().rank(q, _grouped(q, [hist, noise]))
    assert _rank_index(ranked, "hist") < _rank_index(ranked, "noise")


def test_structure_recovers_buried_memory() -> None:
    # near-zero lexical overlap, but shared symbol+test -> structure should rank it first
    q = QueryContext(text="willow plant bounds regression", intent="current", as_of_time="2026-06-01",
                     repo="menhir", symbols=("TreeWillow",), tests=("test_plant_bounds",))
    buried = OracleMemory("buried", text="combat extended immature growth limits", repo="menhir",
                          symbols={"TreeWillow"}, tests={"test_plant_bounds"}, evidence_kinds={"git"})
    lexical = OracleMemory("lexical", text="willow plant bounds regression notes", repo="menhir",
                           belief_bucket="current")
    ranked, _ = LogSpaceOracleCombiner().rank(q, _grouped(q, [buried, lexical]))
    assert "buried" in ranked[:2]


def test_combined_probabilities_form_distribution() -> None:
    q = QueryContext(text="similarity floor", intent="current", as_of_time="2026-06-01", repo="menhir")
    mems = [OracleMemory(f"m{i}", text="similarity floor", repo="menhir", evidence_kinds={"git"}) for i in range(4)]
    ranked, packets = LogSpaceOracleCombiner().rank(q, _grouped(q, mems))
    total = sum(packets[cid].combined_probability for cid in ranked)
    assert abs(total - 1.0) < 1e-9


def test_logspace_is_deterministic() -> None:
    q = QueryContext(text="similarity floor bm25", intent="current", as_of_time="2026-06-01", repo="menhir")
    mems = [OracleMemory(f"m{i}", text=f"similarity floor {i}", repo="menhir") for i in range(5)]
    g = _grouped(q, mems)
    assert LogSpaceOracleCombiner().rank(q, g)[0] == LogSpaceOracleCombiner().rank(q, g)[0]


def test_family_contribution_is_capped() -> None:
    # A flood of same-family support must not exceed the per-family cap.
    q = QueryContext(text="x")
    flood = {"c": [_support(probability=1.0, family="semantic") for _ in range(20)]}
    _, packets = LogSpaceOracleCombiner().rank(q, flood)
    assert packets["c"].role_logits["relevant"] <= MAX_FAMILY_CONTRIBUTION + 1e-9


def test_independence_downweights_duplicate_family() -> None:
    q = QueryContext(text="x")
    # two results, same family vs two results, different families: diff families score higher
    same = {"c": [_support(family="semantic"), _support(family="semantic")]}
    diff = {"c": [_support(family="semantic"), _support(family="structure")]}
    z_same = LogSpaceOracleCombiner().rank(q, same)[1]["c"].role_logits["relevant"]
    z_diff = LogSpaceOracleCombiner().rank(q, diff)[1]["c"].role_logits["relevant"]
    assert z_diff > z_same


def test_weighted_combiner_ranks_and_scores() -> None:
    q = QueryContext(text="similarity floor", intent="current", as_of_time="2026-06-01", repo="menhir")
    live = OracleMemory("live", text="similarity floor", repo="menhir", belief_bucket="current", evidence_kinds={"git"})
    stale = OracleMemory("stale", text="similarity floor", repo="menhir", superseded=True, evidence_kinds={"git"})
    ranked, packets = WeightedOracleCombiner().rank(q, _grouped(q, [live, stale]))
    assert ranked[0] == "live"
    assert "score" in packets["live"].role_logits
