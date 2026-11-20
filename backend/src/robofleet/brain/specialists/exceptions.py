"""Exceptions and Recovery Specialist (Phase 5).
Detects blocked aisles, faulted AMRs, and proposes zone isolation or human escalation.
"""

from __future__ import annotations

from pathlib import Path
from robofleet.contracts.brain import (
    DecisionProposal,
    EscalateToHumanCommand,
    HoldZoneCommand,
    SituationBrief,
)


class ExceptionsRecoverySpecialist:
    name: str = "exceptions"
    prompt_file: Path = Path("prompts/exceptions_v1.txt")

    def propose(self, brief: SituationBrief) -> list[DecisionProposal]:
        proposals: list[DecisionProposal] = []

        # 1. Faulted robot escalation
        for r in brief.critical_robots:
            if "FAULT" in r.state:
                cmd = EscalateToHumanCommand(
                    action_description=f"AMR {r.robot_id} has entered FAULTED state; dispatch maintenance",
                    action_command={"command_type": "clear_fault", "target_id": r.robot_id},
                    severity="CRITICAL",
                    timeout_ticks=50,
                    default_action="deny",
                    reason=f"Robot {r.robot_id} hardware fault requires technician inspection",
                )
                proposals.append(
                    DecisionProposal(
                        specialist="exceptions",
                        action="escalate_to_human",
                        command=cmd.model_dump(),
                        confidence=0.98,
                        rationale=f"AMR {r.robot_id} is FAULTED; escalating to human supervisor for technician dispatch.",
                    )
                )

        # 2. Critical alerts requiring temporary zone isolation
        if brief.active_alert_ids and not brief.held_zone_ids:
            # Recommend holding zone if critical safety alert exists
            alert_id = brief.active_alert_ids[0]
            cmd = HoldZoneCommand(
                zone_id="aisle_zone_1",
                duration_ticks=200,
                expected_effect="Hold aisle zone to clear active safety hazard",
                reason=f"Active alert {alert_id} requires temporary traffic clearance",
            )
            proposals.append(
                DecisionProposal(
                    specialist="exceptions",
                    action="hold_zone",
                    command=cmd.model_dump(),
                    confidence=0.82,
                    rationale=f"Active safety alert {alert_id}; holding zone temporarily to prevent congestion.",
                )
            )

        return proposals
