"""Tests for Pick Verification Model and Statistical Error Rates (SO-101 Pattern, P6-A3, P6-R3)."""

from __future__ import annotations

import numpy as np
import pytest

from robofleet.config.models import PickVerificationConfig
from robofleet.contracts.catalogue import Sku
from robofleet.contracts.chaos import PickOutcome
from robofleet.contracts.common import Coordinate
from robofleet.contracts.layout import Station
from robofleet.contracts.order import Order, OrderLine, OrderStatus
from robofleet.fleet.station import PickingStationManager


def test_pick_verification_lifecycle_events() -> None:
    events: list[tuple[str, dict]] = []

    def mock_emitter(ev_type: str, payload: dict) -> None:
        events.append((ev_type, payload))

    station_def = Station(
        station_id="STATION-1",
        pos=Coordinate(x=5, y=5),
        queue_cells=[Coordinate(x=5, y=6)],
    )

    verif_cfg = PickVerificationConfig(
        enabled=True,
        base_error_rate=0.0,  # 0% error for deterministic happy path
        retry_limit=1,
        confidence_threshold=0.80,
        damaged_item_rate=0.0,
        wrong_item_rate=0.0,
        quantity_mismatch_rate=0.0,
        grasp_failure_rate=0.0,
    )

    rng = np.random.default_rng(42)
    mgr = PickingStationManager(
        station_defs=[station_def],
        base_pick_time_ticks=5,
        verification_cfg=verif_cfg,
        picker_rng=rng,
        event_emitter=mock_emitter,
    )

    sku = Sku(
        sku_id="SKU-001",
        name="Test Item",
        category="snacks",
        pack_size="1x",
        mrp_inr=50.0,
        popularity_rank=10,
        unit_weight_g=200,
        handling_difficulty=1.0,
    )
    line = OrderLine(sku_id="SKU-001", quantity=1)
    order = Order(order_id="ORD-001", lines=[line], created_tick=0, deadline_tick=100)

    # 1. Start pick -> pick.commanded
    mgr.start_pick("STATION-1", order, line, sku, current_tick=0)
    assert any(e[0] == "pick.commanded" for e in events)

    # 2. Advance ticks until completion
    orders_by_id = {order.order_id: order}
    completed: list[tuple[str, str, int]] = []
    for t in range(1, 10):
        comp = mgr.step_picks(t, orders_by_id)
        completed.extend(comp)

    assert len(completed) == 1
    assert completed[0] == ("ORD-001", "SKU-001", 1)
    assert any(e[0] == "pick.verified" for e in events)
    assert mgr.verified_picks_count == 1
    assert mgr.failed_picks_count == 0


def test_pick_verification_retry_and_isolation() -> None:
    events: list[tuple[str, dict]] = []

    def mock_emitter(ev_type: str, payload: dict) -> None:
        events.append((ev_type, payload))

    station_def = Station(
        station_id="STATION-1",
        pos=Coordinate(x=5, y=5),
        queue_cells=[Coordinate(x=5, y=6)],
    )

    # Force 100% damaged item rate
    verif_cfg = PickVerificationConfig(
        enabled=True,
        base_error_rate=0.5,
        retry_limit=1,
        confidence_threshold=0.85,
        damaged_item_rate=1.0,  # Always damaged
        wrong_item_rate=0.0,
        quantity_mismatch_rate=0.0,
        grasp_failure_rate=0.0,
    )

    rng = np.random.default_rng(123)
    mgr = PickingStationManager(
        station_defs=[station_def],
        base_pick_time_ticks=5,
        verification_cfg=verif_cfg,
        picker_rng=rng,
        event_emitter=mock_emitter,
    )

    sku = Sku(
        sku_id="SKU-DAMAGED",
        name="Fragile Eggs",
        category="dairy",
        pack_size="6x",
        mrp_inr=60.0,
        popularity_rank=5,
        unit_weight_g=300,
        fragile=True,
    )
    line = OrderLine(sku_id="SKU-DAMAGED", quantity=1)
    order = Order(order_id="ORD-002", lines=[line], created_tick=0, deadline_tick=100)

    mgr.start_pick("STATION-1", order, line, sku, current_tick=0)

    orders_by_id = {order.order_id: order}
    completed: list[tuple[str, str, int]] = []
    # Advance enough ticks for initial pick + retry duration (5 + 15 + margin)
    for t in range(1, 40):
        comp = mgr.step_picks(t, orders_by_id)
        completed.extend(comp)

    # Completed verified list MUST be empty (item was damaged and isolated!)
    assert len(completed) == 0

    # Events must reflect commanded -> mismatch -> retried -> mismatch -> failed
    event_types = [e[0] for e in events]
    assert "pick.commanded" in event_types
    assert "pick.mismatch" in event_types
    assert "pick.retried" in event_types
    assert "pick.failed" in event_types

    assert mgr.retried_picks_count == 1
    assert mgr.failed_picks_count == 1

    # Invariant: order line was NEVER consolidated as picked
    assert not mgr.is_order_fully_consolidated(order)


def test_pick_verification_statistical_error_rates_over_10000_picks() -> None:
    """Statistical verification check (P6-R3): error rates match config over 10,000 picks."""
    station_def = Station(
        station_id="STATION-1",
        pos=Coordinate(x=5, y=5),
        queue_cells=[Coordinate(x=5, y=6)],
    )

    verif_cfg = PickVerificationConfig(
        enabled=True,
        base_error_rate=0.04,
        retry_limit=0,  # 0 retries to measure single-shot error distribution directly
        confidence_threshold=0.85,
        damaged_item_rate=0.010,
        wrong_item_rate=0.010,
        quantity_mismatch_rate=0.010,
        grasp_failure_rate=0.010,
    )

    total_picks = 10_000
    rng = np.random.default_rng(999)
    mgr = PickingStationManager(
        station_defs=[station_def],
        base_pick_time_ticks=1,
        verification_cfg=verif_cfg,
        picker_rng=rng,
    )

    sku = Sku(
        sku_id="SKU-STAT",
        name="Stat Check",
        category="staples",
        pack_size="1kg",
        mrp_inr=100.0,
        popularity_rank=50,
        unit_weight_g=1000,
        handling_difficulty=1.0,
        fragile=False,
    )

    dummy_order = Order(order_id="ORD-STAT", lines=[], created_tick=0, deadline_tick=100000)
    orders_by_id = {"ORD-STAT": dummy_order}

    for i in range(total_picks):
        line = OrderLine(sku_id="SKU-STAT", quantity=1)
        mgr.start_pick("STATION-1", dummy_order, line, sku, current_tick=i)
        mgr.step_picks(i + 1, orders_by_id)

    # Total failures = damaged + wrong + quantity + grasp + low_confidence
    total_failures = mgr.failed_picks_count
    observed_failure_rate = total_failures / total_picks

    # Sum of component rates: 0.010 * 4 = 0.04 (plus normal distribution tail below 0.85)
    # Expected rate ~ 0.040 to 0.050
    assert 0.025 <= observed_failure_rate <= 0.065, f"Observed failure rate {observed_failure_rate} out of bounds"
    assert mgr.verified_picks_count == total_picks - total_failures
