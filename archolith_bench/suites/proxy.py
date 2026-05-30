"""Proxy suite: multi-turn session benchmark across experiment arms.

Ports the seed benchmark.py into the arm-aware architecture and adds
continuity tracking and restart/bootstrap scoring.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import asdict
from pathlib import Path

import httpx

from ..arms import ARMS, PROXY_FAMILY_ARMS
from ..core.api import (
    API_KEY,
    DIRECT_URL,
    MODEL,
    PROXY_URL,
    apply_arm_config,
    estimate_messages_tokens,
    estimate_tokens,
    get_proxy_trace,
    send_chat,
    set_proxy_budget,
    snapshot_proxy_config,
)
from ..core.metrics import (
    ContinuityMetrics,
    ScenarioResult,
    TokenMetrics,
    TurnResult,
)
from ..core.report import COLLAPSE_TOKEN_THRESHOLD, print_cross_scenario_summary, print_summary, save_results
from ..core.scenario import FactProbe, Scenario

COLLAPSE_CONSECUTIVE_LIMIT = 2


# ---------------------------------------------------------------------------
# ContinuityTracker
# ---------------------------------------------------------------------------

_FILE_PATH_RE = re.compile(r'(?:/[\w.\-]+/){1,}[\w.\-]+\.\w{1,12}', re.IGNORECASE)
_COMMAND_RE = re.compile(r'(?:npm|pip|python|git|cargo|go|docker|kubectl|make)\s+\S+', re.IGNORECASE)


class ContinuityTracker:
    """Track re-mentions of file paths and commands across a scenario run.

    Scans each arm response for file paths / commands first seen in earlier
    turns.  Records repeat_file_reads, repeat_diagnostics, and computes
    decision_retention and verification_continuity at the end.
    """

    def __init__(self) -> None:
        self._seen_files: dict[str, int] = {}
        self._seen_commands: dict[str, int] = {}
        self._repeat_file_reads: int = 0
        self._repeat_diagnostics: int = 0
        self._decisions_retained: int = 0
        self._decisions_total: int = 0
        self._verifications_continued: int = 0
        self._verifications_total: int = 0

    def observe_turn(self, turn: int, response: str) -> dict:
        """Scan a response, update internal state, and return per-turn stats."""
        files_in_response = set(_FILE_PATH_RE.findall(response))
        commands_in_response = set(_COMMAND_RE.findall(response))

        repeat_files = 0
        new_files = 0
        for f in files_in_response:
            if f in self._seen_files:
                repeat_files += 1
                self._repeat_file_reads += 1
            else:
                new_files += 1
                self._seen_files[f] = turn

        repeat_cmds = 0
        new_cmds = 0
        for c in commands_in_response:
            if c in self._seen_commands:
                repeat_cmds += 1
                self._repeat_diagnostics += 1
            else:
                new_cmds += 1
                self._seen_commands[c] = turn

        return {
            "turn": turn,
            "files_mentioned": len(files_in_response),
            "repeat_files": repeat_files,
            "new_files": new_files,
            "commands_mentioned": len(commands_in_response),
            "repeat_commands": repeat_cmds,
            "new_commands": new_cmds,
        }

    def record_decision(self, retained: bool) -> None:
        self._decisions_total += 1
        if retained:
            self._decisions_retained += 1

    def record_verification(self, continued: bool) -> None:
        self._verifications_total += 1
        if continued:
            self._verifications_continued += 1

    def compute(self) -> ContinuityMetrics:
        return ContinuityMetrics(
            repeat_file_reads=self._repeat_file_reads,
            repeat_diagnostics=self._repeat_diagnostics,
            decision_retention=(
                self._decisions_retained / self._decisions_total
                if self._decisions_total else 0.0
            ),
            verification_continuity=(
                self._verifications_continued / self._verifications_total
                if self._verifications_total else 0.0
            ),
        )


# ---------------------------------------------------------------------------
# Restart / Bootstrap runner
# ---------------------------------------------------------------------------

def run_restart_bootstrap(
    client: httpx.Client,
    scenario: Scenario,
    proxy_url: str,
    direct_url: str,
    model: str,
    api_key: str,
    arm_config: dict | None = None,
) -> dict:
    """Replay a scenario, then start a fresh conversation in the same proxy
    session and score turn_one_orientation_score: did the model recover
    the last blocker / next step without re-reading previously-mentioned files?
    """
    _key = api_key or API_KEY
    system_msg = {"role": "system", "content": scenario.system_prompt}
    history = [system_msg]

    for i, user_msg in enumerate(scenario.turns, 1):
        history.append({"role": "user", "content": user_msg})
        text, _, _ = send_chat(client, proxy_url, _key, history, model)
        history.append({"role": "assistant", "content": text})

    last_response = history[-1]["content"] if history else ""
    last_files = set(_FILE_PATH_RE.findall(last_response))

    orientation_prompt = (
        "Without re-reading any files we already discussed, "
        "what was the last blocker or next step we were working on, "
        "and what should we do next?"
    )

    tracker = ContinuityTracker()
    for f in last_files:
        tracker._seen_files[f] = len(scenario.turns)

    fresh_history = [system_msg, {"role": "user", "content": orientation_prompt}]
    orientation_text, _, _ = send_chat(client, proxy_url, _key, fresh_history, model)

    turn_stats = tracker.observe_turn(len(scenario.turns) + 1, orientation_text)

    orientation_score = 0.0
    if last_files:
        re_mentioned = sum(1 for f in last_files if f.lower() in orientation_text.lower())
        orientation_score = 1.0 - (re_mentioned / len(last_files))
    else:
        orientation_score = 1.0 if orientation_text.strip() else 0.0

    return {
        "orientation_prompt": orientation_prompt,
        "orientation_response_preview": orientation_text[:500],
        "orientation_score": round(orientation_score, 4),
        "last_files_count": len(last_files),
        "re_mentioned_files": turn_stats["repeat_files"],
    }


# ---------------------------------------------------------------------------
# Checkpoint helpers
# ---------------------------------------------------------------------------

def _checkpoint_path(output_dir: Path, scenario_name: str, arm: str, budget: int | None) -> Path:
    budget_str = f"_{budget}b" if budget else ""
    return output_dir / f".checkpoint_{scenario_name}_{arm}{budget_str}.json"


def _save_checkpoint(
    path: Path, scenario_name: str, arm: str, budget: int | None,
    results: list, probe_results: list,
    direct_history: list, arm_history: list,
    proxy_session_id: str | None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({
            "scenario": scenario_name,
            "arm": arm,
            "budget": budget,
            "results": results,
            "probe_results": probe_results,
            "direct_history": direct_history,
            "arm_history": arm_history,
            "proxy_session_id": proxy_session_id,
        }, f)


def _load_checkpoint(path: Path) -> dict | None:
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return None


# ---------------------------------------------------------------------------
# Fact probe evaluation
# ---------------------------------------------------------------------------

def _run_fact_probes(
    client: httpx.Client,
    scenario: Scenario,
    direct_history: list[dict],
    arm_history: list[dict],
    proxy_url: str,
    direct_url: str,
    model: str,
    current_turn: int,
    api_key: str = "",
) -> list[dict]:
    _key = api_key or API_KEY
    results = []
    for probe in scenario.fact_probes:
        if probe.after_turn != current_turn:
            continue
        probe_msg = {"role": "user", "content": probe.question}
        direct_messages = direct_history + [probe_msg]
        direct_text, _, _ = send_chat(client, direct_url, _key, direct_messages, model)
        arm_messages = arm_history + [probe_msg]
        arm_text, _, _ = send_chat(client, proxy_url, _key, arm_messages, model)
        direct_hits = sum(1 for kw in probe.expected_keywords if kw.lower() in direct_text.lower())
        arm_hits = sum(1 for kw in probe.expected_keywords if kw.lower() in arm_text.lower())
        total_kw = len(probe.expected_keywords)
        result = {
            "after_turn": probe.after_turn,
            "question": probe.question,
            "expected_keywords": probe.expected_keywords,
            "direct_recall": round(direct_hits / total_kw, 3) if total_kw else 0,
            "arm_recall": round(arm_hits / total_kw, 3) if total_kw else 0,
            "direct_hits": direct_hits,
            "arm_hits": arm_hits,
            "total_keywords": total_kw,
            "direct_response_preview": direct_text[:200],
            "arm_response_preview": arm_text[:200],
        }
        results.append(result)
        status = "PASS" if arm_hits >= direct_hits else "DEGRADED"
        print(f"  [probe]  After turn {current_turn}: {status} -- "
              f"arm {arm_hits}/{total_kw} vs direct {direct_hits}/{total_kw} keywords recalled")
    return results


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
    proxy_session_id: str | None = None
    start_turn = 0
    consecutive_collapses = 0
    tracker = ContinuityTracker()

    ckpt_path = _checkpoint_path(output_dir, scenario.name, arm, budget)

    if resume:
        ckpt = _load_checkpoint(ckpt_path)
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

        if arm_config:
            apply_arm_config(client, proxy_url, arm_config)

        config_snapshot = snapshot_proxy_config(client, proxy_url)

        for i, user_msg in enumerate(turns, 1):
            if i <= start_turn:
                continue
            print(f"\n{'='*60}")
            print(f"  TURN {i}/{len(turns)}: {scenario.name} [{arm}]")
            print(f"  User: {user_msg[:80]}...")
            print(f"{'='*60}")

            direct_history.append({"role": "user", "content": user_msg})
            arm_history.append({"role": "user", "content": user_msg})

            direct_est = estimate_messages_tokens(direct_history)
            arm_est = estimate_messages_tokens(arm_history)

            is_direct_arm = not arm_def["proxy_enabled"]

            print(f"  [direct] Sending {len(direct_history)} messages (~{direct_est} tokens)...")
            direct_text, direct_latency, direct_usage = send_chat(
                client, direct_url, _key, direct_history, model
            )
            direct_input = direct_usage.get("prompt_tokens", direct_est)
            direct_output = direct_usage.get("completion_tokens", estimate_tokens(direct_text))
            print(f"  [direct] {direct_input} in / {direct_output} out in {direct_latency:.0f}ms")

            if is_direct_arm:
                arm_text, arm_latency, arm_usage = direct_text, direct_latency, direct_usage
                arm_input, arm_output = direct_input, direct_output
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
                }
            else:
                print(f"  [arm={arm}] Sending {len(arm_history)} messages (~{arm_est} tokens)...")
                arm_text, arm_latency, arm_usage = send_chat(
                    client, proxy_url, _key, arm_history, model
                )
                arm_input = arm_usage.get("prompt_tokens", arm_est)
                arm_output = arm_usage.get("completion_tokens", estimate_tokens(arm_text))
                print(f"  [arm={arm}] {arm_input} in / {arm_output} out in {arm_latency:.0f}ms")

                time.sleep(3)
                trace = get_proxy_trace(client, proxy_url, session_id=proxy_session_id)
                trace_turns = trace.get("turns", [])
                expected_turn = i - 1
                trace_turn = {}
                for t in reversed(trace_turns):
                    if t.get("turn_number") == expected_turn:
                        trace_turn = t
                        break
                if not trace_turn and trace_turns:
                    trace_turn = trace_turns[-1]
                if not proxy_session_id and trace.get("summary", {}).get("session_id"):
                    proxy_session_id = trace["summary"]["session_id"]
                    print(f"  [trace]  session_id={proxy_session_id}")

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
                }

            continuity_turn = tracker.observe_turn(i, arm_text)

            if arm_output < COLLAPSE_TOKEN_THRESHOLD:
                consecutive_collapses += 1
                print(f"  [WARN]   Output collapse: {arm_output} tokens "
                      f"(consecutive: {consecutive_collapses}/{COLLAPSE_CONSECUTIVE_LIMIT})")
            else:
                consecutive_collapses = 0

            direct_history.append({"role": "assistant", "content": direct_text})
            arm_history.append({"role": "assistant", "content": arm_text})

            result = {
                "turn": i,
                "user_msg_preview": user_msg[:80],
                "user_msg": user_msg,
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
            results.append(result)

            if run_probes:
                probes = _run_fact_probes(
                    client, scenario, direct_history, arm_history,
                    proxy_url, direct_url, model, i, api_key=_key,
                )
                probe_results.extend(probes)

            _save_checkpoint(
                ckpt_path, scenario.name, arm, budget,
                results, probe_results,
                direct_history, arm_history, proxy_session_id,
            )

            if consecutive_collapses >= COLLAPSE_CONSECUTIVE_LIMIT:
                print(f"\n  [ABORT]  Output collapsed for {COLLAPSE_CONSECUTIVE_LIMIT} "
                      f"consecutive turns. Stopping.")
                break

    if ckpt_path.exists():
        ckpt_path.unlink()

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

    final_continuity = tracker.compute()

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
        "summary": {
            "total_direct_input_tokens": total_direct_input,
            "total_proxy_input_tokens": total_arm_input,
            "total_savings_tokens": total_savings,
            "overall_savings_ratio": round(total_savings / total_direct_input, 4) if total_direct_input else 0,
            "collapsed_turns": collapsed_turns,
            "collapse_rate": round(len(collapsed_turns) / len(results), 3) if results else 0,
        },
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
                    max_turns=max_turns,
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