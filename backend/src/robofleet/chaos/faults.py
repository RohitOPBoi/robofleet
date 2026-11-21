"""Base Fault contract and implementation of the 10 failure taxonomy types (CA-8).
Each fault defines scope, severity, injection logic, step hooks, and recovery behavior.
Adding a new fault type is at most 2 files plus YAML (CD-8).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Literal
import uuid

from robofleet.contracts.chaos import ChaosFault, DegradedMode, ExceptionItem
from robofleet.contracts.commands import BlockCellsCommand, UnblockCellsCommand
from robofleet.contracts.common import Coordinate
from robofleet.contracts.order import OrderStatus, TaskState, TaskType
from robofleet.contracts.robot import RobotState


class BaseFault(ABC):
    """Abstract base class for all registered fault types."""

    fault_type: str = "base"
    default_severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] = "MEDIUM"
    target_type: Literal["robot", "aisle", "station", "bin", "fleet", "system"] = "system"

    def __init__(
        self,
        target_id: str,
        duration_ticks: int = 200,
        severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] | None = None,
        params: dict[str, Any] | None = None,
        fault_type: str | None = None,
    ) -> None:
        if fault_type:
            self.fault_type = fault_type
        self.fault_id = f"FLT-{self.fault_type[:3].upper()}-{uuid.uuid4().hex[:6]}"
        self.target_id = target_id
        self.duration_ticks = duration_ticks
        self.severity = severity or self.default_severity
        self.params = params or {}
        self.injected_tick: int = 0
        self.resolved_tick: int | None = None
        self.is_active: bool = False
        self.degraded_mode_name: str = ""

    def to_contract(self) -> ChaosFault:
        return ChaosFault(
            fault_id=self.fault_id,
            fault_type=self.fault_type,
            target_id=self.target_id,
            target_type=self.target_type,
            severity=self.severity,
            injected_tick=self.injected_tick,
            duration_ticks=self.duration_ticks,
            resolved_tick=self.resolved_tick,
            params=self.params,
            degraded_mode_name=self.degraded_mode_name,
            is_active=self.is_active,
        )

    @abstractmethod
    def inject(self, engine: Any, tick: int) -> None:
        """Applies fault injection through safe engine channels."""
        ...

    def step(self, engine: Any, tick: int) -> None:
        """Optional per-tick hook for active faults."""
        pass

    @abstractmethod
    def resolve(self, engine: Any, tick: int) -> None:
        """Restores normal operating state."""
        ...


class RobotBreakdownFault(BaseFault):
    """AMR motor, drivetrain, or hardware breakdown."""

    fault_type = "robot_breakdown"
    default_severity = "CRITICAL"
    target_type = "robot"

    def inject(self, engine: Any, tick: int) -> None:
        self.injected_tick = tick
        self.is_active = True
        self.degraded_mode_name = f"AMR {self.target_id} hardware breakdown"

        for robot in getattr(engine, "robots", []):
            if robot.robot_id == self.target_id:
                robot.fault = self.fault_type
                robot.state = RobotState.UNAVAILABLE

                # Reassign any active task back to pending queue
                if robot.current_task_id and hasattr(engine, "task_mgr"):
                    task = engine.task_mgr.tasks.get(robot.current_task_id)
                    if task and task.state in (TaskState.ASSIGNED, TaskState.EXECUTING):
                        task.state = TaskState.PENDING
                        task.robot_id = None
                        engine.emit_event(
                            "chaos.task_reassigned",
                            {"task_id": task.task_id, "from_robot": robot.robot_id},
                        )

                # Physical tote recovery: if robot was carrying merchandise, flag for human retrieval
                if robot.carrying:
                    tote_id = robot.carrying[0]
                    exc = ExceptionItem(
                        exception_type="physical_tote_recovery",
                        severity="HIGH",
                        entity_id=robot.robot_id,
                        location=robot.cell,
                        raised_tick=tick,
                        deadline_tick=tick + 300,
                        default_action="dispatch_retrieval_runner",
                        recommended_action="Dispatch human runner to recover tote from faulted AMR",
                        available_actions=["dispatch_retrieval_runner", "tow_robot_with_tote"],
                    )
                    if hasattr(engine, "exceptions_queue"):
                        engine.exceptions_queue.add_exception(exc)

                engine.emit_event(
                    "chaos.fault_injected",
                    {"fault_type": self.fault_type, "robot_id": self.target_id, "cell": robot.cell.as_tuple()},
                )
                break

    def resolve(self, engine: Any, tick: int) -> None:
        self.resolved_tick = tick
        self.is_active = False
        for robot in getattr(engine, "robots", []):
            if robot.robot_id == self.target_id:
                robot.fault = None
                robot.state = RobotState.IDLE
                engine.emit_event(
                    "chaos.fault_resolved",
                    {"fault_type": self.fault_type, "robot_id": self.target_id, "recovery_ticks": tick - self.injected_tick},
                )
                break


class RobotCommsDropFault(BaseFault):
    """AMR wireless communication link dropped."""

    fault_type = "robot_comms_drop"
    default_severity = "HIGH"
    target_type = "robot"

    def inject(self, engine: Any, tick: int) -> None:
        self.injected_tick = tick
        self.is_active = True
        self.degraded_mode_name = f"AMR {self.target_id} radio link lost"

        for robot in getattr(engine, "robots", []):
            if robot.robot_id == self.target_id:
                robot.fault = self.fault_type
                robot.state = RobotState.WAITING
                engine.emit_event(
                    "chaos.fault_injected",
                    {"fault_type": self.fault_type, "robot_id": self.target_id},
                )
                break

    def resolve(self, engine: Any, tick: int) -> None:
        self.resolved_tick = tick
        self.is_active = False
        for robot in getattr(engine, "robots", []):
            if robot.robot_id == self.target_id:
                robot.fault = None
                robot.state = RobotState.IDLE
                engine.emit_event(
                    "chaos.fault_resolved",
                    {"fault_type": self.fault_type, "robot_id": self.target_id, "recovery_ticks": tick - self.injected_tick},
                )
                break


class BatteryCascadeFault(BaseFault):
    """Thermal or BMS anomaly causing accelerated battery drain."""

    fault_type = "battery_cascade"
    default_severity = "HIGH"
    target_type = "fleet"

    def inject(self, engine: Any, tick: int) -> None:
        self.injected_tick = tick
        self.is_active = True
        self.degraded_mode_name = "Fleet battery cascade: accelerated drain active"

        drain_multiplier = float(self.params.get("drain_multiplier", 4.0))
        for robot in getattr(engine, "robots", []):
            robot.battery_pct = max(12.0, robot.battery_pct - 25.0)

        engine.emit_event(
            "chaos.fault_injected",
            {"fault_type": self.fault_type, "drain_multiplier": drain_multiplier},
        )

    def resolve(self, engine: Any, tick: int) -> None:
        self.resolved_tick = tick
        self.is_active = False
        engine.emit_event(
            "chaos.fault_resolved",
            {"fault_type": self.fault_type, "recovery_ticks": tick - self.injected_tick},
        )


class AisleBlockedFault(BaseFault):
    """Spill, dropped pallet, or human obstruction blocking aisle walkway cells."""

    fault_type = "aisle_blocked"
    default_severity = "MEDIUM"
    target_type = "aisle"

    def __init__(self, target_id: str, duration_ticks: int = 200, **kwargs: Any) -> None:
        super().__init__(target_id, duration_ticks, **kwargs)
        self.blocked_coords: list[Coordinate] = []

    def inject(self, engine: Any, tick: int) -> None:
        self.injected_tick = tick
        self.is_active = True
        raw_cells = self.params.get("cells", [])

        if not raw_cells and hasattr(engine, "layout"):
            walkable = [c.pos for c in engine.layout.cells if c.is_walkable]
            if len(walkable) >= 10:
                self.blocked_coords = [walkable[4], walkable[5]]
        else:
            for item in raw_cells:
                if isinstance(item, (list, tuple)) and len(item) == 2:
                    self.blocked_coords.append(Coordinate(x=item[0], y=item[1]))
                elif isinstance(item, dict):
                    self.blocked_coords.append(Coordinate(**item))

        self.degraded_mode_name = f"Aisle blocked at {len(self.blocked_coords)} cells"
        if hasattr(engine, "safety_guard") and self.blocked_coords:
            engine.safety_guard.block_cells(self.blocked_coords)

        engine.emit_event(
            "chaos.fault_injected",
            {
                "fault_type": self.fault_type,
                "target_id": self.target_id,
                "cells": [c.model_dump() for c in self.blocked_coords],
            },
        )

    def resolve(self, engine: Any, tick: int) -> None:
        self.resolved_tick = tick
        self.is_active = False
        if hasattr(engine, "safety_guard") and self.blocked_coords:
            engine.safety_guard.unblock_cells(self.blocked_coords)

        engine.emit_event(
            "chaos.fault_resolved",
            {
                "fault_type": self.fault_type,
                "target_id": self.target_id,
                "recovery_ticks": tick - self.injected_tick,
            },
        )


class BinMissingStockFault(BaseFault):
    """Inventory discrepancy: bin physical count missing/zero."""

    fault_type = "bin_missing_stock"
    default_severity = "MEDIUM"
    target_type = "bin"

    def inject(self, engine: Any, tick: int) -> None:
        self.injected_tick = tick
        self.is_active = True
        self.degraded_mode_name = f"Stock-out discrepancy at bin {self.target_id}"

        bin_obj = None
        if hasattr(engine, "bins"):
            for b in engine.bins:
                if b.bin_id == self.target_id:
                    bin_obj = b
                    b.quantity = 0
                    break

        engine.emit_event(
            "chaos.fault_injected",
            {"fault_type": self.fault_type, "bin_id": self.target_id},
        )

    def resolve(self, engine: Any, tick: int) -> None:
        self.resolved_tick = tick
        self.is_active = False
        # Restock bin
        if hasattr(engine, "bins"):
            for b in engine.bins:
                if b.bin_id == self.target_id:
                    b.quantity = 15
                    break

        engine.emit_event(
            "chaos.fault_resolved",
            {"fault_type": self.fault_type, "bin_id": self.target_id, "recovery_ticks": tick - self.injected_tick},
        )


class ItemDamagedFault(BaseFault):
    """Damaged packaging, broken seal, or dropped merchandise."""

    fault_type = "item_damaged"
    default_severity = "HIGH"
    target_type = "bin"

    def inject(self, engine: Any, tick: int) -> None:
        self.injected_tick = tick
        self.is_active = True
        self.degraded_mode_name = f"Damaged merchandise detected for {self.target_id}"

        exc = ExceptionItem(
            exception_type="damaged_item",
            severity="HIGH",
            entity_id=self.target_id,
            raised_tick=tick,
            deadline_tick=tick + 250,
            default_action="write_off_and_reslot",
            recommended_action="Isolate damaged item and pull replacement from replica bin",
            available_actions=["write_off_and_reslot", "substitute_replica", "return_to_vendor"],
        )
        if hasattr(engine, "exceptions_queue"):
            engine.exceptions_queue.add_exception(exc)

        engine.emit_event(
            "chaos.fault_injected",
            {"fault_type": self.fault_type, "target_id": self.target_id},
        )

    def resolve(self, engine: Any, tick: int) -> None:
        self.resolved_tick = tick
        self.is_active = False
        engine.emit_event(
            "chaos.fault_resolved",
            {"fault_type": self.fault_type, "target_id": self.target_id, "recovery_ticks": tick - self.injected_tick},
        )


class StationSlowdownFault(BaseFault):
    """Picker ergonomics issue or scanner hardware slowdown."""

    fault_type = "station_slowdown"
    default_severity = "MEDIUM"
    target_type = "station"

    def inject(self, engine: Any, tick: int) -> None:
        self.injected_tick = tick
        self.is_active = True
        self.degraded_mode_name = f"Picking station {self.target_id} throughput halved"

        if hasattr(engine, "station_mgr") and hasattr(engine.station_mgr, "base_pick_time_ticks"):
            engine.station_mgr.base_pick_time_ticks = int(engine.station_mgr.base_pick_time_ticks * 2.5)

        engine.emit_event(
            "chaos.fault_injected",
            {"fault_type": self.fault_type, "station_id": self.target_id},
        )

    def resolve(self, engine: Any, tick: int) -> None:
        self.resolved_tick = tick
        self.is_active = False
        if hasattr(engine, "station_mgr") and hasattr(engine.station_mgr, "base_pick_time_ticks"):
            engine.station_mgr.base_pick_time_ticks = max(10, int(engine.station_mgr.base_pick_time_ticks / 2.5))

        engine.emit_event(
            "chaos.fault_resolved",
            {"fault_type": self.fault_type, "station_id": self.target_id, "recovery_ticks": tick - self.injected_tick},
        )


class StationOfflineFault(BaseFault):
    """Tote conveyor jam or emergency station maintenance."""

    fault_type = "station_offline"
    default_severity = "CRITICAL"
    target_type = "station"

    def inject(self, engine: Any, tick: int) -> None:
        self.injected_tick = tick
        self.is_active = True
        self.degraded_mode_name = f"Station {self.target_id} offline: rerouting traffic"

        if hasattr(engine, "station_mgr"):
            # Mark station offline in metadata
            st_def = engine.station_mgr.station_defs.get(self.target_id)
            if st_def:
                st_def.is_active = False

        engine.emit_event(
            "chaos.fault_injected",
            {"fault_type": self.fault_type, "station_id": self.target_id},
        )

    def resolve(self, engine: Any, tick: int) -> None:
        self.resolved_tick = tick
        self.is_active = False
        if hasattr(engine, "station_mgr"):
            st_def = engine.station_mgr.station_defs.get(self.target_id)
            if st_def:
                st_def.is_active = True

        engine.emit_event(
            "chaos.fault_resolved",
            {"fault_type": self.fault_type, "station_id": self.target_id, "recovery_ticks": tick - self.injected_tick},
        )


class UrgentOrderBurstFault(BaseFault):
    """Spike in sudden priority/express orders."""

    fault_type = "urgent_order_burst"
    default_severity = "HIGH"
    target_type = "system"

    def inject(self, engine: Any, tick: int) -> None:
        self.injected_tick = tick
        self.is_active = True
        burst_count = int(self.params.get("order_count", 10))
        self.degraded_mode_name = f"Urgent demand surge ({burst_count} priority orders)"

        if hasattr(engine, "order_source") and hasattr(engine.order_source, "inject_rush_orders"):
            engine.order_source.inject_rush_orders(count=burst_count, current_tick=tick)

        engine.emit_event(
            "chaos.fault_injected",
            {"fault_type": self.fault_type, "burst_count": burst_count},
        )

    def resolve(self, engine: Any, tick: int) -> None:
        self.resolved_tick = tick
        self.is_active = False
        engine.emit_event(
            "chaos.fault_resolved",
            {"fault_type": self.fault_type, "recovery_ticks": tick - self.injected_tick},
        )


class SupervisorUnavailableFault(BaseFault):
    """Shift change, break, or network outage for supervisor station."""

    fault_type = "supervisor_unavailable"
    default_severity = "MEDIUM"
    target_type = "system"

    def inject(self, engine: Any, tick: int) -> None:
        self.injected_tick = tick
        self.is_active = True
        self.degraded_mode_name = "Supervisor unavailable: automatic escalation active"

        if hasattr(engine, "dispatch_mgr"):
            engine.dispatch_mgr.base_handoff_ticks *= 3

        engine.emit_event(
            "chaos.fault_injected",
            {"fault_type": self.fault_type},
        )

    def resolve(self, engine: Any, tick: int) -> None:
        self.resolved_tick = tick
        self.is_active = False
        if hasattr(engine, "dispatch_mgr"):
            engine.dispatch_mgr.base_handoff_ticks = max(20, engine.dispatch_mgr.base_handoff_ticks // 3)

        engine.emit_event(
            "chaos.fault_resolved",
            {"fault_type": self.fault_type, "recovery_ticks": tick - self.injected_tick},
        )
