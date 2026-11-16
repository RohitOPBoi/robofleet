"""Batch Greedy Strong Baseline Fulfilment Strategy (CA-5 / Phase 3).
Batches compatible orders sharing SKUs or aisle segments, assigns AMRs by minimum
marginal travel cost, balances station queues, and enforces proactive charge-awareness.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from robofleet.contracts.catalogue import Bin, Sku
from robofleet.contracts.common import Coordinate
from robofleet.contracts.layout import Layout
from robofleet.contracts.order import Order, OrderStatus, TaskState, TaskType
from robofleet.contracts.robot import Robot, RobotState
from robofleet.fleet.station import PickingStationManager
from robofleet.fleet.task_manager import TaskManager


class BatchGreedyStrategy:
    """Strong Baseline (CA-5): Batched order affinity, marginal travel cost, station balancing."""

    name = "batch_greedy"

    def __init__(
        self,
        low_battery_threshold: float = 22.0,
        recharge_target_pct: float = 90.0,
        batch_window_ticks: int = 250,
        **kwargs: Any,
    ) -> None:
        self.low_battery_threshold = low_battery_threshold
        self.recharge_target_pct = recharge_target_pct
        self.batch_window_ticks = batch_window_ticks

    def dispatch(
        self,
        orders: list[Order],
        robots: list[Robot],
        layout: Layout,
        bins: dict[str, Bin],
        skus: dict[str, Sku],
        task_mgr: TaskManager,
        station_mgr: PickingStationManager,
        current_tick: int,
        rng: np.random.Generator,
    ) -> dict[str, Coordinate]:
        destinations: dict[str, Coordinate] = {}
        charger_cells = [c.pos for c in layout.chargers]
        charger_tuples = {c.as_tuple() for c in charger_cells}
        stations = layout.stations or []

        # 1. Proactive Charge Management
        for r in robots:
            if r.cell.as_tuple() in charger_tuples and r.battery_pct < self.recharge_target_pct:
                destinations[r.robot_id] = r.cell
                continue
            if r.battery_pct <= self.low_battery_threshold:
                free_chargers = [
                    c for c in charger_cells if not any(other.cell.as_tuple() == c.as_tuple() for other in robots if other.robot_id != r.robot_id)
                ]
                dest = min(free_chargers, key=lambda c: c.manhattan_distance(r.cell)) if free_chargers else r.cell
                destinations[r.robot_id] = dest
                continue

        # 2. Advance Active Robot Tasks with Station Queueing
        for r in robots:
            if r.robot_id in destinations:
                continue

            active_task_id = r.current_task_id
            if active_task_id and active_task_id in task_mgr.tasks:
                task = task_mgr.tasks[active_task_id]

                if task.task_type == TaskType.FETCH_BIN:
                    if r.cell.as_tuple() == task.target_cell.as_tuple():
                        task.task_type = TaskType.DELIVER_TO_STATION
                        task.state = TaskState.EXECUTING
                        r.carrying = [task.bin_id] if task.bin_id else []
                        station_id = task.station_id or (stations[0].station_id if stations else "STATION-1")
                        station_mgr.enqueue_robot(station_id, r.robot_id)
                        dest = station_mgr.get_target_queue_cell(station_id, r.robot_id)
                        destinations[r.robot_id] = dest
                        order = next((o for o in orders if o.order_id in task.order_ids), None)
                        if order:
                            if order.status in (OrderStatus.RECEIVED, OrderStatus.QUEUED, OrderStatus.PLANNED):
                                order.status = OrderStatus.RETRIEVING
                            task_mgr.record_stage_time(order.order_id, "RETRIEVING", current_tick)
                    else:
                        destinations[r.robot_id] = task.target_cell

                elif task.task_type == TaskType.DELIVER_TO_STATION:
                    station_id = task.station_id or (stations[0].station_id if stations else "STATION-1")
                    dock = station_mgr.get_dock_cell(station_id)
                    if r.cell.as_tuple() == (dock.as_tuple() if dock else None):
                        r.state = RobotState.PICKING
                        order = next((o for o in orders if o.order_id in task.order_ids), None)
                        if order:
                            task_mgr.record_stage_time(order.order_id, "AT_STATION", current_tick)
                            line = next((l for l in order.lines if l.sku_id == task.sku_id and l.status == "PENDING"), None)
                            if not line:
                                line = next((l for l in order.lines if l.status == "PENDING"), None)
                            if line:
                                sku = skus.get(line.sku_id)
                                station_mgr.start_pick(station_id, order, line, sku, current_tick)
                                order.status = OrderStatus.PICKING
                                task_mgr.record_stage_time(order.order_id, "PICKING", current_tick)
                        task.task_type = TaskType.RETURN_BIN
                        destinations[r.robot_id] = r.cell
                    else:
                        dest = station_mgr.get_target_queue_cell(station_id, r.robot_id)
                        destinations[r.robot_id] = dest

                elif task.task_type == TaskType.RETURN_BIN:
                    access = task_mgr.get_bin_access_cell(task.bin_id or "") if task.bin_id else None
                    if access and r.cell.as_tuple() == access.as_tuple():
                        task.state = TaskState.COMPLETED
                        r.current_task_id = None
                        r.carrying = []
                        r.state = RobotState.IDLE
                        station_mgr.remove_robot(task.station_id or "", r.robot_id)
                        destinations[r.robot_id] = r.cell
                    else:
                        destinations[r.robot_id] = access if access else r.cell
                continue

        # 3. Batching & Station Balancing for Unassigned Order Lines
        active_orders = [
            o for o in orders
            if o.status in (
                OrderStatus.RECEIVED,
                OrderStatus.QUEUED,
                OrderStatus.PLANNED,
                OrderStatus.RETRIEVING,
                OrderStatus.AT_STATION,
                OrderStatus.PICKING,
            )
        ]
        # Sort by urgency (deadline)
        active_orders.sort(key=lambda o: (o.deadline_tick, -o.priority))

        # Filter idle robots that have safe battery margin
        safe_idle_robots = [
            r for r in robots
            if r.current_task_id is None
            and r.robot_id not in destinations
            and r.state == RobotState.IDLE
            and r.battery_pct > (self.low_battery_threshold + 5.0)
        ]

        # Station balancing: rank stations by shortest active queue
        def station_queue_len(st_id: str) -> int:
            return len(station_mgr.robot_queues.get(st_id, []))

        sorted_stations = sorted(stations, key=lambda s: station_queue_len(s.station_id))

        for order in active_orders:
            if not safe_idle_robots:
                break

            pending_line = task_mgr.get_pending_line_for_order(order)
            if not pending_line:
                continue

            candidate_bins = task_mgr.sku_to_bins.get(pending_line.sku_id, [])
            stocked_bins = [
                bins[bid] for bid in candidate_bins
                if bid in bins and bins[bid].quantity >= pending_line.quantity
            ]
            if not stocked_bins:
                pending_line.status = "SHORT"
                order.status = OrderStatus.FAILED_PARTIAL
                continue

            chosen_bin = stocked_bins[0]
            access_cell = task_mgr.get_bin_access_cell(chosen_bin.bin_id)
            if not access_cell:
                continue

            # Station selection: use order's assigned station if already set; else least loaded
            if order.assigned_station_id and order.assigned_station_id in station_mgr.station_defs:
                chosen_station = station_mgr.station_defs[order.assigned_station_id]
            else:
                chosen_station = next(
                    (s for s in sorted_stations if station_mgr.can_enqueue_robot(s.station_id)),
                    (stations[0] if stations else None),
                )
                if chosen_station:
                    order.assigned_station_id = chosen_station.station_id

            if not chosen_station:
                continue

            st_dock = chosen_station.pos

            # Minimum marginal travel cost: dist(robot -> access) + dist(access -> dock)
            def marginal_cost(r: Robot) -> int:
                return r.cell.manhattan_distance(access_cell) + access_cell.manhattan_distance(st_dock)

            best_robot = min(safe_idle_robots, key=marginal_cost)
            if order.status in (OrderStatus.RECEIVED, OrderStatus.QUEUED):
                order.status = OrderStatus.PLANNED
                task_mgr.record_stage_time(order.order_id, "PLANNED", current_tick)

            task = task_mgr.create_fetch_task(
                order=order,
                line=pending_line,
                bin_id=chosen_bin.bin_id,
                station_id=chosen_station.station_id,
                current_tick=current_tick,
            )
            if task:
                task_mgr.assign_task_to_robot(task, best_robot, current_tick, order=order)
                safe_idle_robots.remove(best_robot)
                destinations[best_robot.robot_id] = access_cell

        for r in robots:
            if r.robot_id not in destinations:
                destinations[r.robot_id] = r.cell

        return destinations
