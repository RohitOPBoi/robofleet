"""Tests for Failure Taxonomy and Fault Registry (CA-8, CD-8, Phase 6)."""

from __future__ import annotations

import pytest

from robofleet.chaos.faults import (
    AisleBlockedFault,
    BaseFault,
    BatteryCascadeFault,
    BinMissingStockFault,
    ItemDamagedFault,
    RobotBreakdownFault,
    RobotCommsDropFault,
    StationOfflineFault,
    StationSlowdownFault,
    SupervisorUnavailableFault,
    UrgentOrderBurstFault,
)
from robofleet.chaos.registry import FaultRegistry, fault_registry
from robofleet.config.loader import load_config
from robofleet.contracts.common import Coordinate
from robofleet.contracts.robot import RobotState
from robofleet.layout.generator import generate_parametric_layout
from robofleet.sim.engine import SimEngine


@pytest.fixture
def test_engine() -> SimEngine:
    cfg, _ = load_config(scenario_name="standard")
    layout = generate_parametric_layout(cfg.layout)
    from robofleet.catalogue.generator import generate_catalogue
    from robofleet.catalogue.slotting import slot_inventory

    skus = generate_catalogue(sku_count=100, seed=42)
    bins, _ = slot_inventory(skus=skus, layout=layout, seed=42)
    return SimEngine(config=cfg, layout=layout, skus=skus, bins=bins)


def test_registry_contains_all_10_shipped_fault_types() -> None:
    expected = [
        "aisle_blocked",
        "battery_cascade",
        "bin_missing_stock",
        "item_damaged",
        "robot_breakdown",
        "robot_comms_drop",
        "station_offline",
        "station_slowdown",
        "supervisor_unavailable",
        "urgent_order_burst",
    ]
    registered = fault_registry.list_registered()
    for f in expected:
        assert f in registered


def test_robot_breakdown_and_recovery(test_engine: SimEngine) -> None:
    robot = test_engine.robots[0]
    fault = test_engine.chaos_engine.inject_fault("robot_breakdown", robot.robot_id, duration_ticks=50, tick=10)

    assert fault.is_active
    assert robot.state == RobotState.UNAVAILABLE
    assert robot.fault == "robot_breakdown"
    assert len(test_engine.chaos_engine.get_active_degraded_modes()) == 1

    # Advance 55 ticks to trigger auto-resolution
    for t in range(11, 65):
        test_engine.chaos_engine.step(t)

    assert not fault.is_active
    assert robot.state == RobotState.IDLE
    assert robot.fault is None
    assert len(test_engine.chaos_engine.get_active_degraded_modes()) == 0

    mttr = test_engine.chaos_engine.get_mttr_by_type()
    assert "robot_breakdown" in mttr
    assert mttr["robot_breakdown"] > 0


def test_aisle_blocked_and_recovery(test_engine: SimEngine) -> None:
    blocked_cell = Coordinate(x=6, y=8)
    fault = test_engine.chaos_engine.inject_fault(
        "aisle_blocked",
        "aisle-1",
        duration_ticks=40,
        params={"cells": [[6, 8]]},
        tick=5,
    )
    assert fault.is_active
    assert (6, 8) in test_engine.safety_guard.blocked_cells

    # Auto-resolve
    for t in range(6, 50):
        test_engine.chaos_engine.step(t)

    assert not fault.is_active
    assert (6, 8) not in test_engine.safety_guard.blocked_cells


def test_perfect_storm_injection_and_clear_all(test_engine: SimEngine) -> None:
    faults = test_engine.chaos_engine.inject_perfect_storm(tick=20)
    assert len(faults) >= 4
    assert len(test_engine.chaos_engine.active_faults) >= 4
    assert len(test_engine.chaos_engine.get_active_degraded_modes()) >= 4

    # Clear and heal all
    cleared = test_engine.chaos_engine.clear_and_heal_all(tick=25)
    assert cleared >= 4
    assert len(test_engine.chaos_engine.active_faults) == 0
    assert len(test_engine.chaos_engine.get_active_degraded_modes()) == 0


def test_cd8_add_new_fault_type_at_most_two_files_plus_yaml() -> None:
    """CD-8: add a new fault type in at most 2 files plus YAML."""
    class ScannerLensFogFault(BaseFault):
        fault_type = "scanner_lens_fog"
        default_severity = "LOW"
        target_type = "station"

        def inject(self, engine: Any, tick: int) -> None:
            self.injected_tick = tick
            self.is_active = True
            self.degraded_mode_name = f"Station {self.target_id} lens fog"

        def resolve(self, engine: Any, tick: int) -> None:
            self.resolved_tick = tick
            self.is_active = False

    custom_reg = FaultRegistry()
    custom_reg.register("scanner_lens_fog", ScannerLensFogFault)

    f = custom_reg.create("scanner_lens_fog", "STATION-1", duration_ticks=50)
    assert f.fault_type == "scanner_lens_fog"
    assert f.target_id == "STATION-1"
