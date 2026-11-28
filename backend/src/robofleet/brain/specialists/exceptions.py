"""Exceptions and Recovery Specialist (Phase 5 - Upgraded).
Detects blocked aisles, faulted AMRs, station outages, and proposes task reassignment,
zone isolation against real layout zones, or human escalation.
"""

from __future__ import annotations

from pathlib import Path

from robofleet.contracts.brain import (
    DecisionProposal,
    EscalateToHumanCommand,
    HoldZoneCommand,
    RerouteStationCommand,
    SituationBrief,
)


class ExceptionsRecoverySpecialist:
    name: str = "exceptions"
    prompt_file: Path = Path("prompts/exceptions_v1.txt")

    def propose(self, brief: SituationBrief) -> list[DecisionProposal]:
        proposals: list[DecisionProposal] = []

        # 1. Faulted / unavailable robot task preservation & escalation
        for r in brief.critical_robots:
            if "FAULT" in r.state or "UNAVAILABLE" in r.state or r.fault is not None:
                proposals.append(
                    DecisionProposal(
                        specialist="exceptions",
                        action="reassign_task",
                        command={
                            "command_type": "reassign_task",
                            "robot_id": r.robot_id,
                            "issued_tick": brief.tick,
                            "reason": f"Reassign pending work from unavailable AMR {r.robot_id}",
                        },
                        confidence=0.95,
                        rationale=f"Reassign pending tasks of faulted AMR {r.robot_id} to active fleet pool.",
                    )
                )

                cmd = EscalateToHumanCommand(
                    action_description=f"AMR {r.robot_id} is {r.state}; inspect hardware or clear fault",
                    action_command={"command_type": "clear_fault", "target_id": r.robot_id},
                    severity="CRITICAL",
                    timeout_ticks=50,
                    default_action="deny",
                    issued_tick=brief.tick,
                    reason=f"Robot {r.robot_id} hardware/availability fault requires supervisor intervention",
                )
                proposals.append(
                    DecisionProposal(
                        specialist="exceptions",
                        action="escalate_to_human",
                        command=cmd.model_dump(),
                        confidence=0.98,
                        rationale=f"AMR {r.robot_id} unavailable; escalating to human supervisor.",
                    )
                )

        # 2. Offline / unavailable picking station recovery
        for st in brief.station_queues:
            if not st.is_active and st.queue_length > 0:
                rr_cmd = RerouteStationCommand(
                    station_id=st.station_id,
                    issued_tick=brief.tick,
                    expected_effect=f"Rebalance queued AMRs away from offline station {st.station_id}",
                    reason=f"Station {st.station_id} is offline with {st.queue_length} queued AMRs",
                )
                proposals.append(
                    DecisionProposal(
                        specialist="exceptions",
                        action="reroute_station",
                        command=rr_cmd.model_dump(),
                        confidence=0.92,
                        rationale=rr_cmd.reason,
                    )
                )

        # 3. Critical safety alerts requiring temporary zone isolation (using real layout zone!)
        if brief.active_alert_ids and not brief.held_zone_ids and brief.available_zones:
            alert_id = brief.active_alert_ids[0]
            target_zone = brief.available_zones[0]
            h_cmd = HoldZoneCommand(
                zone_id=target_zone,
                duration_ticks=200,
                issued_tick=brief.tick,
                expected_effect=f"Hold zone {target_zone} temporarily to clear active safety hazard",
                reason=f"Active alert {alert_id} requires temporary traffic clearance in {target_zone}",
            )
            proposals.append(
                DecisionProposal(
                    specialist="exceptions",
                    action="hold_zone",
                    command=h_cmd.model_dump(),
                    confidence=0.82,
                    rationale=f"Active safety alert {alert_id}; holding {target_zone} temporarily to prevent congestion.",
                )
            )

        return proposals
