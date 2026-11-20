"""Traffic and Fleet Specialist (Phase 5).
Focuses on congestion mitigation, battery preservation, and fleet re-routing.
"""

from __future__ import annotations

from pathlib import Path
from robofleet.contracts.brain import (
    DecisionProposal,
    RerouteRobotCommand,
    SendToChargeCommand,
    SituationBrief,
)


class TrafficFleetSpecialist:
    name: str = "traffic"
    prompt_file: Path = Path("prompts/traffic_v1.txt")

    def propose(self, brief: SituationBrief) -> list[DecisionProposal]:
        proposals: list[DecisionProposal] = []

        # 1. Critical Battery Protection
        for r in brief.critical_robots:
            if r.battery_percent < 25.0 and r.state not in ("CHARGING", "FAULTED"):
                cmd = SendToChargeCommand(
                    robot_id=r.robot_id,
                    expected_effect=f"Recharge AMR {r.robot_id} to prevent operational stall",
                    reason=f"AMR {r.robot_id} battery is at {r.battery_percent}%",
                )
                proposals.append(
                    DecisionProposal(
                        specialist="traffic",
                        action="send_to_charge",
                        command=cmd.model_dump(),
                        confidence=0.96,
                        rationale=f"AMR {r.robot_id} battery is {r.battery_percent}%; dispatching to charger.",
                    )
                )

        # 2. Congestion re-routing
        if brief.congested_cells:
            # If robots are heading near congested cells, recommend avoidance
            hotspots = brief.congested_cells[:3]
            for r in brief.critical_robots:
                if "BLOCKED" in r.state:
                    cmd = RerouteRobotCommand(
                        robot_id=r.robot_id,
                        avoid_cells=hotspots,
                        expected_effect=f"Reroute AMR {r.robot_id} around junction hotspots",
                        reason=f"AMR {r.robot_id} is blocked near congested cells",
                    )
                    proposals.append(
                        DecisionProposal(
                            specialist="traffic",
                            action="reroute_robot",
                            command=cmd.model_dump(),
                            confidence=0.85,
                            rationale=f"AMR {r.robot_id} blocked; rerouting around {len(hotspots)} junction hotspots.",
                        )
                    )

        return proposals
