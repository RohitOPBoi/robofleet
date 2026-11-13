"""Webhook Ingest Order Source Adapter (CA-2).
Accepts live JSON order payloads from external partners via REST API
with idempotency guarantees and rate-limiting.
"""

from __future__ import annotations

import threading
import time
from typing import Any

from robofleet.contracts.order import Order, OrderLine, OrderStatus
from robofleet.interfaces.protocols import OrderSource


class WebhookOrderSource(OrderSource):
    """Ingests orders from REST endpoints and queues them for the simulation."""

    def __init__(self, max_rate_per_sec: int = 50, queue_limit: int = 2000) -> None:
        self.max_rate_per_sec = max_rate_per_sec
        self.queue_limit = queue_limit
        self._lock = threading.Lock()
        self._queue: list[Order] = []
        self._seen_order_ids: set[str] = set()
        self._timestamps: list[float] = []

    def ingest_order(self, payload: dict[str, Any], current_tick: int = 0) -> Order:
        """Validate, check idempotency, apply rate limit, and queue an incoming order."""
        with self._lock:
            # 1. Rate limiting check
            now = time.monotonic()
            self._timestamps = [t for t in self._timestamps if now - t < 1.0]
            if len(self._timestamps) >= self.max_rate_per_sec:
                raise ValueError(
                    f"Rate limit exceeded: max {self.max_rate_per_sec} orders per second"
                )

            # 2. Extract and check order_id idempotency
            order_id = payload.get("order_id")
            if not order_id:
                raise ValueError("Missing 'order_id' in order payload")
            if order_id in self._seen_order_ids:
                raise ValueError(f"Duplicate order_id: {order_id} has already been ingested")

            # 3. Validate lines
            lines_data = payload.get("lines", [])
            if not lines_data:
                raise ValueError("Order must contain at least one line")

            lines: list[OrderLine] = []
            for l_idx, l in enumerate(lines_data):
                sku_id = l.get("sku_id")
                qty = l.get("quantity", 1)
                if not sku_id:
                    raise ValueError(f"Line {l_idx}: missing 'sku_id'")
                if qty < 1:
                    raise ValueError(f"Line {l_idx}: quantity must be >= 1")
                lines.append(OrderLine(sku_id=sku_id, quantity=qty))

            priority = int(payload.get("priority") or 1)
            raw_deadline = payload.get("deadline_tick")
            deadline_tick = int(raw_deadline) if raw_deadline is not None else (current_tick + 600)
            sla_tier = str(payload.get("sla_tier") or "standard")

            order = Order(
                order_id=order_id,
                lines=lines,
                status=OrderStatus.QUEUED,
                priority=priority,
                created_tick=current_tick,
                deadline_tick=deadline_tick,
                sla_tier=sla_tier,
            )

            # Check queue capacity
            if len(self._queue) >= self.queue_limit:
                raise ValueError(f"Order queue capacity exceeded ({self.queue_limit})")

            self._seen_order_ids.add(order_id)
            self._timestamps.append(now)
            self._queue.append(order)

            return order

    def poll_orders(self, current_tick: int) -> list[Order]:
        """Poll and drain all queued orders into the simulation engine."""
        with self._lock:
            if not self._queue:
                return []
            orders = list(self._queue)
            self._queue.clear()
            return orders
