"""Benchmark-local R3 ladder — belief buckets + currentness policy.

R3 (menhir research ladder) tests whether the intent-aware currentness policy
(menhir.domain.belief.build_intent_aware_packet) reduces stale-current assertions
and poisoned context vs an honest baseline, WITHOUT losing historical context —
the CE-willow belief-drift failure (belief-layer.md).

Repo-split discipline: this package lives in archolith-bench and consumes menhir's
belief domain as a LIBRARY (it does not reimplement the policy, so the bench stays
the falsifiable spec for menhir's real behavior). Pure-stdlib otherwise; runs in CI
given menhir-frontier/src on the path.
"""
