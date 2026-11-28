"""Deterministic Heuristic Provider (Baseline Intelligence).

Invokes Planner, Traffic, and Exceptions specialists cleanly, arbitrates conflicts,
handles battery triage, SLA escalation, and deadlock yield recovery in < 5ms with zero cost.
"""

from __future__ import annotations

import time
from typing import Any

from robofleet.brain.providers.base import (
    LLMProviderResult,
    collect_and_arbitrate_specialists,
)
from robofleet.contracts.brain import (
    DecisionProposal,
    NoActionCommand,
    ReprioritiseOrderCommand,
    SendToChargeCommand,
    SetStationPolicyCommand,
    SituationBrief,
    YieldRobotCommand,
)


class HeuristicProvider:
    name: str = "heuristic"

    async def decide(
        self,
        brief: SituationBrief,
        specialists: list[Any] | None = None,
    ) -> LLMProviderResult:
        t0 = time.perf_counter()

        # 1. Invoke and arbitrate all configured Specialists
        proposals: list[DecisionProposal] = collect_and_arbitrate_specialists(brief, specialists)
        commands: list[dict[str, Any]] = [p.command for p in proposals if p.command]
        rationales: list[str] = [p.rationale for p in proposals if p.rationale]

        # 2. Direct deterministic fallback safeguards when no specialists were passed
        existing_types = {(c.get("command_type"), c.get("robot_id"), c.get("order_id")) for c in commands}

        # Critical Battery Triage
        low_thresh = brief.battery_thresholds.get("low_battery_threshold", 25.0)
        for r in brief.critical_robots:
            if r.battery_percent < low_thresh and r.state not in ("CHARGING", "FAULTED", "UNAVAILABLE"):
                key = ("send_to_charge", r.robot_id, None)
                if not any(c.get("robot_id") == r.robot_id for c in commands):
                    cmd = SendToChargeCommand(
                        robot_id=r.robot_id,
                        issued_tick=brief.tick,
                        expected_effect="Prevent robot stall by dispatching to nearest available charger",
                        reason=f"Robot {r.robot_id} battery is critically low at {r.battery_percent}%",
                    )
                    proposals.append(
                        DecisionProposal(
                            specialist="traffic",
                            action="send_to_charge",
                            command=cmd.model_dump(),
                            confidence=0.95,
                            rationale=cmd.reason,
                        )
                    )
                    commands.append(cmd.model_dump())
                    rationales.append(f"Robot {r.robot_id} ({r.battery_percent}%) routed to charging bank")
                    existing_types.add(key)
                    break

        # Deadlock Yield Arbitration
        for dl in brief.deadlocks_detected:
            if (
                dl.recommended_yield_robot
                and not dl.no_route_available
                and not any(c.get("robot_id") == dl.recommended_yield_robot for c in commands)
            ):
                    y_cmd = YieldRobotCommand(
                        robot_id=dl.recommended_yield_robot,
                        yield_cell=dl.recommended_yield_cell,
                        priority_robot_id=dl.recommended_priority_robot,
                        issued_tick=brief.tick,
                        expected_effect=f"Break {dl.conflict_type} so {dl.recommended_priority_robot or 'priority AMR'} clears",
                        reason=dl.description or f"Resolve {dl.conflict_type}",
                    )
                    proposals.append(
                        DecisionProposal(
                            specialist="traffic",
                            action="yield_robot",
                            command=y_cmd.model_dump(),
                            confidence=0.92,
                            rationale=y_cmd.reason,
                        )
                    )
                    commands.append(y_cmd.model_dump())
                    rationales.append(y_cmd.reason)
                    break

        # At-Risk Order Prioritization
        if not any(c.get("command_type") == "reprioritise_order" for c in commands):
            for o in brief.at_risk_orders:
                if o.sla_remaining_ticks < 120 and o.priority < 8:
                    r_cmd = ReprioritiseOrderCommand(
                        order_id=o.order_id,
                        new_priority=10,
                        issued_tick=brief.tick,
                        expected_effect="Elevate order to top priority queue",
                        reason=f"Order {o.order_id} has only {o.sla_remaining_ticks} ticks SLA remaining",
                    )
                    proposals.append(
                        DecisionProposal(
                            specialist="planner",
                            action="reprioritise_order",
                            command=r_cmd.model_dump(),
                            confidence=0.90,
                            rationale=r_cmd.reason,
                        )
                    )
                    commands.append(r_cmd.model_dump())
                    rationales.append(f"Elevated urgent order {o.order_id} to express priority 10")
                    break

        # Station Load Balancing
        if not any(c.get("command_type") == "set_station_policy" for c in commands):
            congested_stations = [s for s in brief.station_queues if s.queue_length >= 4]
            idle_stations = [s for s in brief.station_queues if s.queue_length <= 1]
            if congested_stations and idle_stations:
                c_st = congested_stations[0]
                i_st = idle_stations[0]
                s_cmd = SetStationPolicyCommand(
                    station_id=c_st.station_id,
                    max_queue_depth=5,
                    batch_window_sec=15.0,
                    issued_tick=brief.tick,
                    expected_effect=f"Throttle input to station {c_st.station_id} to rebalance toward {i_st.station_id}",
                    reason=f"Station {c_st.station_id} queue is {c_st.queue_length} while station {i_st.station_id} is idle",
                )
                proposals.append(
                    DecisionProposal(
                        specialist="planner",
                        action="set_station_policy",
                        command=s_cmd.model_dump(),
                        confidence=0.85,
                        rationale=s_cmd.reason,
                    )
                )
                commands.append(s_cmd.model_dump())
                rationales.append(f"Throttled station {c_st.station_id} to balance with {i_st.station_id}")

        # Nominal No-Action fallback when queue is smooth
        if not commands:
            n_cmd = NoActionCommand(
                issued_tick=brief.tick,
                expected_effect="Store operations running nominally within SLA bounds",
                reason=f"Queue depth is {brief.kpis.queue_depth}, utilization is {brief.kpis.fleet_utilization_pct}%, zero critical bottlenecks",
            )
            proposals.append(
                DecisionProposal(
                    specialist="explainer",
                    action="no_action",
                    command=n_cmd.model_dump(),
                    confidence=1.0,
                    rationale=n_cmd.reason,
                )
            )
            commands.append(n_cmd.model_dump())
            rationales.append(f"Operations nominal ({brief.kpis.fleet_utilization_pct}% utilization); no intervention required")

        latency = (time.perf_counter() - t0) * 1000.0
        traffic_plan = {
            "conflict_detected": bool(brief.deadlocks_detected or brief.congested_cells),
            "deadlock_detected": bool(brief.deadlocks_detected),
            "robots_affected": sorted({r for dl in brief.deadlocks_detected for r in dl.robots_involved}),
            "resolution": rationales[0] if rationales else "Nominal operations",
        }

        return LLMProviderResult(
            proposals=proposals,
            commands=commands,
            rationale="; ".join(rationales[:4]),
            situation_summary=f"Deterministic assessment at tick {brief.tick}: {brief.trigger}",
            traffic_plan=traffic_plan,
            token_usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            cost_usd=0.0,
            latency_ms=round(latency, 2),
            operating_mode="heuristic",
            provider_name="Heuristic",
            model_name="deterministic-rules",
            fallback_used=False,
            provider_status="connected",
            attribution="Heuristic Mode — deterministic provider",
        )
