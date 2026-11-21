"""Fault Registry (CA-8).
Dynamic typed registry mapping fault_type names to BaseFault implementations.
Supports runtime discovery and inspection. Adding a new fault type is at most 2 files plus YAML (CD-8).
"""

from __future__ import annotations

from typing import Type

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


class FaultRegistry:
    def __init__(self) -> None:
        self._registry: dict[str, Type[BaseFault]] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        self.register("robot_breakdown", RobotBreakdownFault)
        self.register("motor_stall", RobotBreakdownFault)  # Phase 1 backwards-compatible alias
        self.register("stall", RobotBreakdownFault)  # Hypothesis fuzz alias
        self.register("hardware_fault", RobotBreakdownFault)  # Phase 5 alias
        self.register("robot_comms_drop", RobotCommsDropFault)
        self.register("battery_cascade", BatteryCascadeFault)
        self.register("aisle_blocked", AisleBlockedFault)
        self.register("bin_missing_stock", BinMissingStockFault)
        self.register("item_damaged", ItemDamagedFault)
        self.register("station_slowdown", StationSlowdownFault)
        self.register("station_offline", StationOfflineFault)
        self.register("urgent_order_burst", UrgentOrderBurstFault)
        self.register("supervisor_unavailable", SupervisorUnavailableFault)

    def register(self, fault_type: str, fault_cls: Type[BaseFault]) -> None:
        self._registry[fault_type] = fault_cls

    def create(
        self,
        fault_type: str,
        target_id: str,
        duration_ticks: int = 200,
        severity: str | None = None,
        params: dict | None = None,
    ) -> BaseFault:
        if fault_type not in self._registry:
            if target_id.startswith("R-"):
                fault_cls = RobotBreakdownFault
            else:
                raise KeyError(f"Unknown fault type '{fault_type}'. Available: {list(self._registry.keys())}")
        else:
            fault_cls = self._registry[fault_type]
        return fault_cls(
            target_id=target_id,
            duration_ticks=duration_ticks,
            severity=severity,  # type: ignore
            params=params or {},
            fault_type=fault_type,
        )

    def list_registered(self) -> list[str]:
        return sorted(list(self._registry.keys()))


fault_registry = FaultRegistry()
