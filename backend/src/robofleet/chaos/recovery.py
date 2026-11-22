"""Self-Healing and Degraded-Mode Recovery Logic (Phase 6).
Executes algorithmic first recovery strategies:
1. Task Reassignment from failed/stalled AMRs back to pool with priority preservation.
2. Dynamic Rerouting around blocked aisles and inaccessible zones.
3. Item Substitution from replica bins or short-line policies (partial, delay, cancel).
4. Station Failover queue rebalancing when picking stations slow down or jam.
"""

from __future__ import annotations

import logging
from typing import Any, Literal

from robofleet.contracts.chaos import DegradedMode, ExceptionItem
from robofleet.contracts.common import Coordinate
from robofleet.contracts.order import Order, OrderLine, OrderStatus, Task, TaskState, TaskType
from robofleet.contracts.robot import Robot, RobotState

logger = logging.getLogger(__name__)


class SelfHealingManager:
    """Coordinates autonomous self-healing recovery actions under chaos duress."""

    def __init__(self, engine: Any) -> None:
        self.engine = engine
        self.degraded_modes: dict[str, DegradedMode] = {}
        self.recovered_orders_count: int = 0
        self.substitutions_performed: int = 0
        self.reroutes_performed: int = 0

    def register_degraded_mode(self, fault_id: str, name: str, description: str, tick: int) -> DegradedMode:
        mode = DegradedMode(
            fault_id=fault_id,
            name=name,
            description=description,
            active_since_tick=tick,
        )
        self.degraded_modes[fault_id] = mode
        self.engine.emit_event(
            "chaos.degraded_mode_entered",
            {"fault_id": fault_id, "name": name, "description": description},
        )
        return mode

    def clear_degraded_mode(self, fault_id: str, tick: int) -> None:
        if fault_id in self.degraded_modes:
            mode = self.degraded_modes.pop(fault_id)
            mode.resolved_tick = tick
            self.engine.emit_event(
                "chaos.degraded_mode_cleared",
                {"fault_id": fault_id, "name": mode.name, "duration_ticks": tick - mode.active_since_tick},
            )

    def reassign_robot_tasks(self, robot_id: str, tick: int) -> list[str]:
        """Reassigns in-flight tasks from a broken or stalled robot back to pool."""
        reassigned_task_ids: list[str] = []
        if not hasattr(self.engine, "task_mgr"):
            return reassigned_task_ids

        for task in self.engine.task_mgr.tasks.values():
            if task.robot_id == robot_id and task.state in (TaskState.ASSIGNED, TaskState.EXECUTING):
                task.state = TaskState.PENDING
                task.robot_id = None
                reassigned_task_ids.append(task.task_id)
                self.engine.emit_event(
                    "recovery.task_reassigned",
                    {"task_id": task.task_id, "from_robot": robot_id, "target_cell": task.target_cell.as_tuple()},
                )

        return reassigned_task_ids

    def substitute_missing_or_damaged_item(
        self,
        order_id: str,
        sku_id: str,
        quantity: int,
        reason: str,
        tick: int,
        short_policy: Literal["partial_fulfilment", "delay", "cancel"] = "partial_fulfilment",
    ) -> bool:
        """Finds a replica bin stocking the required SKU and creates a replacement task.
        If no replica stock exists, executes short line policy.
        """
        task_mgr = getattr(self.engine, "task_mgr", None)
        if not task_mgr:
            return False

        order = next((o for o in self.engine.orders if o.order_id == order_id), None)
        if not order:
            return False

        # 1. Search replica bins
        candidate_bin_ids = task_mgr.sku_to_bins.get(sku_id, [])
        replica_bin = None
        for b_id in candidate_bin_ids:
            b = task_mgr.bins.get(b_id)
            if b and b.quantity >= quantity:
                replica_bin = b
                break

        if replica_bin:
            # Create substitute fetch task
            station_id = order.assigned_station_id or (
                self.engine.layout.stations[0].station_id if self.engine.layout.stations else "STATION-1"
            )
            line = next((l for l in order.lines if l.sku_id == sku_id), None)
            if line:
                task = task_mgr.create_fetch_task(
                    order=order,
                    line=line,
                    bin_id=replica_bin.bin_id,
                    station_id=station_id,
                    current_tick=tick,
                )
                self.substitutions_performed += 1
                self.engine.emit_event(
                    "recovery.item_substituted",
                    {
                        "order_id": order_id,
                        "sku_id": sku_id,
                        "replica_bin": replica_bin.bin_id,
                        "reason": reason,
                    },
                )
                return True

        # 2. No replica stock available: execute Short-Line Policy
        line = next((l for l in order.lines if l.sku_id == sku_id), None)
        if line:
            line.status = "SHORT"

        if short_policy == "partial_fulfilment":
            order.status = OrderStatus.FAILED_PARTIAL
            self.engine.emit_event(
                "recovery.short_line_handled",
                {"order_id": order_id, "sku_id": sku_id, "policy": "partial_fulfilment"},
            )
        elif short_policy == "delay":
            order.deadline_tick += 300  # Extend SLA deadline
            self.engine.emit_event(
                "recovery.short_line_handled",
                {"order_id": order_id, "sku_id": sku_id, "policy": "delay", "new_deadline": order.deadline_tick},
            )
        elif short_policy == "cancel":
            order.status = OrderStatus.CANCELLED
            self.engine.emit_event(
                "recovery.short_line_handled",
                {"order_id": order_id, "sku_id": sku_id, "policy": "cancel"},
            )

        return False

    def rebalance_station_queues(self, offline_or_slow_station_id: str, tick: int) -> int:
        """Diverts robots and orders away from an offline or slow picking station."""
        st_mgr = getattr(self.engine, "station_mgr", None)
        if not st_mgr:
            return 0

        operational_stations = [
            s.station_id
            for s in self.engine.layout.stations
            if s.station_id != offline_or_slow_station_id
            and getattr(s, "is_active", True)
            and st_mgr.can_enqueue_robot(s.station_id)
        ]
        if not operational_stations:
            return 0

        rebalanced_count = 0
        queued_robots = list(st_mgr.robot_queues.get(offline_or_slow_station_id, []))
        for r_id in queued_robots:
            target_st = operational_stations[rebalanced_count % len(operational_stations)]
            st_mgr.remove_robot(offline_or_slow_station_id, r_id)
            if st_mgr.enqueue_robot(target_st, r_id):
                rebalanced_count += 1
                self.engine.emit_event(
                    "recovery.station_rerouted",
                    {"robot_id": r_id, "from_station": offline_or_slow_station_id, "to_station": target_st},
                )

        return rebalanced_count
