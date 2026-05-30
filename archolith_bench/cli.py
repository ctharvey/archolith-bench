"""CLI entrypoint for archolith-bench."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .arms import ARMS, PROXY_FAMILY_ARMS
from .core.api import API_KEY, DIRECT_URL, MODEL, PROXY_URL, check_proxy_health
from .core.report import print_cross_scenario_summary, print_summary, save_results
from .core.scenario import Scenario, list_scenarios
from .suites.proxy import run_benchmark, run_experiment


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="archolith-bench",
        description="Unified benchmark suite for the archolith product family",
    )
    subparsers = parser.add_subparsers(dest="suite", help="Benchmark suite to run")

    # ---- proxy subcommand ----
    proxy_p = subparsers.add_parser("proxy", help="Proxy suite: multi-turn token savings + continuity")
    proxy_p.add_argument("--scenario", type=Path, help="Path to scenario JSON file")
    proxy_p.add_argument("--all", action="store_true", help="Run all scenarios in scenarios/")
    proxy_p.add_argument("--list", action="store_true", help="List available scenarios and exit")
    proxy_p.add_argument("--arms", type=str, default="proxy_plus_filter",
                         help=f"Comma-separated arms to run. Available: {', '.join(ARMS)}")
    proxy_p.add_argument("--budget", type=int, default=None, help="Token budget (sets context_token_budget)")
    proxy_p.add_argument("--budgets", type=str, default=None,
                         help="Comma-separated budgets for matrix run (e.g., 4000,8000,15000)")
    proxy_p.add_argument("--turns", type=int, default=None, help="Limit number of turns to run")
    proxy_p.add_argument("--proxy", default=PROXY_URL, help="Proxy URL")
    proxy_p.add_argument("--direct", default=DIRECT_URL, help="Direct upstream URL")
    proxy_p.add_argument("--model", default=MODEL, help="Model to use")
    proxy_p.add_argument("--output-dir", type=Path, default=Path("results"),
                         help="Output directory for results")
    proxy_p.add_argument("--resume", action="store_true", help="Resume from last checkpoint")
    proxy_p.add_argument("--api-key", default=None, help="API key (overrides UPSTREAM_API_KEY)")
    proxy_p.add_argument("--experiment", type=str, default=None,
                         help="Named experiment -- snapshots proxy config, saves to experiments/<name>/")
    proxy_p.add_argument("--config", type=str, default=None,
                         help="JSON proxy config overrides")
    proxy_p.add_argument("--no-probes", action="store_true", help="Skip fact probes")
    proxy_p.add_argument("--no-restart", action="store_true", help="Skip restart/bootstrap scoring")

    args = parser.parse_args(argv)

    if not args.suite:
        parser.print_help()
        sys.exit(1)

    if args.suite == "proxy":
        _run_proxy(args)
    else:
        print(f"Unknown suite: {args.suite}")
        sys.exit(1)


def _run_proxy(args: argparse.Namespace) -> None:
    if args.list:
        print("Available scenarios:")
        for p in list_scenarios():
            s = Scenario.from_file(p)
            print(f"  {p.name:<25} {s.name:<15} {len(s.turns)} turns  "
                  f"{len(s.fact_probes)} probes  {s.description[:60]}")
        return

    api_key = args.api_key or API_KEY

    # Parse arms
    arm_names = [a.strip() for a in args.arms.split(",")]
    for arm_name in arm_names:
        if arm_name not in ARMS:
            print(f"ERROR: Unknown arm '{arm_name}'. Available: {', '.join(ARMS)}", file=sys.stderr)
            sys.exit(1)

    # Parse scenarios
    scenarios: list[Scenario] = []
    if args.all:
        scenarios = [Scenario.from_file(p) for p in list_scenarios()]
    elif args.scenario:
        scenarios = [Scenario.from_file(args.scenario)]
    else:
        print("ERROR: Specify --scenario <file> or --all", file=sys.stderr)
        sys.exit(1)

    # Parse budgets
    budgets: list[int | None] = [args.budget]
    if args.budgets:
        budgets = [int(b.strip()) for b in args.budgets.split(",")]

    print(f"Proxy suite: {len(scenarios)} scenario(s) x {len(arm_names)} arm(s) x {len(budgets)} budget(s)")
    print(f"  Proxy:  {args.proxy}")
    print(f"  Direct: {args.direct}")
    print(f"  Model:  {args.model}")
    print(f"  Arms:   {', '.join(arm_names)}")

    # Health check only when actually running (not --list)
    needs_proxy = any(ARMS[a]["proxy_enabled"] for a in arm_names)
    if needs_proxy:
        health = check_proxy_health(args.proxy)
        if health is None:
            print(f"ERROR: Cannot reach proxy at {args.proxy}. Is it running?", file=sys.stderr)
            sys.exit(1)
        print(f"  Proxy health: {health}")
        if health.get("graph") != "connected":
            print("WARNING: Proxy graph not connected -- assembly won't fire")

    if not api_key:
        print("ERROR: Set UPSTREAM_API_KEY in .env or pass --api-key", file=sys.stderr)
        sys.exit(1)
    print(f"  API key: ...{api_key[-8:]}")

    # Parse config overrides
    config_overrides = None
    if args.config:
        try:
            config_overrides = json.loads(args.config)
        except json.JSONDecodeError as e:
            print(f"ERROR: Invalid --config JSON: {e}", file=sys.stderr)
            sys.exit(1)

    # Experiment mode
    if args.experiment:
        run_experiment(
            experiment_name=args.experiment,
            scenarios=scenarios,
            arms=arm_names,
            budgets=budgets,
            proxy_url=args.proxy,
            direct_url=args.direct,
            model=args.model,
            output_dir=args.output_dir,
            resume=args.resume,
            api_key=api_key,
            max_turns=args.turns,
        )
        return

    # Apply manual config overrides (non-experiment mode)
    if config_overrides:
        from .core.api import apply_arm_config
        import httpx
        with httpx.Client() as client:
            apply_arm_config(client, args.proxy, config_overrides)

    # Run the matrix
    all_results = []
    for arm_name in arm_names:
        for scenario in scenarios:
            for budget in budgets:
                print(f"\n{'#'*70}")
                print(f"  Running: {scenario.name} / {arm_name} @ budget={budget or 'default'}")
                print(f"  {scenario.description}")
                print(f"{'#'*70}")

                data = run_benchmark(
                    scenario, arm_name, args.proxy, args.direct, args.model,
                    budget, args.output_dir, args.resume, api_key=api_key,
                    max_turns=args.turns,
                    run_probes=not args.no_probes,
                    run_restart=not args.no_restart,
                )
                print_summary(data)
                save_results(data, args.output_dir)
                all_results.append(data)

    if len(all_results) > 1:
        print_cross_scenario_summary(all_results)


if __name__ == "__main__":
    main()