"""Benchmark-local R5 — StructureTemporalOracle (time-aware blast radius).

Tests whether ranking a failing anchor's structural dependencies by what CHANGED in the
time window beats a structure-only baseline that can't tell what changed when. Consumes
menhir.domain.structure_temporal (the real oracle), per the repo-split rule.
"""
