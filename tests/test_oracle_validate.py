"""Tests for the oracle fixture validator (the silliness guardrail)."""

from __future__ import annotations

from pathlib import Path

from archolith_bench.oracle.models import OracleFixture, OracleMemory, OracleQuery
from archolith_bench.oracle.validate import has_errors, validate_oracle_fixture

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def _codes(findings) -> set[str]:
    return {f.code for f in findings}


def _fixture(memories, queries) -> OracleFixture:
    return OracleFixture("t", "t", memories, queries)


def test_real_fixtures_validate_clean() -> None:
    for name in ("oracle_demo", "oracle_hard", "oracle_correlated"):
        findings = validate_oracle_fixture(OracleFixture.from_file(FIXTURES / f"{name}.json"))
        assert not has_errors(findings), f"{name}: {[str(x) for x in findings]}"
        assert findings == [], f"{name} should be silliness-free: {[str(x) for x in findings]}"


def test_dangling_support_is_error() -> None:
    fx = _fixture([OracleMemory("m1", text="a", belief_bucket="current")],
                  [OracleQuery("q1", text="a", support_ids=["nope"])])
    assert "DANGLING-SUPPORT" in _codes(validate_oracle_fixture(fx))


def test_stale_gold_under_current_is_error() -> None:
    fx = _fixture(
        [OracleMemory("m1", text="floor cosine", superseded=True, belief_bucket="historical"),
         OracleMemory("m2", text="floor source aware", belief_bucket="current")],
        [OracleQuery("q1", text="floor", intent="current", support_ids=["m1"])],
    )
    assert "STALE-GOLD" in _codes(validate_oracle_fixture(fx))


def test_anachronistic_gold_is_error() -> None:
    fx = _fixture(
        [OracleMemory("m1", text="future fact", created_at="2026-09-01", belief_bucket="current"),
         OracleMemory("m2", text="future fact distractor", belief_bucket="current")],
        [OracleQuery("q1", text="future fact", intent="current", as_of_time="2026-06-01", support_ids=["m1"])],
    )
    assert "ANACHRONISTIC-GOLD" in _codes(validate_oracle_fixture(fx))


def test_bad_bucket_and_date_order_are_errors() -> None:
    fx = _fixture(
        [OracleMemory("m1", text="x", belief_bucket="bogus", valid_at="2026-05-01", invalid_at="2026-01-01")],
        [OracleQuery("q1", text="x", support_ids=["m1"])],
    )
    codes = _codes(validate_oracle_fixture(fx))
    assert "BAD-BUCKET" in codes
    assert "DATE-ORDER" in codes


def test_uncontested_query_is_warning() -> None:
    fx = _fixture(
        [OracleMemory("m1", text="unique alpha topic", belief_bucket="current"),
         OracleMemory("m2", text="completely different beta subject", belief_bucket="current")],
        [OracleQuery("q1", text="unique alpha topic", intent="current", support_ids=["m1"])],
    )
    assert "UNCONTESTED" in _codes(validate_oracle_fixture(fx))


def test_thin_scope_is_warning() -> None:
    mems = [OracleMemory("m1", text="lease", repo="maint", belief_bucket="current")]
    mems += [OracleMemory(f"o{i}", text="other", repo="menhir", belief_bucket="current") for i in range(5)]
    fx = _fixture(mems, [OracleQuery("q1", text="lease", intent="current", repo="maint", support_ids=["m1"])])
    assert "THIN-SCOPE" in _codes(validate_oracle_fixture(fx))


def test_no_stale_is_warning() -> None:
    fx = _fixture(
        [OracleMemory("m1", text="floor topic", belief_bucket="current"),
         OracleMemory("m2", text="floor topic other", belief_bucket="current")],
        [OracleQuery("q1", text="floor topic", intent="current", support_ids=["m1"])],
    )
    assert "NO-STALE" in _codes(validate_oracle_fixture(fx))


def test_no_scope_var_is_warning() -> None:
    fx = _fixture(
        [OracleMemory("m1", text="topic one", repo="menhir", belief_bucket="current"),
         OracleMemory("m2", text="topic one stale", repo="menhir", superseded=True, belief_bucket="historical")],
        [OracleQuery("q1", text="topic one", intent="current", repo="menhir", support_ids=["m1"])],
    )
    assert "NO-SCOPE-VAR" in _codes(validate_oracle_fixture(fx))
