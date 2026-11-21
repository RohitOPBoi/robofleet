"""Chaos Simulation Engine (Phase 6).
Coordinates scheduled and manual fault injection, evaluates recovery timelines,
tracks MTTR and degraded modes, and integrates into the SimEngine tick lifecycle.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
import yaml

from robofleet.chaos.faults import BaseFault
from robofleet.chaos.recovery import SelfHealingManager
from robofleet.chaos.registry import fault_registry
from robofleet.contracts.chaos import ChaosFault, DegradedMode

logger = logging.getLogger(__name__)


class ChaosEngine:
    """Coordinates fault injection, incident timelines, and recovery tracking."""

    def __init__(self, engine: Any, scenario_path: str | Path | None = None) -> None:
        self.engine = engine
        self.recovery_mgr = SelfHealingManager(engine=engine)
        self.active_faults: list[BaseFault] = []
        self.history_faults: list[BaseFault] = []
        self.scheduled_faults: list[dict[str, Any]] = []

        # Metric tracking: fault_type -> list of recovery times in ticks
        self.recovery_times_by_type: dict[str, list[int]] = {}
        self.total_incidents_count: int = 0
        self.detection_delays: list[int] = []

        if scenario_path:
            self.load_chaos_scenario(scenario_path)

    def load_chaos_scenario(self, path: str | Path) -> None:
        p = Path(path)
        if not p.exists():
            logger.warning("[ChaosEngine] Scenario file %s not found", path)
            return

        with open(p, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        self.scheduled_faults = data.get("scheduled_faults", [])
        logger.info("[ChaosEngine] Loaded %d scheduled faults from %s", len(self.scheduled_faults), path)

    def inject_fault(
        self,
        fault_type: str,
        target_id: str,
        duration_ticks: int = 200,
        severity: str | None = None,
        params: dict[str, Any] | None = None,
        tick: int = 0,
    ) -> BaseFault:
        """Injects a registered fault type immediately."""
        fault = fault_registry.create(
            fault_type=fault_type,
            target_id=target_id,
            duration_ticks=duration_ticks,
            severity=severity,
            params=params,
        )
        fault.inject(self.engine, tick)
        self.active_faults.append(fault)
        self.total_incidents_count += 1

        # Register degraded mode
        self.recovery_mgr.register_degraded_mode(
            fault_id=fault.fault_id,
            name=fault.degraded_mode_name,
            description=f"Fault {fault.fault_type} active on {fault.target_id}",
            tick=tick,
        )

        return fault

    def inject_perfect_storm(self, tick: int) -> list[BaseFault]:
        """Triggers simultaneous compound faults: breakdown, aisle obstruction, station slowdown, and urgent rush."""
        injected: list[BaseFault] = []

        # 1. Robot breakdown
        if self.engine.robots:
            r_target = self.engine.robots[0].robot_id
            f1 = self.inject_fault("robot_breakdown", r_target, duration_ticks=150, tick=tick)
            injected.append(f1)

        # 2. Aisle obstruction
        f2 = self.inject_fault("aisle_blocked", "aisle-1", duration_ticks=200, tick=tick)
        injected.append(f2)

        # 3. Station slowdown
        if self.engine.layout.stations:
            st_target = self.engine.layout.stations[0].station_id
            f3 = self.inject_fault("station_slowdown", st_target, duration_ticks=180, tick=tick)
            injected.append(f3)

        # 4. Urgent order burst
        f4 = self.inject_fault(
            "urgent_order_burst",
            "system",
            duration_ticks=100,
            params={"order_count": 8},
            tick=tick,
        )
        injected.append(f4)

        return injected

    def resolve_fault(self, fault_id: str, tick: int) -> bool:
        """Resolves an active fault and tracks its recovery duration."""
        target_fault = next((f for f in self.active_faults if f.fault_id == fault_id), None)
        if not target_fault:
            return False

        target_fault.resolve(self.engine, tick)
        self.active_faults.remove(target_fault)
        self.history_faults.append(target_fault)

        # Record MTTR
        recovery_duration = max(1, tick - target_fault.injected_tick)
        if target_fault.fault_type not in self.recovery_times_by_type:
            self.recovery_times_by_type[target_fault.fault_type] = []
        self.recovery_times_by_type[target_fault.fault_type].append(recovery_duration)

        # Clear degraded mode
        self.recovery_mgr.clear_degraded_mode(target_fault.fault_id, tick)
        return True

    def clear_and_heal_all(self, tick: int) -> int:
        """Heals all active faults in the simulation."""
        cleared_count = len(self.active_faults)
        for fault in list(self.active_faults):
            self.resolve_fault(fault.fault_id, tick)
        return cleared_count

    def step(self, tick: int) -> None:
        """Advances active chaos incidents and evaluates scheduled injections."""
        # 1. Evaluate scheduled scenario faults
        remaining_schedules: list[dict[str, Any]] = []
        for sched in self.scheduled_faults:
            s_tick = sched.get("tick", 0)
            if tick >= s_tick:
                self.inject_fault(
                    fault_type=sched["fault_type"],
                    target_id=sched.get("target_id", "system"),
                    duration_ticks=sched.get("duration_ticks", 200),
                    severity=sched.get("severity"),
                    params=sched.get("params", {}),
                    tick=tick,
                )
            else:
                remaining_schedules.append(sched)
        self.scheduled_faults = remaining_schedules

        # 2. Step active faults and auto-resolve expired durations
        for fault in list(self.active_faults):
            fault.step(self.engine, tick)
            if tick >= fault.injected_tick + fault.duration_ticks:
                self.resolve_fault(fault.fault_id, tick)

    def get_mttr_by_type(self) -> dict[str, float]:
        """Returns mean time to recovery in seconds for each fault type."""
        tick_hz = getattr(self.engine.clock, "tick_hz", 10)
        result: dict[str, float] = {}
        for ftype, durations in self.recovery_times_by_type.items():
            if durations:
                mean_ticks = sum(durations) / len(durations)
                result[ftype] = round(mean_ticks / tick_hz, 2)
            else:
                result[ftype] = 0.0
        return result

    def get_active_degraded_modes(self) -> list[DegradedMode]:
        return list(self.recovery_mgr.degraded_modes.values())
