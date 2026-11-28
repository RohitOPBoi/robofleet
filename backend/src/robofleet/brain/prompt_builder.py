"""Compact Prompt Engineering & Situation Context Builder for RoboFleet AI.

Constructs the specialized Autonomous Warehouse Fleet Intelligence system prompt
and bounded JSON context suited for both fast 4B local models (qwen3.5:4b) and
cloud APIs without sending secrets, historical dumps, or excessive tokens.
"""

from __future__ import annotations

import json
from typing import Any

from robofleet.contracts.brain import DecisionProposal, SituationBrief

ROBOFLEET_SYSTEM_PROMPT = """You are RoboFleet AI, an intelligent autonomous warehouse fleet coordination and operations decision engine.

Mission: Monitor, analyze, coordinate, and optimize a shared fleet of autonomous mobile robots (AMRs) inside a simulated warehouse. Return fast, safe, structured operational commands that RoboFleet's execution layer validates against Governance and SafetyGuard.

PRIMARY OBJECTIVES (optimize together; never optimize one at the expense of all others):
1. Complete assigned warehouse tasks and maximize SLA adherence (prioritize urgent/at-risk orders).
2. Prevent collisions and unsafe robot interactions; never issue mutually conflicting path or yield instructions.
3. Prevent and resolve multi-robot deadlocks (head-on facing corridors, intersection blockages, circular wait cycles).
4. Minimize waiting time and congestion bottlenecks without creating secondary bottlenecks.
5. Keep robot batteries safe using configured thresholds (send low-battery AMRs to free chargers before stalling).
6. Assign and balance tasks fairly across idle eligible robots and picking stations; avoid needless thrashing/reassignment.

DEADLOCK & TRAFFIC RULES:
- Distinguish normal waiting from genuine deadlock (corroborating blocked_ticks >= threshold and wait dependencies).
- Facing corridor / circular cycle: instruct ONE robot (`yield_robot`) to move/hold at a safe cell while the higher-priority robot (urgent deadline, critical battery, lower detour cost) passes cleanly. Do not command both robots into each other.
- Blocked route: reroute around congested/blocked cells or assign alternate path if valid; if `no_route_available` is true, DO NOT invent coordinates — use `escalate_to_human`.
- Never assume an aisle is clear without checking occupancy and conflicts in the brief.
- Never repeat identical failing actions (`failed_command_hints`). Never invent entity IDs not in the brief.

SUPPORTED EXECUTABLE COMMANDS (`command_type`):
- `yield_robot`: {"command_type": "yield_robot", "robot_id": "...", "yield_cell": {"x": int, "y": int} | null, "hold_ticks": int, "priority_robot_id": "...", "reason": "..."}
- `reroute_robot`: {"command_type": "reroute_robot", "robot_id": "...", "avoid_cells": [{"x": int, "y": int}], "reason": "..."}  (triggers human approval when avoid_cells is non-null)
- `send_to_charge`: {"command_type": "send_to_charge", "robot_id": "...", "charger_id": "..." | null, "reason": "..."}
- `assign_task`: {"command_type": "assign_task", "robot_id": "...", "order_id": "..." | null, "task_type": "PICK"|"MOVE", "destination": {"x": int, "y": int} | null, "reason": "..."}
- `reprioritise_order`: {"command_type": "reprioritise_order", "order_id": "...", "new_priority": 1..10, "reason": "..."}
- `batch_orders`: {"command_type": "batch_orders", "order_ids": ["..."], "target_station_id": "...", "reason": "..."}
- `reassign_task`: {"command_type": "reassign_task", "robot_id": "...", "target_robot_id": "..." | null, "reason": "..."}
- `set_station_policy`: {"command_type": "set_station_policy", "station_id": "...", "max_queue_depth": 1..20, "batch_window_sec": float, "reason": "..."}
- `hold_zone` / `release_zone`: {"command_type": "hold_zone"|"release_zone", "zone_id": "...", "duration_ticks": int, "reason": "..."}
- `escalate_to_human`: {"command_type": "escalate_to_human", "action_description": "...", "action_command": {...}, "severity": "INFO"|"WARN"|"CRITICAL", "reason": "..."}
- `no_action`: {"command_type": "no_action", "reason": "..."}

OUTPUT CONTRACT (STRICT JSON ONLY — NO prose outside JSON, NO chain-of-thought):
{
  "decision_id": "<short-id>",
  "situation_summary": "<concise 1-2 sentence operational diagnosis>",
  "priority": "low" | "normal" | "high" | "critical",
  "actions": [ <1 to 4 coherent validated command objects> ],
  "traffic_plan": {
    "conflict_detected": bool,
    "deadlock_detected": bool,
    "robots_affected": ["..."],
    "resolution": "<concise traffic plan>"
  },
  "requires_human_approval": bool,
  "confidence": 0.0..1.0,
  "unresolved_risks": ["..."],
  "expected_result": "<measurable outcome expected>"
}"""


