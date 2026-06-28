"""Benchmark-local oracle pipeline (menhir R4-R7, bench-first).

Implements the *retrieval-altitude* oracle layer from menhir's
`docs/research/oracle-amplified-retrieval.md` and the runtime contract in
`oracle-runtime-interfaces.md`, as a falsifiable bench prototype. Like the facet
package this is self-contained inside archolith-bench: R4-R7 are build-first rungs,
but nothing here is wired into menhir production.

Pieces (all pure Python, deterministic, explainable):
- `models`    — QueryContext/CandidateMemory/OracleResult/OraclePacket + fixture model.
- `oracles`   — cheap RetrievalOracles (Semantic/Structure/Scope/Temporal/Evidence).
- `executor`  — bounded, deterministic OracleExecutor.
- `combiner`  — WeightedOracleCombiner (E) and LogSpaceOracleCombiner (F, the R7 baseline).
- `metrics`   — recall/precision/MRR/NDCG + stale-hit / wrong-scope / current-truth
                suppression / historical preservation / ranking determinism.
- `runner`    — condition ladder A_semantic / E_weighted / F_logspace + promotion gate.
"""

from __future__ import annotations

from .combiner import LogSpaceOracleCombiner, WeightedOracleCombiner
from .executor import OracleExecutor
from .models import (
    CandidateMemory,
    OracleFixture,
    OracleMemory,
    OraclePacket,
    OraclePolarity,
    OracleQuery,
    OracleResult,
    OracleTarget,
    QueryContext,
    Role,
)
from .oracles import (
    EvidenceOracle,
    RetrievalOracle,
    ScopeOracle,
    SemanticOracle,
    StructureOracle,
    TemporalOracle,
    default_oracles,
)
from .runner import OracleBenchmarkRunner, evaluate_promotion_gate, run_ablation

__all__ = [
    "CandidateMemory",
    "EvidenceOracle",
    "LogSpaceOracleCombiner",
    "OracleBenchmarkRunner",
    "OracleExecutor",
    "OracleFixture",
    "OracleMemory",
    "OraclePacket",
    "OraclePolarity",
    "OracleQuery",
    "OracleResult",
    "OracleTarget",
    "QueryContext",
    "Role",
    "RetrievalOracle",
    "ScopeOracle",
    "SemanticOracle",
    "StructureOracle",
    "TemporalOracle",
    "WeightedOracleCombiner",
    "default_oracles",
    "evaluate_promotion_gate",
    "run_ablation",
]
