"""Station and Picking Operations Model (Phase 3).
Simulates pick stations with bounded robot queues, pick workers, service-time calculation,
and strict order tote consolidation without mixing.
"""

from __future__ import annotations

from typing import Any
import numpy as np

from robofleet.contracts.catalogue import Sku
from robofleet.contracts.common import Coordinate
from robofleet.contracts.layout import Station as StationDef
from robofleet.contracts.order import Order, OrderLine, OrderStatus


class StationQueueSlot:
    def __init__(self, cell: Coordinate, index: int) -> None:
        self.cell = cell
        self.index = index
        self.occupant_robot_id: str | None = None


class ActivePickOperation:
    def __init__(
        self,
        order_id: str,
        sku_id: str,
        quantity: int,
        duration_ticks: int,
        start_tick: int,
    ) -> None:
        self.order_id = order_id
        self.sku_id = sku_id
        self.quantity = quantity
        self.duration_ticks = max(1, duration_ticks)
        self.start_tick = start_tick
        self.elapsed_ticks = 0

    @property
    def is_finished(self) -> bool:
        return self.elapsed_ticks >= self.duration_ticks


class PickingStationManager:
    """Manages physical picking stations, queues, and consolidation buffers."""

    def __init__(
        self,
        station_defs: list[StationDef],
        base_pick_time_ticks: int = 30,
        consolidation_time_ticks: int = 20,
        max_queue_capacity: int = 6,
    ) -> None:
        self.station_defs = {s.station_id: s for s in station_defs}
        self.base_pick_time_ticks = base_pick_time_ticks
        self.consolidation_time_ticks = consolidation_time_ticks
        self.max_queue_capacity = max_queue_capacity

        # Per-station dynamic tracking
        self.dock_occupant: dict[str, str | None] = {s.station_id: None for s in station_defs}
        self.robot_queues: dict[str, list[str]] = {s.station_id: [] for s in station_defs}
        self.active_picks: dict[str, list[ActivePickOperation]] = {s.station_id: [] for s in station_defs}

        # Order consolidation buffer: order_id -> dict of sku_id -> count picked
        self.order_consolidation: dict[str, dict[str, int]] = {}
        self.order_consolidation_started: dict[str, int] = {}
        self.order_consolidation_progress: dict[str, int] = {}

        # Utilization tracking: station_id -> busy ticks
        self.busy_ticks: dict[str, int] = {s.station_id: 0 for s in station_defs}
        self.total_ticks: int = 0

    def get_dock_cell(self, station_id: str) -> Coordinate | None:
        st = self.station_defs.get(station_id)
        return st.pos if st else None

    def get_queue_cells(self, station_id: str) -> list[Coordinate]:
        st = self.station_defs.get(station_id)
        if not st or not st.queue_cells:
            # Fallback: compute 2-3 cells east/west of dock
            if not st:
                return []
            return [Coordinate(x=st.pos.x + i, y=st.pos.y) for i in range(1, self.max_queue_capacity + 1)]
        return st.queue_cells[: self.max_queue_capacity]

    def can_enqueue_robot(self, station_id: str) -> bool:
        queue = self.robot_queues.get(station_id, [])
        return len(queue) < self.max_queue_capacity

    def enqueue_robot(self, station_id: str, robot_id: str) -> bool:
        if station_id not in self.robot_queues:
            return False
        if robot_id in self.robot_queues[station_id]:
            return True
        if len(self.robot_queues[station_id]) >= self.max_queue_capacity:
            return False
        self.robot_queues[station_id].append(robot_id)
        return True

    def remove_robot(self, station_id: str, robot_id: str) -> None:
        if station_id in self.robot_queues and robot_id in self.robot_queues[station_id]:
            self.robot_queues[station_id].remove(robot_id)
        if self.dock_occupant.get(station_id) == robot_id:
            self.dock_occupant[station_id] = None

    def get_target_queue_cell(self, station_id: str, robot_id: str) -> Coordinate:
        """Returns the specific cell in the station approach queue for this robot."""
        dock = self.get_dock_cell(station_id)
        if not dock:
            return Coordinate(x=0, y=0)

        queue = self.robot_queues.get(station_id, [])
        if robot_id not in queue:
            # Not yet queued; head towards queue entrance (tail cell)
            q_cells = self.get_queue_cells(station_id)
            return q_cells[-1] if q_cells else dock

        index = queue.index(robot_id)
        if index == 0:
            # Head of queue goes to dock cell
            return dock

        q_cells = self.get_queue_cells(station_id)
        if index - 1 < len(q_cells):
            return q_cells[index - 1]
        return q_cells[-1] if q_cells else dock

    def start_pick(
        self,
        station_id: str,
        order: Order,
        line: OrderLine,
        sku: Sku | None,
        current_tick: int,
    ) -> ActivePickOperation:
        """Schedules pick operation at station with item difficulty multiplier."""
        difficulty = sku.handling_difficulty if sku else 1.0
        # Service time = base * difficulty * quantity
        duration = int(round(self.base_pick_time_ticks * difficulty * max(1, line.quantity)))

        op = ActivePickOperation(
            order_id=order.order_id,
            sku_id=line.sku_id,
            quantity=line.quantity,
            duration_ticks=duration,
            start_tick=current_tick,
        )
        self.active_picks[station_id].append(op)
        return op

    def step_picks(
        self,
        current_tick: int,
        orders_by_id: dict[str, Order],
    ) -> list[tuple[str, str, int]]:
        """Advances active picks. Returns list of completed (order_id, sku_id, quantity)."""
        self.total_ticks += 1
        completed: list[tuple[str, str, int]] = []

        for st_id, picks in self.active_picks.items():
            if picks:
                self.busy_ticks[st_id] += 1
                active_op = picks[0]
                active_op.elapsed_ticks += 1

                if active_op.is_finished:
                    completed.append((active_op.order_id, active_op.sku_id, active_op.quantity))
                    picks.pop(0)

                    # Update consolidation buffer
                    ord_id = active_op.order_id
                    if ord_id not in self.order_consolidation:
                        self.order_consolidation[ord_id] = {}
                    self.order_consolidation[ord_id][active_op.sku_id] = (
                        self.order_consolidation[ord_id].get(active_op.sku_id, 0) + active_op.quantity
                    )

        # Step consolidation progress for orders that have all items picked
        for ord_id, order in list(orders_by_id.items()):
            if order.status == OrderStatus.CONSOLIDATING:
                if ord_id not in self.order_consolidation_started:
                    self.order_consolidation_started[ord_id] = current_tick
                    self.order_consolidation_progress[ord_id] = 0

                self.order_consolidation_progress[ord_id] += 1
                if self.order_consolidation_progress[ord_id] >= self.consolidation_time_ticks:
                    order.status = OrderStatus.PACKED

        return completed

    def is_order_fully_consolidated(self, order: Order) -> bool:
        """Strict non-mixing invariant: order only complete when all required lines are present."""
        picked_dict = self.order_consolidation.get(order.order_id, {})
        for line in order.lines:
            if picked_dict.get(line.sku_id, 0) < line.quantity:
                return False
        return True

    def get_station_utilization(self, station_id: str) -> float:
        if self.total_ticks <= 0:
            return 0.0
        return min(1.0, self.busy_ticks.get(station_id, 0) / self.total_ticks)
