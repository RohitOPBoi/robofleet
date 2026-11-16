"""Task and Inventory Lifecycle Manager (Phase 3).
Coordinates multi-step robot tasks (FETCH_BIN, DELIVER_TO_STATION, RETURN_BIN, CARRY_ORDER_TOTE, CHARGE),
enforces stock decrements and stock-out handling, and maintains unit conservation invariants.
"""

from __future__ import annotations

import uuid
from typing import Any

from robofleet.contracts.catalogue import Bin, Sku
from robofleet.contracts.common import Coordinate
from robofleet.contracts.layout import Layout
from robofleet.contracts.order import DelayAttribution, Order, OrderLine, OrderStatus, Task, TaskState, TaskType
from robofleet.contracts.robot import Robot, RobotState
from robofleet.fleet.dispatch_bay import DispatchBayManager
from robofleet.fleet.station import PickingStationManager


class TaskManager:
    """Coordinates fleet tasks, order state progression, and inventory accounting."""

    def __init__(
        self,
        layout: Layout,
        skus: list[Sku],
        bins: list[Bin],
        station_mgr: PickingStationManager,
        dispatch_mgr: DispatchBayManager,
    ) -> None:
        self.layout = layout
        self.skus = {s.sku_id: s for s in skus}
        self.bins = {b.bin_id: b for b in bins}
        self.station_mgr = station_mgr
        self.dispatch_mgr = dispatch_mgr

        # Reverse lookup: sku_id -> list of bin_ids stocking it
        self.sku_to_bins: dict[str, list[str]] = {}
        for b in bins:
            if b.sku_id:
                if b.sku_id not in self.sku_to_bins:
                    self.sku_to_bins[b.sku_id] = []
                self.sku_to_bins[b.sku_id].append(b.bin_id)

        # Inventory conservation ledger
        self.initial_total_units: int = sum(b.quantity for b in bins)
        self.units_in_flight: int = 0
        self.units_completed: int = 0

        # Tasks state
        self.tasks: dict[str, Task] = {}
        self.robot_active_task: dict[str, str | None] = {}
        self.robot_target_cells: dict[str, Coordinate] = {}

        # Order time-in-state tracking for delay attribution
        self.order_timestamps: dict[str, dict[str, int]] = {}

    def get_bin_access_cell(self, bin_id: str) -> Coordinate | None:
        b = self.bins.get(bin_id)
        if not b:
            return None
        # Walkway cell adjacent to shelf
        bx, by = b.cell.x, b.cell.y
        for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            nx, ny = bx + dx, by + dy
            # Check if cell exists in layout and is walkable
            for c in self.layout.cells:
                if c.pos.x == nx and c.pos.y == ny and c.is_walkable:
                    return c.pos
        return b.cell

    def get_task(self, task_id: str) -> Task | None:
        return self.tasks.get(task_id)

    def get_pending_line_for_order(self, order: Order) -> OrderLine | None:
        """Finds first pending line for order that does not already have an active task in flight."""
        active_skus = {
            t.sku_id
            for t in self.tasks.values()
            if t.state in (TaskState.PENDING, TaskState.ASSIGNED, TaskState.EXECUTING)
            and order.order_id in t.order_ids
            and t.sku_id is not None
        }
        for line in order.lines:
            if line.status == "PENDING" and line.sku_id not in active_skus:
                return line
        return None

    def create_fetch_task(
        self,
        order: Order,
        line: OrderLine,
        bin_id: str,
        station_id: str,
        current_tick: int,
    ) -> Task | None:
        access_cell = self.get_bin_access_cell(bin_id)
        if not access_cell:
            return None

        task_id = f"TSK-FETCH-{uuid.uuid4().hex[:6]}"
        task = Task(
            task_id=task_id,
            task_type=TaskType.FETCH_BIN,
            state=TaskState.PENDING,
            target_cell=access_cell,
            order_ids=[order.order_id],
            bin_id=bin_id,
            sku_id=line.sku_id,
            quantity=line.quantity,
            station_id=station_id,
            created_tick=current_tick,
            deadline_tick=order.deadline_tick,
        )
        self.tasks[task_id] = task
        return task

    def assign_task_to_robot(
        self,
        task: Task,
        robot: Robot,
        current_tick: int,
        order: Order | None = None,
    ) -> None:
        task.robot_id = robot.robot_id
        task.state = TaskState.ASSIGNED
        robot.current_task_id = task.task_id
        self.robot_active_task[robot.robot_id] = task.task_id
        self.robot_target_cells[robot.robot_id] = task.target_cell
        if order:
            if not order.tote_id:
                order.tote_id = f"TOTE-{order.order_id[-4:]}"
            if robot.robot_id not in order.assigned_robot_ids:
                order.assigned_robot_ids.append(robot.robot_id)

    def record_stage_time(self, order_id: str, stage: str, current_tick: int) -> None:
        if order_id not in self.order_timestamps:
            self.order_timestamps[order_id] = {}
        if stage not in self.order_timestamps[order_id]:
            self.order_timestamps[order_id][stage] = current_tick

    def compute_delay_attribution(self, order: Order, current_tick: int) -> DelayAttribution:
        ts = self.order_timestamps.get(order.order_id, {})
        t_recv = order.created_tick
        t_plan = ts.get("PLANNED", t_recv)
        t_retr = ts.get("RETRIEVING", t_plan)
        t_at_st = ts.get("AT_STATION", t_retr)
        t_pick = ts.get("PICKING", t_at_st)
        t_cons = ts.get("CONSOLIDATING", t_pick)
        t_pack = ts.get("PACKED", t_cons)
        t_hand = order.handover_tick or current_tick

        total_lateness = max(0, t_hand - order.deadline_tick)
        if total_lateness <= 0:
            return DelayAttribution(total_lateness_ticks=0)

        # Stage durations
        d_wait_robot = max(0, t_plan - t_recv)
        d_travel = max(0, t_at_st - t_retr)
        d_queue = max(0, t_pick - t_at_st)
        d_picking = max(0, t_cons - t_pick)
        d_consolidation = max(0, t_pack - t_cons)
        d_supervisor = max(0, t_hand - t_pack)

        total_duration = max(1, d_wait_robot + d_travel + d_queue + d_picking + d_consolidation + d_supervisor)

        # Proportional WareMax decomposition summing EXACTLY to total_lateness
        p_wait = int(round(total_lateness * (d_wait_robot / total_duration)))
        p_trav = int(round(total_lateness * (d_travel / total_duration)))
        p_que = int(round(total_lateness * (d_queue / total_duration)))
        p_pick = int(round(total_lateness * (d_picking / total_duration)))
        p_cons = int(round(total_lateness * (d_consolidation / total_duration)))
        # Remainder to supervisor to guarantee sum == total_lateness
        p_sup = total_lateness - (p_wait + p_trav + p_que + p_pick + p_cons)

        return DelayAttribution(
            waiting_for_robot_ticks=p_wait,
            travel_ticks=p_trav,
            station_queue_ticks=p_que,
            picking_ticks=p_pick,
            consolidation_ticks=p_cons,
            supervisor_handoff_ticks=p_sup,
            total_lateness_ticks=total_lateness,
        )

    def verify_unit_conservation(self) -> tuple[bool, int, int]:
        """Conservation invariant: units in bins + in-flight + completed == initial."""
        current_bins = sum(b.quantity for b in self.bins.values())
        current_total = current_bins + self.units_in_flight + self.units_completed
        return (current_total == self.initial_total_units, current_total, self.initial_total_units)