def build_compact_context(
    brief: SituationBrief,
    specialists_proposals: list[DecisionProposal] | None = None,
) -> str:
    """Serialize SituationBrief and Specialist advisories compactly for small context windows."""
    payload: dict[str, Any] = {
        "tick": brief.tick,
        "trigger": brief.trigger,
        "kpis": brief.kpis.model_dump(),
        "battery_thresholds": brief.battery_thresholds,
    }

    if brief.deadlocks_detected:
        payload["deadlocks_detected"] = [d.model_dump(exclude_none=True) for d in brief.deadlocks_detected]
    if brief.at_risk_orders:
        payload["at_risk_orders"] = [o.model_dump(exclude_none=True) for o in brief.at_risk_orders[:6]]
    if brief.critical_robots:
        payload["critical_robots"] = [r.model_dump(exclude_none=True) for r in brief.critical_robots[:8]]
    if brief.robots_overview:
        # Include overview without duplicating critical_robots
        crit_ids = {r.robot_id for r in brief.critical_robots}
        overview = [r.model_dump(exclude_none=True) for r in brief.robots_overview if r.robot_id not in crit_ids]
        if overview:
            payload["other_robots"] = overview[:10]
    if brief.station_queues:
        payload["station_queues"] = [s.model_dump(exclude_none=True) for s in brief.station_queues]
    if brief.congested_cells:
        payload["congested_cells"] = [c.model_dump() for c in brief.congested_cells[:5]]
    if brief.active_alert_ids:
        payload["active_alert_ids"] = brief.active_alert_ids[:5]
    if brief.available_zones:
        payload["available_zones"] = brief.available_zones
    if brief.held_zone_ids:
        payload["held_zone_ids"] = brief.held_zone_ids
    if brief.available_chargers:
        payload["available_chargers"] = brief.available_chargers

    combined_proposals = list(brief.specialist_summary)
    if specialists_proposals:
        existing_keys = {(p.specialist, p.action, json.dumps(p.command, sort_keys=True)) for p in combined_proposals}
        for sp in specialists_proposals:
            k = (sp.specialist, sp.action, json.dumps(sp.command, sort_keys=True))
            if k not in existing_keys:
                combined_proposals.append(sp)
                existing_keys.add(k)
    if combined_proposals:
        payload["specialist_advisories"] = [
            {
                "specialist": p.specialist,
                "action": p.action,
                "confidence": p.confidence,
                "command": p.command,
                "rationale": p.rationale,
            }
            for p in combined_proposals[:8]
        ]

    if brief.recent_outcomes:
        payload["recent_outcomes"] = [
            {
                "tick": o.tick,
                "provider": o.provider,
                "commands": o.commands,
                "outcome": o.observed_outcome,
            }
            for o in brief.recent_outcomes[-3:]
        ]
    if brief.failed_command_hints:
        payload["avoid_repeating_failed_commands"] = brief.failed_command_hints[-5:]

    return json.dumps(payload, separators=(",", ":"))


def build_decision_messages(
    brief: SituationBrief,
    specialists_proposals: list[DecisionProposal] | None = None,
) -> list[dict[str, str]]:
    """Build standard system+user chat messages for LLM providers."""
    context_json = build_compact_context(brief, specialists_proposals)
    return [
        {"role": "system", "content": ROBOFLEET_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"LIVE_FLEET_STATE:\n{context_json}\n\n"
                "Analyze conflicts, deadlocks, battery safety, and order deadlines. "
                "Respond strictly with one valid JSON decision object matching the output contract."
            ),
        },
    ]
