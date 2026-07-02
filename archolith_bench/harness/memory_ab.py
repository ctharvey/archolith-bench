"""Mode-B driver: persistent-memory benchmarks via ingest-then-recall.

Unlike `run_ab` (history in-context) this exercises a real memory system. Per
question item, for each memory arm: isolate a fresh `group_id`, ingest the
haystack sessions, recall against the question, feed the recalled memory (not the
raw history) to the chat model, and score. The advertisable claim is the
memory-QA accuracy lift from the no-memory baseline to memory-recall.

The memory backend is abstracted behind `MenhirClient` so offline tests use a
deterministic in-memory stub (no Neo4j); real runs point at a throwaway
menhir+Neo4j (never production — `assert_not_production` guards the target).
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from contextlib import nullcontext
from statistics import mean
from typing import TYPE_CHECKING, Protocol, runtime_checkable

import httpx

if TYPE_CHECKING:
    from .checkpoint import MemoryCheckpoint

from ..core.api import API_KEY, MODEL, PROXY_URL, send_chat
from ..core.metrics import PricingModel, compute_arm_cost
from .base import ABResult, ArmResult, TaskResult, _compute_deltas, _pick_pricing, _usage_tokens
from .menhir_client import HttpMenhirClient

# Arms: a no-memory floor vs memory-recall arms.
NO_MEMORY = "no_memory"
DEFAULT_MEMORY_ARMS = (NO_MEMORY, "menhir_recall")

_PROD_MARKERS = ("prod", "production", "menhir.", "staging.", "preprod", "preview", "release")


@runtime_checkable
class MenhirClient(Protocol):
    """Minimal memory backend the Mode-B driver needs (stub or HTTP)."""

    def new_group(self) -> str:
        """Return a fresh isolated namespace id for one benchmark item."""
        ...

    def ingest(self, group_id: str, role: str, content: str) -> None:
        """Ingest one conversation turn into the memory store under group_id."""
        ...

    def recall(self, group_id: str, query: str, limit: int = 10) -> list[str]:
        """Return recalled memory snippets for the query, scoped to group_id."""
        ...

    def reset(self, group_id: str) -> None:
        """Clear all memory for a group (best-effort cleanup)."""
        ...


@runtime_checkable
class MemoryQAAdapter(Protocol):
    """Adapter contract for an ingest-then-recall memory QA benchmark."""

    benchmark_id: str
    name: str

    def load_items(self, subset, limit, fixture_path) -> list[dict]: ...  # noqa: ANN001
    def sessions(self, item: dict) -> list[list[dict]]: ...
    def question(self, item: dict) -> str:  ...
    def build_messages(self, memory_context: str, question: str) -> list[dict]: ...
    def score(self, item: dict, response_text: str) -> bool: ...


def assert_not_production(target: str) -> None:
    """Refuse to run a write-heavy benchmark against anything that looks prod."""
    low = (target or "").lower()
    if any(m in low for m in _PROD_MARKERS):
        raise SystemExit(
            f"REFUSING: memory benchmark target {target!r} looks like production. "
            "Point --menhir-url at a throwaway instance."
        )


def _run_memory_arm(
    adapter: MemoryQAAdapter,
    arm: str,
    items: Sequence[dict],
    *,
    client: MenhirClient | None,
    chat_client: httpx.Client,
    send_fn,
    chat_base_url: str,
    api_key: str,
    model: str,
    recall_limit: int,
    pricing: PricingModel,
    reset_memory: bool,
    reset_confirmed: bool,
    dry_run_reset: bool,
    recall_only: bool = False,
    namespace_template: str = "lme-{question_id}",
    checkpoint: "MemoryCheckpoint | None" = None,
    score_fn=None,  # noqa: ANN001
) -> ArmResult:
    results: list[TaskResult] = []
    turn_dicts: list[dict] = []
    for i, item in enumerate(items):
        task_id = str(item.get("question_id") or f"item-{i}")
        # Resume: if this (arm, item) was already scored in a prior run, reuse it and
        # skip re-ingesting its haystack -- the expensive, abort-prone part.
        if checkpoint is not None:
            cached = checkpoint.get(arm, task_id)
            if cached is not None:
                results.append(cached)
                turn_dicts.append({"input_tokens": cached.input_tokens, "output_tokens": cached.output_tokens})
                continue
        question = adapter.question(item)
        if arm == NO_MEMORY or client is None:
            memory_context = ""
        elif recall_only:
            # Recall-only A/B: the graph is pre-built once in stable per-question
            # namespaces (e.g. lme-<question_id>), so skip ingest AND reset entirely and
            # recall in place. No new_group, no mutation -> needs no --confirm-menhir-reset.
            group_id = namespace_template.format(question_id=item.get("question_id") or task_id)
            recalled = client.recall(group_id, question, limit=recall_limit)
            memory_context = "\n".join(recalled)
        else:
            group_id = client.new_group()
            try:
                for session in adapter.sessions(item):
                    for turn in session:
                        client.ingest(group_id, turn.get("role", "user"), turn.get("content", ""))
                recalled = client.recall(group_id, question, limit=recall_limit)
                memory_context = "\n".join(recalled)
            finally:
                if reset_memory:
                    _reset_memory_group(
                        client,
                        group_id,
                        reset_confirmed=reset_confirmed,
                        dry_run_reset=dry_run_reset,
                    )
        messages = adapter.build_messages(memory_context, question)
        text, latency_ms, usage = send_fn(chat_client, chat_base_url, api_key, messages, model)
        inp, out = _usage_tokens(usage)
        correct = score_fn(item, text) if score_fn is not None else adapter.score(item, text)
        tr = TaskResult(
            task_id=task_id,
            response_text=text,
            input_tokens=inp,
            output_tokens=out,
            latency_ms=latency_ms,
            correct=correct,
            raw_usage=usage,
        )
        results.append(tr)
        turn_dicts.append({"input_tokens": inp, "output_tokens": out})
        # Persist immediately so a later crash/rate-limit abort keeps this item.
        if checkpoint is not None:
            checkpoint.record(arm, task_id, tr)

    score = mean(1.0 if r.correct else 0.0 for r in results) if results else 0.0
    arm_cost = compute_arm_cost(turn_dicts, pricing)
    return ArmResult(
        arm=arm,
        n=len(results),
        score=round(score, 4),
        input_tokens=sum(r.input_tokens for r in results),
        output_tokens=sum(r.output_tokens for r in results),
        cost_usd=round(arm_cost.total_effective_cost_usd, 6),
        results=results,
    )


def run_memory_ab(
    adapter: MemoryQAAdapter,
    *,
    arms: Sequence[str] = DEFAULT_MEMORY_ARMS,
    subset: str | None = None,
    limit: int | None = None,
    fixture_path=None,  # noqa: ANN001
    client: MenhirClient | None = None,
    send_fn=send_chat,  # noqa: ANN001
    chat_base_url: str = PROXY_URL,
    api_key: str = API_KEY,
    model: str = MODEL,
    # MSC sweep knob: override the recall top-k via env so accuracy-vs-context can be
    # measured without a CLI change. Default 10 preserves prior behavior when unset.
    recall_limit: int = int(os.getenv("LME_RECALL_LIMIT", "10")),
    pricing: PricingModel | None = None,
    reset_memory: bool = True,
    reset_confirmed: bool = False,
    dry_run_reset: bool = False,
    recall_only: bool = False,
    namespace_template: str = "lme-{question_id}",
    checkpoint: "MemoryCheckpoint | None" = None,
    score_fn=None,  # noqa: ANN001
) -> ABResult:
    """Run an ingest-then-recall memory benchmark across arms.

    `no_memory` answers with an empty memory context (the floor); memory arms
    ingest+recall via `client`. Offline: pass `fixture_path` and a stub `client`
    + deterministic `send_fn`. Real runs require a throwaway menhir client.

    `checkpoint`: optional MemoryCheckpoint. When given, each item's result is
    persisted as it completes and already-recorded items are skipped, so a long run
    survives crashes and rate-limit aborts (rerun the same command to resume).

    `score_fn`: optional `(item, response_text) -> bool` override for grading (e.g. an
    LLMJudgeScorer for LongMemEval-comparable accuracy). Defaults to `adapter.score`
    (the offline containment scorer). If it exposes `.close()`, it is closed on exit.
    """
    items = adapter.load_items(subset, limit, fixture_path)
    pricing = _pick_pricing(model, pricing)
    needs_client = any(a != NO_MEMORY for a in arms)
    if needs_client and client is None:
        raise ValueError("memory arms require a MenhirClient (got None)")
    if recall_only:
        # Recall-only A/B reads a pre-built graph in place: never ingest, never reset.
        # This also makes --confirm-menhir-reset unnecessary (the guard below keys on
        # reset_memory, which we force off here).
        reset_memory = False
    if (
        needs_client
        and isinstance(client, HttpMenhirClient)
        and reset_memory
        and not reset_confirmed
        and not dry_run_reset
    ):
        raise ValueError(
            "memory benchmarks with a real Menhir client require --confirm-menhir-reset "
            "or --dry-run-menhir-reset before any ingest occurs"
        )

    arm_results: dict[str, ArmResult] = {}
    memory_client_cm = client if hasattr(client, "__enter__") and hasattr(client, "__exit__") else nullcontext(client)
    try:
        with httpx.Client(timeout=300) as chat_client:
            with memory_client_cm:
                for arm in arms:
                    arm_client = None if arm == NO_MEMORY else client
                    arm_results[arm] = _run_memory_arm(
                        adapter,
                        arm,
                        items,
                        client=arm_client,
                        chat_client=chat_client,
                        send_fn=send_fn,
                        chat_base_url=chat_base_url,
                        api_key=api_key,
                        model=model,
                        recall_limit=recall_limit,
                        pricing=pricing,
                        reset_memory=reset_memory,
                        reset_confirmed=reset_confirmed,
                        dry_run_reset=dry_run_reset,
                        recall_only=recall_only,
                        namespace_template=namespace_template,
                        checkpoint=checkpoint,
                        score_fn=score_fn,
                    )
    finally:
        if score_fn is not None and hasattr(score_fn, "close"):
            score_fn.close()

    # Deltas vs the no_memory floor (memory lift), reusing the shared helper by
    # aliasing no_memory as the baseline.
    baseline = arm_results.get(NO_MEMORY)
    deltas: dict[str, dict] = {}
    if baseline is not None:
        aliased = {"direct" if k == NO_MEMORY else k: v for k, v in arm_results.items()}
        deltas = _compute_deltas(aliased)

    return ABResult(
        benchmark_id=adapter.benchmark_id,
        name=adapter.name,
        model=model,
        subset=subset,
        arms=arm_results,
        deltas=deltas,
    )


def _reset_memory_group(
    client: MenhirClient,
    group_id: str,
    *,
    reset_confirmed: bool,
    dry_run_reset: bool,
) -> None:
    """Reset a memory group with explicit safety for real HTTP Menhir clients."""
    if dry_run_reset:
        print(f"  [memory] dry-run: would reset group {group_id}")
        return
    if isinstance(client, HttpMenhirClient) and not reset_confirmed:
        raise RuntimeError(
            "Refusing to reset a real Menhir group without confirmation. "
            "Pass --confirm-menhir-reset for cleanup or --dry-run-menhir-reset to inspect."
        )
    client.reset(group_id)
