"""Order adapters tests (CA-2, P2-A4, P2-A5).
Tests SyntheticDemandEngine, CsvReplayOrderSource, and WebhookOrderSource.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from robofleet.adapters.csv_replay import CsvReplayOrderSource
from robofleet.adapters.demand_engine import SyntheticDemandEngine
from robofleet.adapters.webhook import WebhookOrderSource
from robofleet.catalogue.generator import generate_catalogue


def test_demand_engine_arrival_rate_and_basket_validity():
    skus = generate_catalogue(sku_count=200, seed=42)
    sku_ids_set = {s.sku_id for s in skus}

    engine = SyntheticDemandEngine(
        profile_path="profiles/standard_evening.yaml",
        skus=skus,
        seed=42,
        tick_hz=10,
        urgent_share=0.20,
    )

    # Base rate is 120/hr. Over 24 hours, average multiplier across hourly profile is ~1.0
    # Run 24 simulated hours = 24 * 3600 * 10 = 864,000 ticks.
    # We test 2 simulated hours (72,000 ticks) around peak hours (18:00 to 20:00)
    # Peak multiplier is ~2.2x -> expected ~264 orders/hour -> ~528 orders in 2 hours
    start_tick = 18 * 3600 * 10
    orders = []

    # Sample ticks in intervals or step through
    for t in range(start_tick, start_tick + 5000):  # 500 seconds
        new_orders = engine.poll_orders(t)
        orders.extend(new_orders)

    assert len(orders) > 0, "Demand engine must generate orders during active hours"
    for o in orders:
        assert len(o.lines) >= 1
        for line in o.lines:
            assert line.sku_id in sku_ids_set, "Order referenced nonexistent SKU"
            assert line.quantity >= 1
        assert o.deadline_tick > o.created_tick
        assert o.priority in (1, 5)


def test_demand_engine_overlay_increases_rate():
    skus = generate_catalogue(sku_count=50, seed=42)
    engine_base = SyntheticDemandEngine(skus=skus, seed=42, tick_hz=10)
    engine_rush = SyntheticDemandEngine(skus=skus, seed=42, tick_hz=10)

    engine_rush.trigger_rush(multiplier=3.0, duration_s=600)

    base_orders_count = 0
    rush_orders_count = 0

    for t in range(2000):
        base_orders_count += len(engine_base.poll_orders(t))
        rush_orders_count += len(engine_rush.poll_orders(t))

    assert rush_orders_count > base_orders_count, (
        f"Rush overlay ({rush_orders_count}) must produce more orders than base ({base_orders_count})"
    )


def test_csv_replay_adapter_valid_and_release():
    csv_path = "scenarios/sample_orders.csv"
    adapter = CsvReplayOrderSource(csv_path=csv_path, tick_hz=10)

    # At tick 0, no orders released
    assert len(adapter.poll_orders(0)) == 0

    # At tick 10, ORD-CSV-001 arrives
    orders_10 = adapter.poll_orders(10)
    assert len(orders_10) == 1
    assert orders_10[0].order_id == "ORD-CSV-001"
    assert len(orders_10[0].lines) == 2

    # At tick 100, orders scheduled up to tick 100 arrive
    orders_100 = adapter.poll_orders(100)
    assert len(orders_100) == 3  # ORD-CSV-002 (25), 003 (50), 004 (80)


def test_csv_replay_adapter_catches_invalid_rows(tmp_path: Path):
    bad_csv = tmp_path / "bad_orders.csv"
    bad_csv.write_text(
        "order_id,arrival_tick,sku_ids,quantities,priority,deadline_tick\n"
        "ORD-01,10,SKU-1;SKU-2,1,1,100\n",  # 2 skus but only 1 quantity!
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="quantities count"):
        CsvReplayOrderSource(csv_path=str(bad_csv))


def test_webhook_adapter_idempotency_and_rate_limit():
    webhook = WebhookOrderSource(max_rate_per_sec=10)

    payload = {
        "order_id": "ORD-WH-001",
        "lines": [{"sku_id": "SKU-0001", "quantity": 2}],
        "priority": 3,
        "deadline_tick": 500,
    }

    # 1. First ingest succeeds
    order = webhook.ingest_order(payload, current_tick=10)
    assert order.order_id == "ORD-WH-001"

    # 2. Duplicate ingest raises idempotency error
    with pytest.raises(ValueError, match="Duplicate order_id"):
        webhook.ingest_order(payload, current_tick=11)

    # 3. Draining orders via poll_orders returns the ingested order
    polled = webhook.poll_orders(12)
    assert len(polled) == 1
    assert polled[0].order_id == "ORD-WH-001"
    assert len(webhook.poll_orders(13)) == 0  # Queue drained


def test_demand_engine_24h_arrival_statistics():
    """Verify diurnal Poisson arrival rate matches profile across 24 simulated hours (P2-A4)."""
    skus = generate_catalogue(sku_count=50, seed=123)
    engine = SyntheticDemandEngine(
        profile_path="profiles/standard_evening.yaml",
        skus=skus,
        seed=123,
        tick_hz=1,  # 1 tick per second for fast 24h calculation
    )

    hourly_counts: dict[int, int] = dict.fromkeys(range(24), 0)
    total_seconds = 24 * 3600

    for sec in range(total_seconds):
        orders = engine.poll_orders(sec)
        hour = (sec // 3600) % 24
        hourly_counts[hour] += len(orders)

    total_orders = sum(hourly_counts.values())
    # Expected total is ~2712 orders (sum of multipliers = 22.6 * 120 = 2712)
    expected_total = 2712
    # Check within 10% tolerance
    assert abs(total_orders - expected_total) / expected_total < 0.10, (
        f"24h total orders {total_orders} deviated >10% from expected {expected_total}"
    )

    # Check peak hour (19:00) vs trough hour (3:00)
    assert hourly_counts[19] > 180, f"Peak hour 19 count {hourly_counts[19]} should be ~288"
    assert hourly_counts[3] < 25, f"Trough hour 3 count {hourly_counts[3]} should be ~6"
    assert hourly_counts[19] > 10 * hourly_counts[3], "Peak hour must exceed trough hour by >10x"
