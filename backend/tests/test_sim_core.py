"""Tests for simulation core: SafetyGuard invariants, emergency stop, battery cycle, and hooks.
Includes an independent test-side invariant checker.
"""

from __future__ import annotations

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
from robofleet.contracts.robot import RobotState
from robofleet.layout.generator import generate_parametric_layout
from robofleet.sim.engine import SimEngine


class IndependentSafetyChecker:
    """Independent test-side verifier running outside the SafetyGuard."""

    def __init__(self) -> None:
        self.prev_positions: dict[str, tuple[int, int]] = {}

    def verify_tick(self, engine: SimEngine) -> None:
        current_positions = {r.robot_id: r.cell.as_tuple() for r in engine.robots}

        # Invariant 1: No duplicate cells (zero shared cells)
        pos_list = list(current_positions.values())
        assert len(pos_list) == len(set(pos_list)), (
            f"Independent check FAILED: duplicate cells detected: {pos_list}"
        )

        # Invariant 2: No head-on swap collisions between any two robots
        if self.prev_positions:
            for r_a, pos_a in current_positions.items():
                prev_a = self.prev_positions.get(r_a)
                if not prev_a or prev_a == pos_a:
                    continue
                for r_b, pos_b in current_positions.items():
                    if r_a == r_b:
                        continue
                    prev_b = self.prev_positions.get(r_b)
                    if not prev_b or prev_b == pos_b:
                        continue
                    # Swap check: A moved to B's previous cell and B moved to A's previous cell
                    if pos_a == prev_b and pos_b == prev_a:
                        raise AssertionError(
                            f"Independent check FAILED: Head-on swap detected between {r_a} and {r_b} ({prev_a} <-> {prev_b})"
                        )

        # Invariant 3: Walkable and unblocked
        grid = {(c.pos.x, c.pos.y): c for c in engine.layout.cells}
        for r in engine.robots:
            c_pos = r.cell.as_tuple()
            assert c_pos not in engine.safety_guard.blocked_cells, (
                f"Robot {r.robot_id} is in blocked cell {c_pos}"
            )
            cell = grid.get(c_pos)
            assert cell is not None and cell.is_walkable, (
                f"Robot {r.robot_id} is in non-walkable cell {c_pos}"
            )

        self.prev_positions = current_positions


def test_safety_guard_independent_verification_over_500_ticks() -> None:
    cfg, _ = load_config(scenario_name="standard")
    layout = generate_parametric_layout(cfg.layout)
    skus = generate_catalogue(sku_count=500, seed=42)
    bins, _ = slot_inventory(layout=layout, skus=skus, seed=42)

    engine = SimEngine(config=cfg, layout=layout, skus=skus, bins=bins)
    checker = IndependentSafetyChecker()

    for _ in range(500):
        engine.step()
        checker.verify_tick(engine)


def test_emergency_stop_halts_and_holds_until_resume() -> None:
    cfg, _ = load_config(scenario_name="standard", cli_overrides=["dispatcher.type=wander"])
    layout = generate_parametric_layout(cfg.layout)
    skus = generate_catalogue(sku_count=200, seed=42)
    bins, _ = slot_inventory(layout=layout, skus=skus, seed=42)
    engine = SimEngine(config=cfg, layout=layout, skus=skus, bins=bins)

    # Let robots start moving for 20 ticks
    for _ in range(20):
        engine.step()

    # Issue emergency stop for all robots
    engine.queue_command(EmergencyStopCommand(command_id="CMD-E1", scope="all"))
    engine.step()  # Step 1 applies command

    frozen_positions = {r.robot_id: r.cell.as_tuple() for r in engine.robots}

    # Verify all robots halt and hold for 20 consecutive ticks
    for _ in range(20):
        engine.step()
        current_positions = {r.robot_id: r.cell.as_tuple() for r in engine.robots}
        assert current_positions == frozen_positions, "Robots moved while E-stop was active!"

    # Issue resume
    engine.queue_command(ResumeCommand(command_id="CMD-R1", scope="all"))
    engine.step()
    # Resume stepping: robots should move again
    for _ in range(30):
        engine.step()
    resumed_positions = {r.robot_id: r.cell.as_tuple() for r in engine.robots}
    assert resumed_positions != frozen_positions, (
        "Robots did not resume moving after resume command!"
    )


def test_blocked_cells_and_faulted_robots() -> None:
    cfg, _ = load_config(scenario_name="standard")
    layout = generate_parametric_layout(cfg.layout)
    skus = generate_catalogue(sku_count=200, seed=42)
    bins, _ = slot_inventory(layout=layout, skus=skus, seed=42)
    engine = SimEngine(config=cfg, layout=layout, skus=skus, bins=bins)

    # Block an aisle cell
    target_block = Coordinate(x=6, y=5)
    engine.queue_command(BlockCellsCommand(command_id="CMD-B1", cells=[target_block]))

    # Inject fault into robot 1
    engine.queue_command(
        InjectFaultCommand(command_id="CMD-F1", fault_type="motor_stall", target_id="R-001")
    )
    engine.step()

    # R-001 should be UNAVAILABLE with fault
    r1 = next(r for r in engine.robots if r.robot_id == "R-001")
    assert r1.state == RobotState.UNAVAILABLE
    assert r1.fault == "motor_stall"

    # Step and verify no robot ever enters target_block
    for _ in range(100):
        engine.step()
        for r in engine.robots:
            assert r.cell.as_tuple() != (6, 5), "A robot entered a blocked cell!"

    # Clear fault
    engine.queue_command(ClearFaultCommand(command_id="CMD-C1", target_id="R-001"))
    engine.step()
    assert r1.fault is None


def test_battery_dynamics_none_reaches_zero() -> None:
    cfg, _ = load_config(scenario_name="standard")
    layout = generate_parametric_layout(cfg.layout)
    skus = generate_catalogue(sku_count=200, seed=42)
    bins, _ = slot_inventory(layout=layout, skus=skus, seed=42)
    engine = SimEngine(config=cfg, layout=layout, skus=skus, bins=bins)

    for _ in range(1000):
        engine.step()
        for r in engine.robots:
            assert r.battery_pct > 0.0, f"Robot {r.robot_id} battery reached 0%!"
