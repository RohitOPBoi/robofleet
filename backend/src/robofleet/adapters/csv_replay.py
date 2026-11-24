"""CSV Replay Order Source Adapter (CA-2).
Replays real or exported historical dark store orders from a CSV file.
Supports both native tick-based order CSVs and standard customer timestamped order line exports.
"""

from __future__ import annotations

import csv
import datetime
from pathlib import Path
from typing import Any

from robofleet.contracts.order import Order, OrderLine, OrderStatus
from robofleet.interfaces.protocols import OrderSource


class CsvReplayOrderSource(OrderSource):
    """Replays orders from a CSV file with row-level validation and schema flexibility."""

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

        with self.csv_path.open("r", encoding="utf-8-sig", errors="replace") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                raise ValueError(f"Empty CSV file: {self.csv_path}")

            field_map = {col.strip().lower(): col for col in reader.fieldnames}

            # Check if this is a tick-based grouped CSV (format A)
            if "arrival_tick" in field_map and ("sku_ids" in field_map or "skus" in field_map):
                self._load_tick_based_csv(reader, field_map)
            # Or standard line-item export CSV (format B, e.g. customer_orders_sample.csv)
            elif "order_id" in field_map and ("sku_id" in field_map or "sku" in field_map):
                self._load_line_item_csv(reader, field_map)
            else:
                raise ValueError(
                    f"Unrecognized CSV format in {self.csv_path}. Headers found: {list(reader.fieldnames)}"
                )

        # Sort buffered orders by arrival tick
        self.buffered_orders.sort(key=lambda item: item[0])

    def _load_tick_based_csv(self, reader: csv.DictReader[str], field_map: dict[str, str]) -> None:
        for row_idx, row in enumerate(reader, start=2):
            try:
                order_id = row[field_map["order_id"]].strip()
                arrival_col = field_map["arrival_tick"]
                arrival_tick = int(float(row[arrival_col].strip()) / self.speed_factor)
                sku_col = field_map.get("sku_ids") or field_map["skus"]
                qty_col = field_map.get("quantities") or field_map.get("quantity") or field_map["quantities"]

                sku_ids = [s.strip() for s in row[sku_col].split(";") if s.strip()]
                quantities = [int(q.strip()) for q in row[qty_col].split(";") if q.strip()]

                if len(sku_ids) != len(quantities):
                    raise ValueError(
                        f"Row {row_idx}: sku_ids count ({len(sku_ids)}) != quantities count ({len(quantities)})"
                    )

                lines = [
                    OrderLine(sku_id=sid, quantity=qty)
                    for sid, qty in zip(sku_ids, quantities, strict=False)
                ]
                priority_col = field_map.get("priority")
                priority = int(row[priority_col].strip()) if priority_col and row.get(priority_col) else 1

                dl_col = field_map.get("deadline_tick")
                deadline_tick = (
                    int(float(row[dl_col].strip()) / self.speed_factor)
                    if dl_col and row.get(dl_col)
                    else (arrival_tick + 600)
                )

                sla_col = field_map.get("sla_tier")
                sla_tier = row[sla_col].strip() if sla_col and row.get(sla_col) else "standard"

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

    def _load_line_item_csv(self, reader: csv.DictReader[str], field_map: dict[str, str]) -> None:
        """Groups individual order lines from a transactional customer export into orders."""
        order_col = field_map["order_id"]
        sku_col = field_map.get("sku_id") or field_map["sku"]
        qty_col = field_map.get("quantity") or field_map.get("qty")
        time_col = field_map.get("timestamp") or field_map.get("created_at") or field_map.get("time")
        prio_col = field_map.get("priority")
        sla_col = field_map.get("sla_tier")

        grouped_orders: dict[str, dict[str, Any]] = {}
        first_dt: datetime.datetime | None = None

        for row_idx, row in enumerate(reader, start=2):
            order_id = row[order_col].strip()
            if not order_id:
                continue

            sku_id = row[sku_col].strip()
            qty_raw = row.get(qty_col, "1") if qty_col else "1"
            qty = max(1, int(float(qty_raw))) if qty_raw else 1

            if order_id not in grouped_orders:
                time_str = (row.get(time_col) or "").strip() if time_col else ""
                parsed_dt: datetime.datetime | None = None
                if time_str:
                    try:
                        parsed_dt = datetime.datetime.fromisoformat(time_str.replace("Z", "+00:00"))
                    except Exception:
                        pass

                if parsed_dt and first_dt is None:
                    first_dt = parsed_dt

                priority = int(row.get(prio_col, 1)) if prio_col and row.get(prio_col) else 1
                sla_tier = row.get(sla_col, "standard").strip() if sla_col and row.get(sla_col) else "standard"

                grouped_orders[order_id] = {
                    "lines": [],
                    "parsed_dt": parsed_dt,
                    "priority": priority,
                    "sla_tier": sla_tier,
                    "order_index": len(grouped_orders),
                }

            grouped_orders[order_id]["lines"].append(OrderLine(sku_id=sku_id, quantity=qty))

        for order_id, data in grouped_orders.items():
            if data["parsed_dt"] and first_dt:
                delta_sec = max(0.0, (data["parsed_dt"] - first_dt).total_seconds())
                arrival_tick = int((delta_sec / max(0.1, self.speed_factor)) * self.tick_hz)
            else:
                # Spaced out by 10 seconds if no timestamps
                arrival_tick = int((data["order_index"] * 10.0 / max(0.1, self.speed_factor)) * self.tick_hz)

            deadline_offset = 600 if data["sla_tier"] == "express" else 1200
            order = Order(
                order_id=order_id,
                lines=data["lines"],
                status=OrderStatus.QUEUED,
                priority=data["priority"],
                created_tick=arrival_tick,
                deadline_tick=arrival_tick + deadline_offset,
                sla_tier=data["sla_tier"],
            )
            self.buffered_orders.append((arrival_tick, order))

    def poll_orders(self, current_tick: int) -> list[Order]:
        """Release orders whose arrival_tick <= current_tick."""
        ready_orders: list[Order] = []
        while self.buffered_orders and self.buffered_orders[0][0] <= current_tick:
            _, order = self.buffered_orders.pop(0)
            ready_orders.append(order)
        return ready_orders
