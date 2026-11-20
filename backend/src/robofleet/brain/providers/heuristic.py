"""Heuristic LLM Provider (Phase 5 - CA-6).
Deterministic, high-speed fallback provider requiring 0ms network latency.
Guarantees bit-for-bit determinism and operates seamlessly in headless/offline environments.
"""

from __future__ import annotations

import time
from typing import Any
from robofleet.brain.providers.base import LLMProviderResult
from robofleet.contracts.brain import (
    DecisionProposal,
    NoActionCommand,
    ReprioritiseOrderCommand,
    SendToChargeCommand,
    SetStationPolicyCommand,
    SituationBrief,
)


class HeuristicProvider:
    name: str = "heuristic"

    async def decide(
        self,
        brief: SituationBrief,
        specialists: list[Any] | None = None,
    ) -> LLMProviderResult:
        t0 = time.perf_counter()
        proposals: list[DecisionProposal] = []
        commands: list[dict[str, Any]] = []
        rationales: list[str] = []

        # 1. Critical Battery Triage
        for r in brief.critical_robots:
            if r.battery_percent < 25.0 and r.state not in ("CHARGING", "FAULTED"):
                cmd = SendToChargeCommand(
                    robot_id=r.robot_id,
                    expected_effect="Prevent robot stall by dispatching to charger",
                    reason=f"Robot {r.robot_id} battery is critically low at {r.battery_percent}%",
                )
                proposals.append(
                    DecisionProposal(
                        specialist="traffic",
                        action="send_to_charge",
                        command=cmd.model_dump(),
                        confidence=0.95,
                        rationale=f"Robot {r.robot_id} battery is critically low ({r.battery_percent}%); dispatching to charger.",
                    )
                )
                commands.append(cmd.model_dump())
                rationales.append(f"Robot {r.robot_id} ({r.battery_percent}%) routed to charging bank")
                break  # Bounded to at most 1 charging command per tick

        # 2. At-Risk Order Prioritization
        for o in brief.at_risk_orders:
            if o.sla_remaining_ticks < 120 and o.priority < 8:
                cmd = ReprioritiseOrderCommand(
                    order_id=o.order_id,
                    new_priority=10,
                    expected_effect="Elevate order to top priority queue",
                    reason=f"Order {o.order_id} has only {o.sla_remaining_ticks} ticks SLA remaining",
                )
                proposals.append(
                    DecisionProposal(
                        specialist="planner",
                        action="reprioritise_order",
                        command=cmd.model_dump(),
                        confidence=0.90,
                        rationale=f"Order {o.order_id} SLA remaining ({o.sla_remaining_ticks} ticks) is under deadline threshold; elevating to priority 10.",
                    )
                )
                commands.append(cmd.model_dump())
                rationales.append(f"Elevated urgent order {o.order_id} to express priority 10")
                break

        # 3. Station Load Balancing
        congested_stations = [s for s in brief.station_queues if s.queue_length >= 4]
        idle_stations = [s for s in brief.station_queues if s.queue_length <= 1]
        if congested_stations and idle_stations:
            c_st = congested_stations[0]
            i_st = idle_stations[0]
            cmd = SetStationPolicyCommand(
                station_id=c_st.station_id,
                max_queue_depth=5,
                batch_window_sec=15.0,
                expected_effect=f"Throttle input to station {c_st.station_id} to rebalance toward {i_st.station_id}",
                reason=f"Station {c_st.station_id} queue is {c_st.queue_length} while station {i_st.station_id} is idle",
            )
            proposals.append(
                DecisionProposal(
                    specialist="planner",
                    action="set_station_policy",
                    command=cmd.model_dump(),
                    confidence=0.85,
                    rationale=f"Station {c_st.station_id} queue is {c_st.queue_length} and station {i_st.station_id} is idle; throttling input to prevent dock bottleneck.",
                )
            )
            commands.append(cmd.model_dump())
            rationales.append(f"Throttled station {c_st.station_id} to balance with idle station {i_st.station_id}")

        # 4. Default nominal action
        if not commands:
            cmd = NoActionCommand(
                expected_effect="Store operations running nominally within SLA bounds",
                reason=f"Queue depth is {brief.kpis.queue_depth}, utilization is {brief.kpis.fleet_utilization_pct}%, zero critical bottlenecks",
            )
            proposals.append(
                DecisionProposal(
                    specialist="explainer",
                    action="no_action",
                    command=cmd.model_dump(),
                    confidence=1.0,
                    rationale=f"Dark store operations nominal: {brief.kpis.queue_depth} orders queued, {brief.kpis.fleet_utilization_pct}% fleet utilization.",
                )
            )
            commands.append(cmd.model_dump())
            rationales.append(f"Operations nominal ({brief.kpis.fleet_utilization_pct}% utilization); no intervention required")

        latency = (time.perf_counter() - t0) * 1000.0

        return LLMProviderResult(
            proposals=proposals,
            commands=commands,
            rationale="; ".join(rationales),
            token_usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            cost_usd=0.0,
            latency_ms=round(latency, 2),
            provider_name="heuristic",
        )
