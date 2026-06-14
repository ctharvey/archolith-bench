"""Proxy suite: multi-turn session benchmark across experiment arms.

Ports the seed benchmark.py into the arm-aware architecture and adds
continuity tracking and restart/bootstrap scoring.

Continuity tracking (Step 3 from the original plan):
- ContinuityTracker: counts repeat file reads and diagnostics across turns,
  records decision retention and verification continuity at final turns.
- run_restart_bootstrap: replays a scenario, then starts a fresh conversation
  to score turn_one_orientation_score (does the model recover context without
  re-reading?).
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict
from pathlib import Path

import httpx

from ..arms import ARMS, PROXY_FAMILY_ARMS
from ..core.api import (
    API_KEY,
    DIRECT_URL,
    MODEL,
    PROXY_URL,
    get_proxy_trace,
    send_chat,
    set_proxy_budget,
    snapshot_proxy_config,
)
from ..core.display import COLLAPSE_TOKEN_THRESHOLD, print_cross_scenario_summary, print_summary
from ..core.metrics import (
    ContinuityMetrics,
    PricingModel,
    compute_arm_cost,
    compute_turn_cost,
    estimate_messages_tokens,
    estimate_tokens,
)
from ..core.report import save_results
from ..core.scenario import Scenario, build_turn_messages, is_tool_turn
from .checkpoints import checkpoint_path, load_checkpoint, save_checkpoint
from .continuity import ContinuityTracker
from .probes import run_fact_probes
from .restart import run_restart_bootstrap

COLLAPSE_CONSECUTIVE_LIMIT = 2


def _upstream_cache_split(usage: dict, prompt_tokens: int) -> tuple[int, int]:
    """Extract (cache_hit, cache_miss) from an upstream usage dict.

    DeepSeek reports prompt_cache_hit_tokens / prompt_cache_miss_tokens. When
    the hit key is present we trust it and derive miss from prompt_tokens if the
    miss key is absent. When neither key is present (provider doesn't report
    cache), returns (0, 0) -- the no-cache-telemetry signal, so the arm stays
    correctly marked as having no cache data.
    """
    if not usage or "prompt_cache_hit_tokens" not in usage:
        return 0, 0
    hit = usage.get("prompt_cache_hit_tokens", 0) or 0
    miss = usage.get("prompt_cache_miss_tokens")
    if miss is None:
        miss = max(0, prompt_tokens - hit)
    return hit, miss


def _compute_cost_summary(results: list[dict], pricing: PricingModel) -> dict:
    """Proxy-arm effective cost + passthrough (direct-arm) delta.

    ``results`` are per-turn dicts carrying ``trace`` (the proxy/arm trace, with
    cache breakdown) and ``direct`` (the passthrough arm's raw token counts).
    Returns the machine-readable cost fields persisted in the run summary so the
    go/no-go verdict (proxy cheaper or not) is queryable, not buried in markdown.

    The passthrough arm has no cache breakdown, so its cost falls back to the
    full input rate -- ``passthrough_cache_data_available`` flags that.
    """
    arm_cost = compute_arm_cost([r["trace"] for r in results], pricing)
    passthrough_cost = compute_arm_cost(
        [r["direct"] for r in results if "direct" in r], pricing
    )

    total = arm_cost.total_effective_cost_usd
    passthrough = passthrough_cost.total_effective_cost_usd
    delta = round(total - passthrough, 6)
    ratio = round(delta / passthrough, 6) if passthrough else 0.0

    return {
        "total_effective_cost_usd": total,
        "cache_data_available": arm_cost.cache_data_available,
        "upstream_input_cost": arm_cost.upstream_input_cost,
        "upstream_output_cost": arm_cost.upstream_output_cost,
        "helper_cost": arm_cost.helper_cost,
        "passthrough_effective_cost_usd": passthrough,
        "passthrough_cache_data_available": passthrough_cost.cache_data_available,
        "cost_delta_usd": delta,
        "cost_delta_vs_passthrough": delta,
        "cost_delta_ratio": ratio,
    }


# ---------------------------------------------------------------------------
# Main benchmark runner (arm-aware)
# ---------------------------------------------------------------------------

def run_benchmark(
    scenario: Scenario,
    arm: str,
    proxy_url: str,
    direct_url: str,
    model: str,
    budget: int | None = None,
    output_dir: Path = Path("results"),
    resume: bool = False,
    api_key: str = "",
    max_turns: int | None = None,
    run_probes: bool = True,
    run_restart: bool = True,
    pricing: PricingModel | None = None,
    collapse_abort: bool = True,
) -> dict:
    """Run the benchmark for a single scenario/arm/budget combination."""
    arm_def = ARMS.get(arm, ARMS["direct"])
    arm_label = arm_def["label"]
    arm_config = arm_def["config_overrides"]
    _key = api_key or API_KEY

    results: list[dict] = []
    probe_results: list[dict] = []
    direct_history: list[dict] = []
    arm_history: list[dict] = []
    # Pin a known session id for this run and send it as X-Session-ID on every proxy
    # call. The proxy honors X-Session-ID as the primary key, so the trace query reads
    # exactly this session instead of guessing sessions[0] (which read stale runs).
    proxy_session_id: str | None = f"bench-{scenario.name}-{arm}-{uuid.uuid4().hex[:12]}"
    start_turn = 0
    consecutive_collapses = 0
    tracker = ContinuityTracker()

    ckpt_path = checkpoint_path(output_dir, scenario.name, arm, budget)

    if resume:
        ckpt = load_checkpoint(ckpt_path)
        if ckpt and ckpt["scenario"] == scenario.name and ckpt.get("arm") == arm and ckpt.get("budget") == budget:
            results = ckpt["results"]
            probe_results = ckpt["probe_results"]
            direct_history = ckpt["direct_history"]
            arm_history = ckpt["arm_history"]
            proxy_session_id = ckpt.get("proxy_session_id")
            start_turn = len(results)
            print(f"  Resuming from turn {start_turn + 1}")

    if not direct_history:
        system_msg = {"role": "system", "content": scenario.system_prompt}
        direct_history.append(system_msg)
        arm_history.append(system_msg)

    turns = scenario.turns[:max_turns] if max_turns else scenario.turns

    with httpx.Client() as client:
        if budget:
            if set_proxy_budget(client, proxy_url, budget):
                print(f"  Budget set to {budget} tokens")
            else:
                print("  WARNING: Could not set budget via admin API")

        # Arm config is applied per-session via the X-Session-Config header on each
        # proxy chat call (see send_chat session_config=arm_config below), NOT via a
        # global PATCH /admin/config. This scopes the arm's overrides to this run's
        # session only, so concurrent arms/runs cannot clobber each other's config
        # and global config_overrides.json is never touched.
        if arm_config:
            print(f"  Arm config (per-session): {arm_config}")

        config_snapshot = snapshot_proxy_config(client, proxy_url)

        for i, turn in enumerate(turns, 1):
            if i <= start_turn:
                continue
            user_display = turn["user"] if isinstance(turn, dict) else turn
            turn_messages = build_turn_messages(turn)
            print(f"\n{'='*60}")
            print(f"  TURN {i}/{len(turns)}: {scenario.name} [{arm}]")
            print(f"  User: {user_display[:80]}...")
            print(f"{'='*60}")

            direct_history.extend(turn_messages)
            arm_history.extend(turn_messages)

            direct_est = estimate_messages_tokens(direct_history)
            arm_est = estimate_messages_tokens(arm_history)

            is_direct_arm = not arm_def["proxy_enabled"] and arm != "filter_only"
            is_filter_only = arm == "filter_only"

            if is_filter_only:
                from .filter import apply_filter_to_history
                arm_chat_history = apply_filter_to_history(arm_history)
                arm_est = estimate_messages_tokens(arm_chat_history)
            else:
                arm_chat_history = arm_history

            print(f"  [direct] Sending {len(direct_history)} messages (~{direct_est} tokens)...")
            direct_text, direct_latency, direct_usage = send_chat(
                client, direct_url, _key, direct_history, model
            )
            direct_input = direct_usage.get("prompt_tokens", direct_est)
            direct_output = direct_usage.get("completion_tokens", estimate_tokens(direct_text))
            print(f"  [direct] {direct_input} in / {direct_output} out in {direct_latency:.0f}ms")

            if is_filter_only:
                print(f"  [arm={arm}] Sending {len(arm_chat_history)} messages (~{arm_est} tokens, filter-preprocessed)...")
                arm_text, arm_latency, arm_usage = send_chat(
                    client, direct_url, _key, arm_chat_history, model
                )
                arm_input = arm_usage.get("prompt_tokens", arm_est)
                arm_output = arm_usage.get("completion_tokens", estimate_tokens(arm_text))
                arm_hit, arm_miss = _upstream_cache_split(arm_usage, arm_input)
                print(f"  [arm={arm}] {arm_input} in / {arm_output} out in {arm_latency:.0f}ms (filter-only)")
                trace_turn = {
                    "assembly_mode": "filter_only",
                    "input_tokens": arm_input,
                    "rewritten_tokens": arm_est,
                    "savings_tokens": direct_input - arm_input if direct_input > arm_input else 0,
                    "savings_ratio": round((direct_input - arm_input) / direct_input, 4) if direct_input > 0 else 0.0,
                    "facts_stored": 0,
                    "assembly_latency_ms": 0.0,
                    "extraction_latency_ms": 0.0,
                    "session_id": "",
                    "cache_hit_tokens": arm_hit,
                    "cache_miss_tokens": arm_miss,
                    "prompt_tokens_actual": arm_input,
                    "output_tokens": arm_output,
                    "turn": i,
                }
            elif is_direct_arm:
                arm_text, arm_latency, arm_usage = direct_text, direct_latency, direct_usage
                arm_input, arm_output = direct_input, direct_output
                direct_hit, direct_miss = _upstream_cache_split(direct_usage, direct_input)
                print(f"  [arm={arm}] Using direct baseline (no proxy)")
                trace_turn = {
                    "assembly_mode": "direct",
                    "input_tokens": direct_input,
                    "rewritten_tokens": direct_input,
                    "savings_tokens": 0,
                    "savings_ratio": 0.0,
                    "facts_stored": 0,
                    "assembly_latency_ms": 0.0,
                    "extraction_latency_ms": 0.0,
                    "session_id": "",
                    # Record the REAL upstream cache split (DeepSeek reports
                    # prompt_cache_hit_tokens). Without this the passthrough
                    # baseline has no cache telemetry and the verdict is always
                    # INCONCLUSIVE.
                    "cache_hit_tokens": direct_hit,
                    "cache_miss_tokens": direct_miss,
                    "prompt_tokens_actual": direct_input,
                    "output_tokens": direct_output,
                    "turn": i,
                }
            else:
                print(f"  [arm={arm}] Sending {len(arm_history)} messages (~{arm_est} tokens)...")
                arm_text, arm_latency, arm_usage = send_chat(
                    client, proxy_url, _key, arm_history, model,
                    session_id=proxy_session_id, session_config=arm_config,
                )
                arm_input = arm_usage.get("prompt_tokens", arm_est)
                arm_output = arm_usage.get("completion_tokens", estimate_tokens(arm_text))
                print(f"  [arm={arm}] {arm_input} in / {arm_output} out in {arm_latency:.0f}ms")

                time.sleep(3)
                trace = get_proxy_trace(client, proxy_url, session_id=proxy_session_id)
                if trace.get("error"):
                    print(f"  [trace]  WARNING: {trace['error']}")
                trace_turns = trace.get("turns", [])
                expected_turn = i - 1
                trace_turn = {}
                for t in reversed(trace_turns):
                    if t.get("turn_number") == expected_turn:
                        trace_turn = t
                        break
                if not trace_turn and trace_turns:
                    trace_turn = trace_turns[-1]

                trace_turn = {
                    "assembly_mode": trace_turn.get("assembly_mode", "unknown"),
                    "input_tokens": trace_turn.get("input_tokens", 0),
                    "rewritten_tokens": trace_turn.get("rewritten_tokens", 0),
                    "savings_tokens": trace_turn.get("savings_tokens", 0),
                    "savings_ratio": trace_turn.get("savings_ratio", 0.0),
                    "facts_stored": trace_turn.get("facts_stored", 0),
                    "assembly_latency_ms": trace_turn.get("assembly_latency_ms", 0.0),
                    "extraction_latency_ms": trace_turn.get("extraction_latency_ms", 0.0),
                    "session_id": proxy_session_id or "",
                    "cache_hit_tokens": trace_turn.get("cache_hit_tokens", 0),
                    "cache_miss_tokens": trace_turn.get("cache_miss_tokens", 0),
                    "prompt_tokens_actual": trace_turn.get(
                        "prompt_tokens_actual", trace_turn.get("input_tokens", 0)
                    ),
                    "output_tokens": arm_output,
                    "turn": i,
                }

            continuity_turn = tracker.observe_turn(i, arm_text)

            # Agent-solo tool-continuation turns naturally produce short
            # responses (the model just acknowledges the tool result before the
            # next step). That is normal agent behavior, NOT output collapse /
            # degeneration, so the collapse guard must not count them. Leave the
            # streak unchanged on tool-loop turns (neither increment nor reset).
            if is_tool_turn(turn):
                pass
            elif arm_output < COLLAPSE_TOKEN_THRESHOLD:
                consecutive_collapses += 1
                print(f"  [WARN]   Output collapse: {arm_output} tokens "
                      f"(consecutive: {consecutive_collapses}/{COLLAPSE_CONSECUTIVE_LIMIT})")
            else:
                consecutive_collapses = 0

            direct_history.append({"role": "assistant", "content": direct_text})
            arm_history.append({"role": "assistant", "content": arm_text})

            result = {
                "turn": i,
                "user_msg_preview": user_display[:80],
                "user_msg": user_display,
                "direct": {
                    "input_tokens": direct_input,
                    "output_tokens": direct_output,
                    "latency_ms": round(direct_latency, 1),
                    "response_preview": direct_text[:150] if direct_text else "",
                    "response": direct_text,
                },
                "arm": {
                    "input_tokens": arm_input,
                    "output_tokens": arm_output,
                    "latency_ms": round(arm_latency, 1),
                    "response_preview": arm_text[:150] if arm_text else "",
                    "response": arm_text,
                },
                "trace": trace_turn,
                "continuity": continuity_turn,
            }

            if pricing is not None:
                turn_cost = compute_turn_cost(trace_turn, pricing)
                result["effective_cost_usd"] = turn_cost.effective_cost_usd
                result["cache_data_available"] = turn_cost.cache_data_available

            results.append(result)

            if run_probes:
                probes = run_fact_probes(
                    client, scenario, direct_history, arm_history,
                    proxy_url, direct_url, model, i, api_key=_key,
                    proxy_session_id=proxy_session_id, arm_config=arm_config,
                )
                probe_results.extend(probes)
                for p in probes:
                    tracker.record_probe_result(
                        direct_recall=p.get("direct_recall", 0.0),
                        arm_recall=p.get("arm_recall", 0.0),
                    )

            save_checkpoint(
                ckpt_path, scenario.name, arm, budget,
                results, probe_results,
                direct_history, arm_history, proxy_session_id,
            )

            if collapse_abort and consecutive_collapses >= COLLAPSE_CONSECUTIVE_LIMIT:
                print(f"\n  [ABORT]  Output collapsed for {COLLAPSE_CONSECUTIVE_LIMIT} "
                      f"consecutive turns. Stopping.")
                break

    if ckpt_path.exists():
        ckpt_path.unlink()

    if results:
        known_files = set(tracker._seen_files.keys())
        known_commands = set(tracker._seen_commands.keys())
        final_response = results[-1].get("arm", {}).get("response", "")
        final_continuity = tracker.compute(
            final_response=final_response,
            known_files=known_files,
            known_commands=known_commands,
        )
    else:
        final_continuity = tracker.compute()

    total_direct_input = sum(r["direct"]["input_tokens"] for r in results)
    total_arm_input = sum(r["arm"]["input_tokens"] for r in results)
    total_savings = sum(r["trace"].get("savings_tokens", 0) for r in results)

    probe_summary = {}
    if probe_results:
        avg_direct_recall = sum(p["direct_recall"] for p in probe_results) / len(probe_results)
        avg_arm_recall = sum(p["arm_recall"] for p in probe_results) / len(probe_results)
        probe_summary = {
            "total_probes": len(probe_results),
            "avg_direct_recall": round(avg_direct_recall, 3),
            "avg_arm_recall": round(avg_arm_recall, 3),
            "recall_preservation": round(avg_arm_recall / avg_direct_recall, 3) if avg_direct_recall > 0 else 0,
        }

    collapsed_turns = [
        r["turn"] for r in results
        if r["arm"]["output_tokens"] < COLLAPSE_TOKEN_THRESHOLD
    ]
    aborted = consecutive_collapses >= COLLAPSE_CONSECUTIVE_LIMIT

    if not results:
        final_continuity = tracker.compute()

    # ---- effective cost (cache-weighted) + passthrough delta ----
    if pricing is not None and results:
        arm_cost_dict: dict = _compute_cost_summary(results, pricing)
    else:
        arm_cost_dict = {}

    bootstrap_result = None
    if run_restart and not is_direct_arm:
        try:
            with httpx.Client() as restart_client:
                bootstrap_result = run_restart_bootstrap(
                    restart_client, scenario, proxy_url, direct_url,
                    model, _key, arm_config=arm_config,
                )
            final_continuity.turn_one_orientation_score = bootstrap_result.get("orientation_score", 0.0)
        except Exception as e:
            print(f"  [WARN] Restart/bootstrap failed: {e}")
            bootstrap_result = {"error": str(e)}

    summary: dict = {
        "total_direct_input_tokens": total_direct_input,
        "total_proxy_input_tokens": total_arm_input,
        "total_savings_tokens": total_savings,
        "overall_savings_ratio": round(total_savings / total_direct_input, 4) if total_direct_input else 0,
        "collapsed_turns": collapsed_turns,
        "collapse_rate": round(len(collapsed_turns) / len(results), 3) if results else 0,
    }
    summary.update(arm_cost_dict)

    data = {
        "scenario": scenario.name,
        "description": scenario.description,
        "model": model,
        "budget": budget,
        "arm": arm,
        "turns_run": len(results),
        "turns_total": len(turns),
        "aborted": aborted,
        "abort_reason": f"output_collapse_{COLLAPSE_CONSECUTIVE_LIMIT}_consecutive" if aborted else "",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "summary": summary,
        "quality": probe_summary,
        "continuity": asdict(final_continuity),
        "bootstrap": bootstrap_result,
        "config_snapshot": config_snapshot,
        "turns": results,
        "fact_probes": probe_results,
    }

    return data


def run_experiment(
    experiment_name: str,
    scenarios: list[Scenario],
    arms: list[str],
    budgets: list[int | None],
    proxy_url: str,
    direct_url: str,
    model: str,
    output_dir: Path,
    resume: bool,
    api_key: str,
    max_turns: int | None = None,
    pricing: PricingModel | None = None,
) -> Path:
    """Run a named experiment across scenarios x arms x budgets."""
    experiment_dir = output_dir / "experiments" / experiment_name
    experiment_dir.mkdir(parents=True, exist_ok=True)

    all_results = []
    for arm_name in arms:
        arm_def = ARMS.get(arm_name)
        if not arm_def:
            print(f"  WARNING: Unknown arm '{arm_name}', skipping")
            continue

        for scenario in scenarios:
            for budget in budgets:
                print(f"\n{'#'*70}")
                print(f"  [{experiment_name}] Running: {scenario.name} / {arm_name} @ budget={budget or 'default'}")
                print(f"{'#'*70}")

                data = run_benchmark(
                    scenario, arm_name, proxy_url, direct_url, model,
                    budget, experiment_dir, resume, api_key=api_key,
                    max_turns=max_turns, pricing=pricing,
                )
                data["experiment"] = experiment_name
                print_summary(data)
                save_results(data, experiment_dir)
                all_results.append(data)

    metadata = {
        "experiment": experiment_name,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "arms": arms,
        "budgets": [b for b in budgets],
        "scenarios": [s.name for s in scenarios],
        "results_summary": [
            {
                "scenario": d["scenario"],
                "arm": d.get("arm", "unknown"),
                "budget": d["budget"],
                "turns": d["turns_run"],
                "savings_ratio": d["summary"]["overall_savings_ratio"],
                "direct_tokens": d["summary"]["total_direct_input_tokens"],
                "arm_tokens": d["summary"]["total_proxy_input_tokens"],
                "savings_tokens": d["summary"]["total_savings_tokens"],
                "avg_arm_recall": d.get("quality", {}).get("avg_arm_recall"),
                "avg_direct_recall": d.get("quality", {}).get("avg_direct_recall"),
                "recall_preservation": d.get("quality", {}).get("recall_preservation"),
            }
            for d in all_results
        ],
    }
    metadata["completed_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with open(experiment_dir / "experiment.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    if len(all_results) > 1:
        print_cross_scenario_summary(all_results)

    print(f"\n  Experiment '{experiment_name}' complete -- {len(all_results)} runs saved to {experiment_dir}")
    return experiment_dir