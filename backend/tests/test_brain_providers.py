"""Tests for Phase 5 LLM Provider Port, Circuit Breaker, and Failover."""

from __future__ import annotations

import time
import pytest
from robofleet.brain.brief import SituationBriefBuilder
from robofleet.brain.providers.anthropic import AnthropicProvider
from robofleet.brain.providers.heuristic import HeuristicProvider
from robofleet.brain.providers.replay import ReplayProvider
from robofleet.brain.specialists.exceptions import ExceptionsRecoverySpecialist
from robofleet.brain.specialists.explainer import ExplainerSpecialist
from robofleet.brain.specialists.planner import PlannerSpecialist
from robofleet.brain.specialists.traffic import TrafficFleetSpecialist
from robofleet.contracts.brain import (
    BriefKPIs,
    BriefOrderSummary,
    BriefRobotSummary,
    BriefStationQueue,
    SituationBrief,
)
from robofleet.contracts.common import Coordinate


@pytest.fixture
def sample_brief() -> SituationBrief:
    return SituationBrief(
        tick=100,
        trigger="order_at_risk",
        kpis=BriefKPIs(
            queue_depth=5,
            throughput_per_hr=120.0,
            at_risk_count=1,
            active_alerts_count=0,
            robots_moving=8,
            robots_idle=2,
            robots_charging=0,
            fleet_utilization_pct=80.0,
        ),
        at_risk_orders=[
            BriefOrderSummary(
                order_id="ORD-999",
                lines_count=2,
                sla_remaining_ticks=80,
                priority=2,
                assigned_robot_id=None,
                state="QUEUED",
            )
        ],
        station_queues=[
            BriefStationQueue(station_id="ST-01", queue_length=5),
            BriefStationQueue(station_id="ST-02", queue_length=0),
        ],
        critical_robots=[
            BriefRobotSummary(
                robot_id="R-003",
                state="IDLE",
                battery_percent=18.5,
                current_coord=Coordinate(x=5, y=5),
            )
        ],
        congested_cells=[Coordinate(x=10, y=10)],
        active_alert_ids=[],
        held_zone_ids=[],
        recent_decision_ids=[],
        brief_hash="test-hash-123",
    )


@pytest.fixture
def specialists():
    return [
        PlannerSpecialist(),
        TrafficFleetSpecialist(),
        ExceptionsRecoverySpecialist(),
        ExplainerSpecialist(),
    ]


@pytest.mark.asyncio
async def test_heuristic_provider_latency_and_decisions(sample_brief: SituationBrief, specialists) -> None:
    provider = HeuristicProvider()
    t0 = time.perf_counter()
    res = await provider.decide(sample_brief, specialists)
    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    assert elapsed_ms < 20.0  # Must be fast sub-tick (< 20ms)
    assert len(res.commands) >= 2  # Reprioritise ORD-999 + Send R-003 to charge
    assert res.cost_usd == 0.0

    cmd_types = [c["command_type"] for c in res.commands]
    assert "reprioritise_order" in cmd_types
    assert "send_to_charge" in cmd_types


@pytest.mark.asyncio
async def test_anthropic_circuit_breaker_and_failover(sample_brief: SituationBrief, specialists) -> None:
    # Set invalid API key to trigger failover
    provider = AnthropicProvider(api_key="invalid-key-for-test", failure_threshold=2, cooldown_sec=10.0)

    # First call: should failover seamlessly to heuristic baseline without throwing exception
    res1 = await provider.decide(sample_brief, specialists)
    assert res1 is not None
    assert len(res1.commands) >= 1  # Executed heuristic baseline commands
    assert provider.consecutive_failures == 1
    assert not provider.circuit_tripped

    # Second call: fails again, tripping circuit breaker
    res2 = await provider.decide(sample_brief, specialists)
    assert res2 is not None
    assert provider.consecutive_failures == 2
    assert provider.circuit_tripped

    # Third call: circuit breaker is tripped, immediate fast failover (< 5ms) without calling network
    t0 = time.perf_counter()
    res3 = await provider.decide(sample_brief, specialists)
    trip_latency = (time.perf_counter() - t0) * 1000.0

    assert trip_latency < 10.0
    assert len(res3.commands) >= 1
