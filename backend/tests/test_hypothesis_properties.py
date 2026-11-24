"""Hypothesis property-based tests for safety invariants and layout generation (P1-A12)."""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st
from robofleet.catalogue.generator import generate_catalogue
from robofleet.catalogue.slotting import slot_inventory
from robofleet.config.loader import load_config
from robofleet.contracts.commands import (
    BlockCellsCommand,
    ClearFaultCommand,
    EmergencyStopCommand,
    InjectFaultCommand,
    ResumeCommand,
)
from robofleet.contracts.common import Coordinate
from robofleet.layout.generator import generate_parametric_layout
from robofleet.layout.validator import validate_layout
from robofleet.sim.engine import SimEngine


@settings(max_examples=25, deadline=None)
@given(
    st.lists(
        st.tuples(
            st.sampled_from(["estop", "resume", "block", "fault", "clear"]),
            st.integers(min_value=1, max_value=5),
        ),
        min_size=5,
        max_size=20,
    )
)
def test_hypothesis_random_command_fuzz_never_violates_safety(
    commands_fuzz: list[tuple[str, int]],
) -> None:
    cfg, _ = load_config(scenario_name="standard")
    cfg.robot_count = 10
    layout = generate_parametric_layout(cfg.layout)
    skus = generate_catalogue(sku_count=100, seed=42)
    bins, _ = slot_inventory(layout=layout, skus=skus, seed=42)
    engine = SimEngine(config=cfg, layout=layout, skus=skus, bins=bins)

    for action, target_num in commands_fuzz:
        r_id = f"R-{target_num:03d}"
        if action == "estop":
            engine.queue_command(EmergencyStopCommand(command_id="FUZZ", scope="all"))
        elif action == "resume":
            engine.queue_command(ResumeCommand(command_id="FUZZ", scope="all"))
        elif action == "block":
            engine.queue_command(BlockCellsCommand(command_id="FUZZ", cells=[Coordinate(x=5, y=5)]))
        elif action == "fault":
            engine.queue_command(
                InjectFaultCommand(command_id="FUZZ", fault_type="stall", target_id=r_id)
            )
        elif action == "clear":
            engine.queue_command(ClearFaultCommand(command_id="FUZZ", target_id=r_id))

        engine.step()

        # Invariant check: zero duplicate robot coordinates
        pos_list = [r.cell.as_tuple() for r in engine.robots]
        assert len(pos_list) == len(set(pos_list)), (
            f"Safety violation during fuzz: duplicate positions {pos_list}"
        )


@settings(max_examples=15, deadline=None)
@given(
    width=st.integers(min_value=16, max_value=36),
    height=st.integers(min_value=12, max_value=24),
    rack_rows=st.integers(min_value=2, max_value=4),
)
def test_hypothesis_layout_generation_validity(width: int, height: int, rack_rows: int) -> None:
    cfg, _ = load_config()
    cfg.layout.width = width
    cfg.layout.height = height
    cfg.layout.rack_rows = rack_rows
    cfg.layout.parking_count = 10
    cfg.layout.station_count = 2
    cfg.layout.charger_count = 2

    layout = generate_parametric_layout(cfg.layout)
    ok, errors = validate_layout(layout, required_robots=5)
    # The generated parametric layout must either be strongly connected and valid, or report specific connectivity errors
    if not ok:
        assert len(errors) > 0
    else:
        assert layout.width == width
        assert layout.height == height


@settings(max_examples=15, deadline=None)
@given(
    fault_sequence=st.lists(
        st.tuples(
            st.sampled_from(["robot_breakdown", "aisle_blocked", "station_slowdown", "battery_cascade", "bin_missing_stock"]),
            st.integers(min_value=1, max_value=5),
            st.integers(min_value=10, max_value=50),
        ),
        min_size=3,
        max_size=12,
    )
)
def test_hypothesis_chaos_fault_sequences_invariants(
    fault_sequence: list[tuple[str, int, int]],
) -> None:
    """Chaos property tests (Hypothesis, Phase 6): invariants hold under random fault sequences."""
    cfg, _ = load_config(scenario_name="standard")
    cfg.robot_count = 8
    layout = generate_parametric_layout(cfg.layout)
    skus = generate_catalogue(sku_count=60, seed=42)
    bins, _ = slot_inventory(layout=layout, skus=skus, seed=42)
    engine = SimEngine(config=cfg, layout=layout, skus=skus, bins=bins)

    initial_total_units = sum(b.quantity for b in bins)

    for fault_type, target_num, duration in fault_sequence:
        r_id = f"R-{target_num:03d}"
        target = r_id if "robot" in fault_type else "system"
        engine.chaos_engine.inject_fault(
            fault_type=fault_type,
            target_id=target,
            duration_ticks=duration,
            tick=engine.clock.tick,
        )

        for _ in range(5):
            engine.step()

            # Invariant 1: SafetyGuard physical invariant (no duplicate robot cells)
            cells = [r.cell.as_tuple() for r in engine.robots]
            assert len(cells) == len(set(cells)), f"Safety collision detected: {cells}"

            # Invariant 2: Unit conservation
            current_units = sum(b.quantity for b in engine.bins) + engine.task_mgr.units_in_flight + engine.task_mgr.units_completed
            assert current_units == initial_total_units, f"Unit conservation breached: {current_units} != {initial_total_units}"

            # Invariant 3: Zero lost orders
            lost_orders = sum(1 for o in engine.orders if o.status.value == "FAILED")
            assert lost_orders == 0, "Zero lost orders invariant failed"

