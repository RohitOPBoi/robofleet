"""Synthetic Demand Engine Adapter (CA-2).
Generates realistic non-homogeneous Poisson order arrivals based on diurnal demand curves,
popularity-biased SKU sampling, and co-purchase affinity matrices.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import yaml

from robofleet.contracts.catalogue import Sku
from robofleet.contracts.order import Order, OrderLine, OrderStatus
from robofleet.interfaces.protocols import OrderSource


class SyntheticDemandEngine(OrderSource):
    """Generates synthetic order traffic following configured diurnal patterns."""

    def __init__(
        self,
        profile_path: str = "profiles/standard_evening.yaml",
        skus: list[Sku] | None = None,
        seed: int = 42,
        tick_hz: int = 10,
        urgent_share: float = 0.20,
        rush_multiplier: float = 1.0,
    ) -> None:
        self.profile_path = profile_path
        self.skus = skus or []
        self.seed = seed
        self.tick_hz = tick_hz
        self.urgent_share = urgent_share
        self.rush_multiplier = rush_multiplier
        self.active_overlay: str | None = None
        self.overlay_multiplier: float = 1.0
        self.overlay_remaining_ticks: int = 0
        self.order_counter: int = 0
        self._queued_immediate_orders: list[Order] = []

        # Dedicated RNG stream
        self.rng = np.random.default_rng(seed + 101)

        # Load profile
        p_path = Path(profile_path)
        if not p_path.exists():
            p_path = Path("profiles/standard_evening.yaml")

        self.profile_data: dict[str, Any] = {}
        if p_path.exists():
            self.profile_data = yaml.safe_load(p_path.read_text(encoding="utf-8")) or {}

        self.base_rate_per_hour: float = float(
            self.profile_data.get("base_arrival_rate_per_hour", 120.0)
        )
        self.hourly_multipliers: dict[int, float] = {
            int(k): float(v) for k, v in self.profile_data.get("hourly_multipliers", {}).items()
        }
        self.overlays: dict[str, dict[str, Any]] = self.profile_data.get("overlays", {})

        # Build SKU selection probability distribution based on popularity rank
        if self.skus:
            # P(sku) ~ 1 / rank^0.8
            ranks = np.array([max(1, s.popularity_rank) for s in self.skus], dtype=float)
            weights = 1.0 / (ranks**0.8)
            self.sku_probabilities = weights / weights.sum()
        else:
            self.sku_probabilities = np.array([], dtype=float)

    def apply_overlay(
        self, name: str, multiplier: float | None = None, duration_ticks: int | None = None
    ) -> None:
        """Apply a demand overlay (e.g. rain, match_night, rush)."""
        self.active_overlay = name
        overlay_info = self.overlays.get(name, {})
        self.overlay_multiplier = multiplier or float(overlay_info.get("multiplier", 1.5))
        hours = float(overlay_info.get("duration_hours", 1.0))
        self.overlay_remaining_ticks = duration_ticks or int(hours * 3600 * self.tick_hz)

    def clear_overlay(self) -> None:
        """Clear any active overlay."""
        self.active_overlay = None
        self.overlay_multiplier = 1.0
        self.overlay_remaining_ticks = 0

    def _create_synthetic_order(self, current_tick: int = 0, priority: int = 5) -> Order:
        self.order_counter += 1
        order_id = f"ORD-{self.order_counter:06d}"
        basket_size = int(np.clip(self.rng.poisson(lam=3.5), 1, 8))
        chosen_sku_indices = self.rng.choice(
            len(self.skus),
            size=basket_size,
            replace=(basket_size > len(self.skus)),
            p=self.sku_probabilities,
        )
        lines: list[OrderLine] = []
        for idx in chosen_sku_indices:
            sku = self.skus[idx]
            qty = int(self.rng.integers(1, 3))
            lines.append(OrderLine(sku_id=sku.sku_id, quantity=qty))
        sla_tier = "express" if priority >= 5 else "standard"
        sla_ticks = int((10 if priority >= 5 else 20) * 60 * self.tick_hz)
        deadline_tick = current_tick + sla_ticks
        return Order(
            order_id=order_id,
            lines=lines,
            status=OrderStatus.QUEUED,
            priority=priority,
            created_tick=current_tick,
            deadline_tick=deadline_tick,
            at_risk=False,
            sla_tier=sla_tier,
        )

    def inject_rush_orders(self, count: int = 6, current_tick: int = 0) -> list[Order]:
        """Immediately generates a burst of express orders into the demand queue."""
        if not self.skus:
            return []
        burst: list[Order] = []
        for _ in range(count):
            burst.append(self._create_synthetic_order(current_tick=current_tick, priority=5))
        self._queued_immediate_orders.extend(burst)
        return burst

    def trigger_rush(self, multiplier: float = 2.5, duration_s: int = 300, burst_count: int = 6) -> None:
        """Trigger an immediate demand rush with both overlay multiplier and immediate order burst."""
        self.apply_overlay(
            name="rush",
            multiplier=multiplier,
            duration_ticks=int(duration_s * self.tick_hz),
        )
        if burst_count > 0:
            self.inject_rush_orders(count=burst_count)

    def poll_orders(self, current_tick: int) -> list[Order]:
        """Poll for new orders arriving at the current simulation tick."""
        if not self.skus:
            return []

        new_orders: list[Order] = []
        # Immediately drain any queued burst/rush orders
        if self._queued_immediate_orders:
            new_orders.extend(self._queued_immediate_orders)
            self._queued_immediate_orders.clear()

        # Countdown active overlay
        if self.overlay_remaining_ticks > 0:
            self.overlay_remaining_ticks -= 1
            if self.overlay_remaining_ticks == 0:
                self.active_overlay = None
                self.overlay_multiplier = 1.0

        # Calculate current time of day in hours (24h loop)
        seconds_elapsed = current_tick / self.tick_hz
        sim_hour = int((seconds_elapsed // 3600) % 24)

        hour_mult = self.hourly_multipliers.get(sim_hour, 1.0)
        effective_mult = hour_mult * self.overlay_multiplier * self.rush_multiplier

        # Lambda: expected arrivals per tick
        arrivals_per_second = (self.base_rate_per_hour * effective_mult) / 3600.0
        lambda_tick = arrivals_per_second / self.tick_hz

        # Sample Poisson arrivals
        arrival_count = int(self.rng.poisson(lam=lambda_tick))

        for _ in range(arrival_count):
            self.order_counter += 1
            order_id = f"ORD-{self.order_counter:06d}"

            # Sample basket size (1 to 8 items, mean ~3.5)
            basket_size = int(np.clip(self.rng.poisson(lam=3.5), 1, 8))

            # Sample SKUs
            chosen_sku_indices = self.rng.choice(
                len(self.skus),
                size=basket_size,
                replace=(basket_size > len(self.skus)),
                p=self.sku_probabilities,
            )

            lines: list[OrderLine] = []
            for idx in chosen_sku_indices:
                sku = self.skus[idx]
                qty = int(self.rng.integers(1, 3))  # 1 or 2 units
                lines.append(OrderLine(sku_id=sku.sku_id, quantity=qty))

            # SLA tier and priority
            is_urgent = bool(self.rng.uniform(0.0, 1.0) < self.urgent_share)
            if is_urgent:
                sla_tier = "express"
                priority = 5
                # 10 minute SLA
                sla_ticks = int(10 * 60 * self.tick_hz)
            else:
                sla_tier = "standard"
                priority = 1
                # 20 minute SLA
                sla_ticks = int(20 * 60 * self.tick_hz)

            deadline_tick = current_tick + sla_ticks

            order = Order(
                order_id=order_id,
                lines=lines,
                status=OrderStatus.QUEUED,
                priority=priority,
                created_tick=current_tick,
                deadline_tick=deadline_tick,
                at_risk=False,
                sla_tier=sla_tier,
            )
            new_orders.append(order)

        return new_orders
