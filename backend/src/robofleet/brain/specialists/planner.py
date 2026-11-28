"""Planner Specialist (Phase 5 - Upgraded).
Focuses on order batching, deadline prioritization, starvation-aware task allocation,
and station load balancing.
"""

from __future__ import annotations

from pathlib import Path

from robofleet.contracts.brain import (
    AssignTaskCommand,
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
        low_bat_thresh = brief.battery_thresholds.get("low_battery_threshold", 20.0)

        # 1. At-risk orders nearing SLA deadline
        for o in brief.at_risk_orders:
            if o.sla_remaining_ticks < 150 and o.priority < 8:
                cmd = ReprioritiseOrderCommand(
                    order_id=o.order_id,
                    new_priority=10,
                    issued_tick=brief.tick,
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
                break

        # 2. Fair task allocation when orders wait unassigned and healthy idle robots exist
        unassigned_orders = [
            o
            for o in brief.at_risk_orders
            if o.assigned_robot_id is None and o.state in ("RECEIVED", "QUEUED")
        ]
        healthy_idle_robots = [
            r
            for r in brief.robots_overview
            if r.state == "IDLE"
            and r.current_task_type is None
            and r.battery_percent > max(25.0, low_bat_thresh + 5.0)
            and r.fault is None
        ]
        if unassigned_orders and healthy_idle_robots:
            # Prefer highest battery idle robot for fairness & energy feasibility
            chosen_robot = max(healthy_idle_robots, key=lambda r: r.battery_percent)
            target_order = unassigned_orders[0]
            assign_cmd = AssignTaskCommand(
                robot_id=chosen_robot.robot_id,
                order_id=target_order.order_id,
                task_type="PICK",
                issued_tick=brief.tick,
                expected_effect=f"Assign waiting order {target_order.order_id} to healthy idle AMR {chosen_robot.robot_id}",
                reason=f"Order {target_order.order_id} queued with SLA {target_order.sla_remaining_ticks}t while {chosen_robot.robot_id} idle at {chosen_robot.battery_percent}% battery",
            )
            proposals.append(
                DecisionProposal(
                    specialist="planner",
                    action="assign_task",
                    command=assign_cmd.model_dump(),
                    confidence=0.87,
                    rationale=assign_cmd.reason,
                )
            )

        # 3. Station load arbitration
        congested = [s for s in brief.station_queues if s.queue_length >= 4]
        idle = [s for s in brief.station_queues if s.queue_length <= 1 and s.is_active]
        if congested and idle:
            c = congested[0]
            st_cmd = SetStationPolicyCommand(
                station_id=c.station_id,
                max_queue_depth=4,
                batch_window_sec=15.0,
                issued_tick=brief.tick,
                expected_effect=f"Throttle station {c.station_id} queue to balance load toward {idle[0].station_id}",
                reason=f"Station {c.station_id} queue is {c.queue_length} while {idle[0].station_id} is lightly loaded",
            )
            proposals.append(
                DecisionProposal(
                    specialist="planner",
                    action="set_station_policy",
                    command=st_cmd.model_dump(),
                    confidence=0.88,
                    rationale=f"Station {c.station_id} queue is {c.queue_length}; throttling intake to balance picking flow.",
                )
            )

        return proposals
