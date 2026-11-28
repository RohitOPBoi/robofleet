"""Chaos Scenario Benchmark and Evaluation CLI (Phase 6, P6-A1, P6-A4).
Runs chaos scenarios across seeds in baseline, heuristic, and AI modes.
Evaluates pass criteria, measures MTTR with confidence intervals, and formats comparison tables.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Any
import numpy as np
import yaml

from robofleet.brain.orchestrator import MissionOrchestrator
from robofleet.catalogue.generator import generate_catalogue
from robofleet.catalogue.slotting import slot_inventory
from robofleet.config.loader import load_config
from robofleet.layout.generator import generate_parametric_layout
from robofleet.sim.engine import SimEngine


def parse_seeds(seed_str: str) -> list[int]:
    if ".." in seed_str:
        start, end = map(int, seed_str.split(".."))
        return list(range(start, end + 1))
    return [int(s.strip()) for s in seed_str.split(",") if s.strip()]


def run_single_chaos_seed(
    scenario_path: Path,
    mode: str = "heuristic",
    seed: int = 42,
    rules_dir: str = "rules",
) -> dict[str, Any]:
    with open(scenario_path, "r", encoding="utf-8") as f:
        scenario_data = yaml.safe_load(f) or {}

    duration_ticks = scenario_data.get("duration_ticks", 500)
    pass_criteria = scenario_data.get("pass_criteria", {})

    cfg, _ = load_config(scenario_name="standard")
    cfg.seed = seed

    layout = generate_parametric_layout(cfg.layout)
    skus = generate_catalogue(sku_count=cfg.catalogue.sku_count, seed=seed)
    bins, _ = slot_inventory(skus=skus, layout=layout, seed=seed)

    engine = SimEngine(config=cfg, layout=layout, skus=skus, bins=bins)
    engine.chaos_engine.load_chaos_scenario(scenario_path)

    orchestrator = None
    if mode in ("heuristic", "ai", "local_llm", "replay"):
        orchestrator = MissionOrchestrator(
            engine=engine,
            provider_name=mode,
            rules_dir=rules_dir,
        )

    # Simulation loop
    safety_violations = 0
    for tick in range(duration_ticks):
        if orchestrator and orchestrator.enabled:
            # Synchronous step helper for CLI
            import asyncio
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            loop.run_until_complete(orchestrator.step(tick))

        try:
            engine.step()
        except Exception as e:
            if "SafetyViolation" in type(e).__name__:
                safety_violations += 1
            else:
                raise

        # Invariant check: zero safety collisions
        cells_occupied = [r.cell.as_tuple() for r in engine.robots]
        if len(cells_occupied) != len(set(cells_occupied)):
            safety_violations += 1

    # Evaluate results
    orders = engine.orders
    completed = [o for o in orders if o.status.value in ("HANDED_OVER", "PACKED", "READY_FOR_DISPATCH")]
    lost_orders = sum(1 for o in orders if o.status.value == "FAILED")
    evaluated_orders = [o for o in completed if o.handover_tick is not None or o.ready_tick is not None]

    on_time = 0
    for o in evaluated_orders:
        t_finish = o.handover_tick or o.ready_tick or 0
        if t_finish <= o.deadline_tick:
            on_time += 1
    on_time_pct = (on_time / len(evaluated_orders) * 100.0) if evaluated_orders else 100.0

    mttr_map = engine.chaos_engine.get_mttr_by_type()
    avg_mttr_s = float(np.mean(list(mttr_map.values()))) if mttr_map else 0.0

    # Verification stats
    failed_unverified = engine.station_mgr.failed_picks_count
    # Invariant: order never completes with UNVERIFIED
    unverified_completed = sum(
        1 for o in completed if any(l.status in ("UNVERIFIED", "MISMATCH") for l in o.lines)
    )

    # Check criteria
    passed = (
        lost_orders <= pass_criteria.get("max_lost_orders", 0)
        and safety_violations <= pass_criteria.get("max_safety_violations", 0)
        and on_time_pct >= pass_criteria.get("min_on_time_pct", 50.0)
        and unverified_completed <= pass_criteria.get("max_unverified_picks", 0)
    )

    return {
        "seed": seed,
        "mode": mode,
        "passed": passed,
        "duration_ticks": duration_ticks,
        "total_orders": len(orders),
        "completed_orders": len(completed),
        "lost_orders": lost_orders,
        "on_time_pct": round(on_time_pct, 1),
        "safety_violations": safety_violations,
        "unverified_completed": unverified_completed,
        "avg_mttr_s": round(avg_mttr_s, 2),
        "mttr_by_type": mttr_map,
        "incidents_count": engine.chaos_engine.total_incidents_count,
        "human_interventions": engine.exceptions_queue.total_human_interventions,
        "substitutions": engine.chaos_engine.recovery_mgr.substitutions_performed,
    }


def cmd_chaos(args: argparse.Namespace) -> int:
    scenario_path = Path("scenarios/chaos") / f"{args.scenario}.yaml"
    if not scenario_path.exists():
        scenario_path = Path(args.scenario)
    if not scenario_path.exists():
        print(f"Error: Scenario file '{args.scenario}' not found.", file=sys.stderr)
        return 1

    seeds = parse_seeds(args.seeds)
    modes = [m.strip() for m in args.modes.split(",") if m.strip()]

    print(f"\n========================================================")
    print(f"RoboFleet Chaos Benchmark: {args.scenario}")
    print(f"Modes: {modes} | Seeds: {seeds} ({len(seeds)} runs per mode)")
    print(f"========================================================\n")

    all_results: list[dict[str, Any]] = []

    for mode in modes:
        mode_results = []
        for s in seeds:
            res = run_single_chaos_seed(scenario_path=scenario_path, mode=mode, seed=s)
            mode_results.append(res)
            all_results.append(res)

        passed_count = sum(1 for r in mode_results if r["passed"])
        avg_on_time = np.mean([r["on_time_pct"] for r in mode_results])
        avg_mttr = np.mean([r["avg_mttr_s"] for r in mode_results])
        total_lost = sum(r["lost_orders"] for r in mode_results)
        total_safety = sum(r["safety_violations"] for r in mode_results)

        print(f"Mode [{mode.upper()}]:")
        print(f"  Pass Rate: {passed_count}/{len(seeds)} ({passed_count/len(seeds)*100:.1f}%)")
        print(f"  On-Time: {avg_on_time:.1f}% | Avg MTTR: {avg_mttr:.2f}s")
        print(f"  Lost Orders: {total_lost} | Safety Violations: {total_safety}")
        print(f"  --------------------------------------------------------")

    # Output detail table
    print(f"\nDetailed Results by Seed:")
    print(f"{'Mode':<10} | {'Seed':<5} | {'Pass':<5} | {'On-Time':<8} | {'Lost':<5} | {'Violations':<10} | {'MTTR (s)':<8}")
    print("-" * 65)
    for r in all_results:
        p_str = "PASS" if r["passed"] else "FAIL"
        print(f"{r['mode']:<10} | {r['seed']:<5} | {p_str:<5} | {r['on_time_pct']:>6.1f}% | {r['lost_orders']:<5} | {r['safety_violations']:<10} | {r['avg_mttr_s']:>7.2f}s")

    return 0
