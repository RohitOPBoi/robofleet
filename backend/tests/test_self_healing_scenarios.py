"""Tests for Self-Healing Recovery, Chaos Scenarios, Replenishment and Re-slotting (P6-A1, P6-A2, P6-A8)."""

from __future__ import annotations

from pathlib import Path
import pytest

from robofleet.cli.chaos import run_single_chaos_seed
from robofleet.config.loader import load_config
from robofleet.contracts.order import Order, OrderLine, OrderStatus
from robofleet.layout.generator import generate_parametric_layout
from robofleet.replenishment.recommender import ReplenishmentManager, ReslottingRecommender
from robofleet.sim.engine import SimEngine


@pytest.mark.parametrize(
    "scenario_name",
    [
        "robot_failure_cascade",
        "aisle_blockage_peak",
        "stock_out_urgent_orders",
        "station_down_rush",
        "comms_drop_two_robots",
        "battery_stress",
        "perfect_storm",
    ],
)
def test_shipped_chaos_scenarios_pass_in_heuristic_mode(scenario_name: str) -> None:
    scenario_path = Path("scenarios/chaos") / f"{scenario_name}.yaml"
    assert scenario_path.exists()

    res = run_single_chaos_seed(scenario_path=scenario_path, mode="heuristic", seed=42)
    assert res["passed"], f"Scenario {scenario_name} failed pass criteria: {res}"
    assert res["lost_orders"] == 0, "Zero lost orders invariant failed"
    assert res["safety_violations"] == 0, "Zero safety violations invariant failed"
    assert res["unverified_completed"] == 0, "Zero unverified picks completed invariant failed"


def test_replenishment_lite_and_urgent_order_priority() -> None:
    """P6-A8: Replenishment-lite triggers low-stock tasks, but urgent order work outranks replenishment."""
    cfg, _ = load_config(scenario_name="standard")
    layout = generate_parametric_layout(cfg.layout)
    from robofleet.catalogue.generator import generate_catalogue
    from robofleet.catalogue.slotting import slot_inventory

    skus = generate_catalogue(sku_count=50, seed=42)
    bins, _ = slot_inventory(skus=skus, layout=layout, seed=42)

    # Force bin 0 to have 1 unit (below low_stock_threshold = 3)
    bins[0].quantity = 1
    target_bin_id = bins[0].bin_id

    engine = SimEngine(config=cfg, layout=layout, skus=skus, bins=bins)
    rep_mgr = engine.replenishment_mgr

    # 1. Step without urgent orders -> restock task is created and advances
    engine.step()
    assert len(rep_mgr.active_tasks) >= 1
    assert any(t.bin_id == target_bin_id for t in rep_mgr.active_tasks)

    # 2. Add an urgent active order (priority = 10, at_risk = True)
    urgent_order = Order(
        order_id="ORD-URGENT",
        priority=10,
        at_risk=True,
        status=OrderStatus.RETRIEVING,
        created_tick=engine.clock.tick,
        deadline_tick=engine.clock.tick + 50,
    )
    engine.orders.append(urgent_order)

    # Advance steps with urgent order in flight
    initial_elapsed = rep_mgr.active_tasks[0].elapsed_ticks
    engine.step()

    # Replenishment task should yield / not advance while urgent order is active!
    assert rep_mgr.active_tasks[0].elapsed_ticks == initial_elapsed

    # 3. Mark urgent order completed -> replenishment resumes
    urgent_order.status = OrderStatus.HANDED_OVER
    engine.step()
    assert rep_mgr.active_tasks[0].elapsed_ticks > initial_elapsed


def test_reslotting_recommender_never_moves_stock_automatically() -> None:
    """P6-A8: Re-slotting engine outputs recommendations only. No automatic moves occur."""
    cfg, _ = load_config(scenario_name="standard")
    layout = generate_parametric_layout(cfg.layout)
    from robofleet.catalogue.generator import generate_catalogue
    from robofleet.catalogue.slotting import slot_inventory

    skus = generate_catalogue(sku_count=100, seed=42)
    bins, _ = slot_inventory(skus=skus, layout=layout, seed=42)

    # Record initial bin SKU mappings and quantities
    initial_bin_state = {b.bin_id: (b.sku_id, b.quantity) for b in bins}

    engine = SimEngine(config=cfg, layout=layout, skus=skus, bins=bins)
    recommender = engine.reslot_recommender

    # Force immediate evaluation
    recs = recommender.evaluate(current_tick=250)
    assert len(recs) > 0, "Recommender should find candidate moves"

    # Verify recommendations are in RECOMMENDED status
    for r in recs:
        assert r.status == "RECOMMENDED"

    # Verify bins did NOT change automatically
    for b in engine.bins:
        assert (b.sku_id, b.quantity) == initial_bin_state[b.bin_id], "Bins must not change automatically"

    # Supervisor approves one recommendation
    first_rec = recs[0]
    ok, msg = recommender.approve_recommendation(
        recommendation_id=first_rec.recommendation_id,
        actor="supervisor_dan",
        role="supervisor",
        current_tick=255,
    )
    assert ok
    assert first_rec.status == "APPROVED"
