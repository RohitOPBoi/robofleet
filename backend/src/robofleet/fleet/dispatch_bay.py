"""Dispatch Bay and Supervisor Desk Model (Phase 3).
Simulates dispatch bay holding packed order totes and a simulated supervisor
handling final courier/rider handover with seeded arrival and service distributions.
"""

from __future__ import annotations

import numpy as np

from robofleet.contracts.common import Coordinate
from robofleet.contracts.order import Order, OrderStatus


class ActiveHandover:
    def __init__(self, order_id: str, duration_ticks: int, start_tick: int) -> None:
        self.order_id = order_id
        self.duration_ticks = max(1, duration_ticks)
        self.start_tick = start_tick
        self.elapsed_ticks = 0

    @property
    def is_finished(self) -> bool:
        return self.elapsed_ticks >= self.duration_ticks


class DispatchBayManager:
    """Manages dispatch bay orders, rider arrivals, and supervisor handoffs."""

    def __init__(
        self,
        dispatch_cells: list[Coordinate],
        supervisor_cells: list[Coordinate],
        base_handoff_ticks: int = 40,
        rider_arrival_rate_per_hr: float = 120.0,
        tick_hz: int = 10,
        seed: int = 42,
    ) -> None:
        self.dispatch_cells = dispatch_cells
        self.supervisor_cells = supervisor_cells
        self.base_handoff_ticks = base_handoff_ticks
        self.rider_arrival_rate_per_hr = rider_arrival_rate_per_hr
        self.tick_hz = tick_hz

        self.rng = np.random.Generator(np.random.PCG64(seed + 9001))

        # Dynamic state
        self.ready_orders_queue: list[str] = []
        self.active_handover: ActiveHandover | None = None
        self.available_riders_count: int = 2  # Initial riders standing by

        # Tracking supervisor utilization
        self.supervisor_busy_ticks: int = 0
        self.total_ticks: int = 0

    @property
    def desk_cell(self) -> Coordinate:
        if self.supervisor_cells:
            return self.supervisor_cells[0]
        if self.dispatch_cells:
            return self.dispatch_cells[0]
        return Coordinate(x=0, y=0)

    def enqueue_ready_order(self, order: Order, current_tick: int) -> None:
        if order.status == OrderStatus.PACKED:
            order.status = OrderStatus.READY_FOR_DISPATCH
            order.ready_tick = current_tick
        if order.order_id not in self.ready_orders_queue:
            self.ready_orders_queue.append(order.order_id)

    def step(self, current_tick: int, orders_by_id: dict[str, Order]) -> list[str]:
        """Advances dispatch operations. Returns list of handed-over order IDs."""
        self.total_ticks += 1
        handed_over: list[str] = []

        # 1. Simulate rider arrivals (Poisson process per tick)
        # Lambda per tick = rate_per_hr / (3600 * tick_hz)
        lambda_per_tick = self.rider_arrival_rate_per_hr / (3600.0 * self.tick_hz)
        arrivals = self.rng.poisson(lam=lambda_per_tick)
        self.available_riders_count += arrivals

        # 2. Advance active handover
        if self.active_handover is not None:
            self.supervisor_busy_ticks += 1
            self.active_handover.elapsed_ticks += 1

            if self.active_handover.is_finished:
                finished_order_id = self.active_handover.order_id
                order = orders_by_id.get(finished_order_id)
                if order:
                    order.status = OrderStatus.HANDED_OVER
                    order.handover_tick = current_tick
                    handed_over.append(finished_order_id)
                self.active_handover = None

        # 3. If supervisor is idle and rider is present, start next handover
        if self.active_handover is None and self.ready_orders_queue and self.available_riders_count > 0:
            next_order_id = self.ready_orders_queue.pop(0)
            self.available_riders_count -= 1

            # Seeded handoff duration jitter (+/- 20%)
            jitter = float(self.rng.uniform(0.8, 1.2))
            handoff_duration = max(10, int(round(self.base_handoff_ticks * jitter)))

            self.active_handover = ActiveHandover(
                order_id=next_order_id,
                duration_ticks=handoff_duration,
                start_tick=current_tick,
            )
            self.supervisor_busy_ticks += 1

        return handed_over

    @property
    def supervisor_utilization(self) -> float:
        if self.total_ticks <= 0:
            return 0.0
        return min(1.0, self.supervisor_busy_ticks / self.total_ticks)
