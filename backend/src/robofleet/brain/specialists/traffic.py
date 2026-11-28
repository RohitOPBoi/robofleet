"""Traffic and Fleet Specialist (Phase 5 - Upgraded).
Focuses on deadlock detection/recovery, intersection arbitration, congestion bypass,
and energy-aware battery protection.
"""

from __future__ import annotations

from pathlib import Path

from robofleet.contracts.brain import (
    DecisionProposal,
    EscalateToHumanCommand,
    RerouteRobotCommand,
    SendToChargeCommand,
    SituationBrief,
    YieldRobotCommand,
)


class TrafficFleetSpecialist:
    name: str = "traffic"
    prompt_file: Path = Path("prompts/traffic_v1.txt")

    def propose(self, brief: SituationBrief) -> list[DecisionProposal]:
        proposals: list[DecisionProposal] = []
        low_thresh = brief.battery_thresholds.get("low_battery_threshold", 25.0)
        effective_charge_trigger = max(25.0, low_thresh)

        # 1. Deadlock and Corridor Conflict Arbitration
        for dl in brief.deadlocks_detected:
            if dl.no_route_available:
                esc = EscalateToHumanCommand(
                    action_description=f"{dl.conflict_type}: No safe yield or detour available for {dl.robots_involved}",
                    action_command={},
                    severity="CRITICAL",
                    timeout_ticks=50,
                    default_action="deny",
                    issued_tick=brief.tick,
                    reason=dl.description or f"Deadlock {dl.conflict_id} has zero valid escape routes",
                )
                proposals.append(
                    DecisionProposal(
                        specialist="traffic",
                        action="escalate_to_human",
                        command=esc.model_dump(),
                        confidence=0.95,
                        rationale=dl.description or esc.reason,
                    )
                )
                continue

            if dl.recommended_yield_robot:
                y_cmd = YieldRobotCommand(
                    robot_id=dl.recommended_yield_robot,
                    yield_cell=dl.recommended_yield_cell,
                    hold_ticks=15,
                    priority_robot_id=dl.recommended_priority_robot,
                    issued_tick=brief.tick,
                    expected_effect=f"Clear {dl.conflict_type} by yielding {dl.recommended_yield_robot} so {dl.recommended_priority_robot or 'priority robot'} advances",
                    reason=dl.description or f"Resolve {dl.conflict_type} involving {', '.join(dl.robots_involved)}",
                )
                proposals.append(
                    DecisionProposal(
                        specialist="traffic",
                        action="yield_robot",
                        command=y_cmd.model_dump(),
                        confidence=0.93,
                        rationale=y_cmd.reason,
                    )
                )

        # 2. Critical Battery Protection & Feasibility Check
        for r in brief.critical_robots:
            is_deadlocked_priority = any(
                dl.recommended_priority_robot == r.robot_id for dl in brief.deadlocks_detected
            )
            if r.battery_percent < effective_charge_trigger and r.state not in ("CHARGING", "FAULTED", "UNAVAILABLE"):
                charger_id = brief.available_chargers[0] if brief.available_chargers else None
                cmd = SendToChargeCommand(
                    robot_id=r.robot_id,
                    charger_id=charger_id,
                    issued_tick=brief.tick,
                    expected_effect=f"Dispatch AMR {r.robot_id} to charging bay to prevent stall",
                    reason=f"AMR {r.robot_id} battery at {r.battery_percent}% (charger distance ~{r.nearest_charger_distance or '?'} cells)",
                )
                proposals.append(
                    DecisionProposal(
                        specialist="traffic",
                        action="send_to_charge",
                        command=cmd.model_dump(),
                        confidence=0.96 if not is_deadlocked_priority else 0.90,
                        rationale=f"AMR {r.robot_id} battery is {r.battery_percent}%; routing to charger.",
                    )
                )

        # 3. Congestion Hotspot Rerouting (for blocked AMRs not already receiving yield instruction)
        yielding_ids = {
            p.command.get("robot_id")
            for p in proposals
            if p.action == "yield_robot"
        }
        if brief.congested_cells:
            hotspots = brief.congested_cells[:3]
            for r in brief.critical_robots:
                if r.robot_id in yielding_ids:
                    continue
                if "BLOCKED" in r.state or r.blocked_ticks >= 12 or "WAITING" in r.state and r.blocked_ticks >= 12:
                    reroute_cmd = RerouteRobotCommand(
                        robot_id=r.robot_id,
                        avoid_cells=hotspots,
                        issued_tick=brief.tick,
                        expected_effect=f"Reroute AMR {r.robot_id} around junction hotspots",
                        reason=f"AMR {r.robot_id} stalled {r.blocked_ticks} ticks near congested cells",
                    )
                    proposals.append(
                        DecisionProposal(
                            specialist="traffic",
                            action="reroute_robot",
                            command=reroute_cmd.model_dump(),
                            confidence=0.85,
                            rationale=f"AMR {r.robot_id} stalled near congestion; rerouting around {len(hotspots)} hotspots.",
                        )
                    )

        return proposals
