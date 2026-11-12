"""Simulation runner.
Executes scenario runs, streams events, and writes artifacts into runs/ directory.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from robofleet.catalogue.generator import generate_catalogue
from robofleet.catalogue.slotting import slot_inventory
from robofleet.config.models import ScenarioConfig
from robofleet.contracts.state import WorldSnapshot
from robofleet.layout.ascii_loader import load_ascii_layout
from robofleet.layout.generator import generate_parametric_layout
from robofleet.sim.engine import SimEngine
from robofleet.sim.state_hash import compute_state_hash


def run_simulation(
    config: ScenarioConfig,
    duration_s: int | None = None,
    output_dir: Path | str | None = None,
) -> dict[str, object]:
    start_wall = time.perf_counter()
    total_duration_s = duration_s or config.timing.max_duration_s
    total_ticks = total_duration_s * config.timing.tick_hz

    # 1. Build layout
    if config.layout.preset == "custom" and config.layout.ascii_file:
        layout = load_ascii_layout(config.layout.ascii_file, cell_size_m=config.physics.cell_size_m)
    else:
        layout = generate_parametric_layout(config.layout, name=config.scenario_name)

    # 2. Build catalogue and slot inventory
    skus = generate_catalogue(sku_count=config.catalogue.sku_count, seed=config.seed)
    bins, _ = slot_inventory(
        layout=layout,
        skus=skus,
        empty_bin_pct=config.catalogue.empty_bin_pct,
        top_k_popular_replicas=config.catalogue.top_k_popular_replicas,
        seed=config.seed,
    )

    # 3. Create simulation engine
    engine = SimEngine(
        config=config,
        layout=layout,
        skus=skus,
        bins=bins,
    )

    # Prepare output paths
    out_path = Path(output_dir or f"runs/{config.scenario_name}_{int(time.time())}")
    out_path.mkdir(parents=True, exist_ok=True)
    events_file = out_path / "events.ndjson"

    # Step simulation loop
    with events_file.open("w", encoding="utf-8") as ef:
        for _ in range(total_ticks):
            engine.step()
            # Flush recent events to ndjson
            while engine.events:
                ev = engine.events.pop(0)
                ef.write(ev.model_dump_json() + "\n")

    end_wall = time.perf_counter()
    wall_duration = end_wall - start_wall

    final_dynamic = engine.get_dynamic_state()
    final_static = engine.get_static_world()
    final_hash = compute_state_hash(final_dynamic)

    # Write final snapshot
    snapshot = WorldSnapshot(static=final_static, dynamic=final_dynamic)
    (out_path / "final_snapshot.json").write_text(
        snapshot.model_dump_json(indent=2), encoding="utf-8"
    )

    # Calculate metrics
    destinations_visited = {
        r_id: len(cells) for r_id, cells in engine.visited_cells_per_robot.items()
    }
    min_visited = min(destinations_visited.values()) if destinations_visited else 0

    metrics = {
        "scenario": config.scenario_name,
        "seed": config.seed,
        "sim_duration_s": total_duration_s,
        "sim_ticks": total_ticks,
        "wall_duration_s": round(wall_duration, 3),
        "sim_seconds_per_wall_second": round(total_duration_s / max(wall_duration, 0.001), 2),
        "robot_count": config.robot_count,
        "deadlock_incidents": engine.planner.deadlock_incidents,
        "min_destinations_visited_per_robot": min_visited,
        "final_state_hash": final_hash,
    }
    (out_path / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    return metrics
