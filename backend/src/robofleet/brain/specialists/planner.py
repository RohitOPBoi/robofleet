"""Planner Specialist (Phase 5).
Focuses on order batching, deadline prioritization, and station load arbitration.
"""

from __future__ import annotations

from pathlib import Path
from robofleet.contracts.brain import (
    DecisionProposal,
    ReprioritiseOrderCommand,
    SetStationPolicyCommand,
    SituationBrief,
)


class PlannerSpecialist:
    name: str = "planner"
    prompt_file: Path = Path("prompts/planner_v1.txt")

    def propose(self, brief: SituationBrief) -> list[DecisionProposal]:
        proposals: list[DecisionProposal] = []

        # 1. At-risk orders nearing SLA deadline
        for o in brief.at_risk_orders:
            if o.sla_remaining_ticks < 150 and o.priority < 8:
                cmd = ReprioritiseOrderCommand(
                    order_id=o.order_id,
                    new_priority=10,
                    expected_effect=f"Elevate order {o.order_id} to highest priority tier",
                    reason=f"Order {o.order_id} has {o.sla_remaining_ticks} ticks SLA remaining",
                )
                proposals.append(
                    DecisionProposal(
                        specialist="planner",
                        action="reprioritise_order",
                        command=cmd.model_dump(),
                        confidence=0.92,
                        rationale=f"Order {o.order_id} has only {o.sla_remaining_ticks} ticks remaining; elevating priority.",
                    )
                )

        # 2. Station load arbitration
        congested = [s for s in brief.station_queues if s.queue_length >= 4]
        idle = [s for s in brief.station_queues if s.queue_length <= 1]
        if congested and idle:
            c = congested[0]
            cmd = SetStationPolicyCommand(
                station_id=c.station_id,
                max_queue_depth=4,
                batch_window_sec=15.0,
                expected_effect=f"Throttle station {c.station_id} queue to balance load",
                reason=f"Station {c.station_id} queue is {c.queue_length} while other stations are idle",
            )
            proposals.append(
                DecisionProposal(
                    specialist="planner",
                    action="set_station_policy",
                    command=cmd.model_dump(),
                    confidence=0.88,
                    rationale=f"Station {c.station_id} queue is {c.queue_length}; throttling intake to balance picking flow.",
                )
            )

        return proposals
