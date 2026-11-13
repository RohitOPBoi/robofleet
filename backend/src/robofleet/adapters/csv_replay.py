"""CSV Replay Order Source Adapter (CA-2).
Replays real or exported historical dark store orders from a CSV file.
"""

from __future__ import annotations

import csv
from pathlib import Path

from robofleet.contracts.order import Order, OrderLine, OrderStatus
from robofleet.interfaces.protocols import OrderSource


class CsvReplayOrderSource(OrderSource):
    """Replays orders from a CSV file with row-level validation."""

    def __init__(
        self,
        csv_path: str = "scenarios/sample_orders.csv",
        speed_factor: float = 1.0,
        tick_hz: int = 10,
    ) -> None:
        self.csv_path = Path(csv_path)
        self.speed_factor = speed_factor
        self.tick_hz = tick_hz
        self.buffered_orders: list[tuple[int, Order]] = []
        self._load_and_validate_csv()

    def _load_and_validate_csv(self) -> None:
        if not self.csv_path.exists():
            raise FileNotFoundError(f"Orders CSV file not found: {self.csv_path}")

        with self.csv_path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            required_cols = {
                "order_id",
                "arrival_tick",
                "sku_ids",
                "quantities",
                "priority",
                "deadline_tick",
            }
            if not reader.fieldnames or not required_cols.issubset(set(reader.fieldnames)):
                missing = required_cols - set(reader.fieldnames or [])
                raise ValueError(f"CSV header missing required columns: {missing}")

            for row_idx, row in enumerate(reader, start=2):
                try:
                    order_id = row["order_id"].strip()
                    arrival_tick = int(float(row["arrival_tick"].strip()) / self.speed_factor)
                    sku_ids = [s.strip() for s in row["sku_ids"].split(";") if s.strip()]
                    quantities = [int(q.strip()) for q in row["quantities"].split(";") if q.strip()]

                    if len(sku_ids) != len(quantities):
                        raise ValueError(
                            f"Row {row_idx}: sku_ids count ({len(sku_ids)}) != quantities count ({len(quantities)})"
                        )

                    lines = [
                        OrderLine(sku_id=sid, quantity=qty)
                        for sid, qty in zip(sku_ids, quantities, strict=False)
                    ]
                    priority = int(row["priority"].strip())
                    deadline_tick = int(float(row["deadline_tick"].strip()) / self.speed_factor)
                    sla_tier = row.get("sla_tier", "standard").strip()

                    order = Order(
                        order_id=order_id,
                        lines=lines,
                        status=OrderStatus.QUEUED,
                        priority=priority,
                        created_tick=arrival_tick,
                        deadline_tick=deadline_tick,
                        sla_tier=sla_tier,
                    )
                    self.buffered_orders.append((arrival_tick, order))
                except Exception as e:
                    raise ValueError(f"CSV validation error on row {row_idx}: {e}") from e

        # Sort buffered orders by arrival tick
        self.buffered_orders.sort(key=lambda item: item[0])

    def poll_orders(self, current_tick: int) -> list[Order]:
        """Release orders whose arrival_tick <= current_tick."""
        ready_orders: list[Order] = []
        while self.buffered_orders and self.buffered_orders[0][0] <= current_tick:
            _, order = self.buffered_orders.pop(0)
            ready_orders.append(order)
        return ready_orders
