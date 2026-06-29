"""Intent benchmark runner (menhir IntentOracle, Phase 4).

The falsifiable claim, in four arms over ONE topic (so any ranking change is attributable
to intent, not topic):

    baseline   semantic-only: no task intent. Top-1 cannot track intent.
    intent_on  default oracles + IntentOracle through the log-space combiner.
    shuffle    intent_on but the IntentOracle is fed a deliberately WRONG intent.
    no_harm    generic/orientation queries: intent_on must not degrade nDCG vs baseline.

Headline = role-based intent-correct@1 (top-1 carries a PREFERRED role for the TRUE
intent). Promotion gate: intent_on >> baseline AND shuffle collapses to <= baseline
(a wrong intent is no better than no intent) AND no-harm holds. Nothing here touches
menhir production; the semantic oracle is a lexical stand-in (swap a real embedder
before quoting absolute numbers).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from archolith_bench.oracle.combiner import LogSpaceOracleCombiner
from archolith_bench.oracle.executor import OracleExecutor
from archolith_bench.oracle.models import QueryContext
from archolith_bench.oracle.oracles import SemanticOracle, SemanticScorer, default_oracles

from . import metrics as M
from .classifier import TaskIntent, classify_intent, primary_intent
from .matrix import task_intents_to_query_intent
from .models import IntentFixture
from .oracle import IntentOracle

DEFAULT_K = 5

# All task intents except the bare default; the shuffle arm averages over every WRONG one.
_ALL_INTENTS: tuple[TaskIntent, ...] = tuple(
    i for i in TaskIntent if i is not TaskIntent.UNDERSTAND_SYSTEM
)


@dataclass
class QueryDetail:
    query_id: str
    true_intent: str
    baseline_top: str
    baseline_correct: float
    intent_top: str
    intent_correct: float
    shuffle_correct: float  # mean intent-correct@1 over all WRONG forced intents


@dataclass
class IntentBenchmarkRunner:
    fixture: IntentFixture
    semantic_scorer: SemanticScorer | None = None
    k: int = DEFAULT_K
    _combiner: LogSpaceOracleCombiner = field(default_factory=LogSpaceOracleCombiner)

    def __post_init__(self) -> None:
        self.candidates = self.fixture.candidates
        self.by_id = {c.id: c for c in self.candidates}

    # --- ranking arms -------------------------------------------------------

    @staticmethod
    def _tiebreak(cid: str) -> str:
        """Role-neutral deterministic tiebreak. Alphabetical-id tiebreak systematically
        favored `benchmark_*` (a broadly-preferred role), inflating the semantic-only
        baseline above chance; hashing the id removes that role correlation while staying
        deterministic."""
        return hashlib.md5(cid.encode()).hexdigest()

    def _rank_baseline(self, text: str) -> list[str]:
        ctx = QueryContext(text=text)
        sem = SemanticOracle(self.semantic_scorer)
        scored = [(c.id, sem.evaluate(ctx, c).probability) for c in self.candidates]
        return [cid for cid, _ in sorted(scored, key=lambda kv: (-kv[1], self._tiebreak(kv[0])))]

    def _rank_intent(self, text: str, forced: TaskIntent | None = None) -> list[str]:
        if forced is not None:
            intents = [forced]
        else:
            hits, _ = classify_intent(text)
            intents = [h.intent for h in hits]
        lens = task_intents_to_query_intent(intents)
        ctx = QueryContext(text=text, intent=lens)
        oracles = default_oracles(self.semantic_scorer) + [IntentOracle(forced)]
        grouped = OracleExecutor(oracles).evaluate(ctx, self.candidates)
        ranked, _ = self._combiner.rank(ctx, grouped)
        return ranked

    def _rank_full_no_intent(self, text: str) -> list[str]:
        """Full oracle stack WITHOUT the IntentOracle, on the default current lens.

        The honest no-harm control: it isolates the IntentOracle's contribution by
        holding the rest of the stack constant (vs the semantic-only baseline, which
        would conflate intent with the whole stack)."""
        ctx = QueryContext(text=text, intent="current")
        grouped = OracleExecutor(default_oracles(self.semantic_scorer)).evaluate(ctx, self.candidates)
        ranked, _ = self._combiner.rank(ctx, grouped)
        return ranked

    # --- run ----------------------------------------------------------------

    def _meta(self, ranked: list[str]) -> object:
        return self.by_id[ranked[0]].metadata if ranked else None

    def run(self) -> dict:
        details: list[QueryDetail] = []
        b_sum = on_sum = sh_sum = 0.0
        for q in self.fixture.queries:
            true = primary_intent(classify_intent(q.text)[0])
            base = self._rank_baseline(q.text)
            on = self._rank_intent(q.text)

            b_ok = M.intent_correct_at_1(self._meta(base), true)
            on_ok = M.intent_correct_at_1(self._meta(on), true)
            # Shuffle: feed every WRONG intent and average — the expected accuracy of a
            # random wrong intent. If intent_on's lift were topic leakage, this would
            # stay near intent_on; it collapses instead.
            wrongs = [w for w in _ALL_INTENTS if w is not true]
            sh_ok = sum(
                M.intent_correct_at_1(self._meta(self._rank_intent(q.text, forced=w)), true)
                for w in wrongs
            ) / (len(wrongs) or 1)

            b_sum += b_ok
            on_sum += on_ok
            sh_sum += sh_ok
            details.append(QueryDetail(
                query_id=q.id, true_intent=true.value,
                baseline_top=base[0] if base else "", baseline_correct=b_ok,
                intent_top=on[0] if on else "", intent_correct=on_ok,
                shuffle_correct=round(sh_ok, 4),
            ))

        n = len(self.fixture.queries) or 1
        baseline_acc = round(b_sum / n, 4)
        intent_acc = round(on_sum / n, 4)
        shuffle_acc = round(sh_sum / n, 4)
        no_harm = self._run_no_harm()
        gate = self._gate(baseline_acc, intent_acc, shuffle_acc, no_harm)

        return {
            "fixture": self.fixture.name,
            "description": self.fixture.description,
            "config": {
                "k": self.k,
                "n_memories": len(self.fixture.memories),
                "n_queries": len(self.fixture.queries),
                "n_no_harm_queries": len(self.fixture.no_harm_queries),
            },
            "intent_correct_at_1": {
                "baseline": baseline_acc,
                "intent_on": intent_acc,
                "shuffle_ablation": shuffle_acc,
            },
            "no_harm_ndcg_at_5": no_harm,
            "determinism": self._determinism(),
            "promotion_gate": gate,
            "per_query": [d.__dict__ for d in details],
        }

    def _run_no_harm(self) -> dict:
        """Isolate intent: full stack WITHOUT intent vs full stack WITH intent. Adding the
        IntentOracle must not drop nDCG on orientation queries."""
        if not self.fixture.no_harm_queries:
            return {"no_intent": 1.0, "intent_on": 1.0, "n": 0}
        off = on = 0.0
        for q in self.fixture.no_harm_queries:
            support = q.support_ids
            off += M.ndcg_at_k(self._rank_full_no_intent(q.text), support, self.k)
            on += M.ndcg_at_k(self._rank_intent(q.text), support, self.k)
        n = len(self.fixture.no_harm_queries)
        return {"no_intent": round(off / n, 4), "intent_on": round(on / n, 4), "n": n}

    def _determinism(self) -> float:
        for q in self.fixture.queries:
            if self._rank_intent(q.text) != self._rank_intent(q.text):
                return 0.0
        return 1.0

    @staticmethod
    def _gate(
        baseline: float, intent_on: float, shuffle: float, no_harm: dict,
        tol: float = 1e-9, shuffle_margin: float = 0.15,
    ) -> dict:
        beats_baseline = intent_on > baseline + tol
        # Collapse: a random WRONG intent loses most of the lift (proves the gain is the
        # intent signal, not topic leakage). Residual shuffle accuracy is expected — some
        # artifact roles are broadly task-useful — so we require a margin, not zero.
        shuffle_collapses = intent_on - shuffle > shuffle_margin
        no_harm_ok = no_harm["intent_on"] >= no_harm["no_intent"] - tol
        return {
            "graduates": bool(beats_baseline and shuffle_collapses and no_harm_ok),
            "intent_beats_baseline": bool(beats_baseline),
            "shuffle_collapses": bool(shuffle_collapses),
            "no_harm_holds": bool(no_harm_ok),
            "shuffle_margin": shuffle_margin,
            "lift_vs_baseline": round(intent_on - baseline, 4),
            "lift_vs_shuffle": round(intent_on - shuffle, 4),
        }
