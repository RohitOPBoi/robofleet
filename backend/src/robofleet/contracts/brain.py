"""AI Operations Brain Contracts (Phase 5).
Defines typed commands, situation briefs, specialist proposals, decision records,
approval requests, and supervisor natural language queries.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any, Literal

from pydantic import Field

from robofleet.contracts.commands import BaseCommand
from robofleet.contracts.common import Coordinate, RoboFleetBaseModel


# ---------------------------------------------------------------------------
# 1. Typed Brain Commands (The only way the AI acts)
# ---------------------------------------------------------------------------

class BrainBaseCommand(BaseCommand):
    expected_effect: str = Field(default="", description="Predictive operational impact statement")
    reason: str = Field(default="", description="Grounded operational rationale")


class AssignTaskCommand(BrainBaseCommand):
    command_type: Literal["assign_task"] = "assign_task"
    robot_id: str
    order_id: str | None = None
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task_type: Literal["PICK", "CHARGE", "STOW", "MOVE"] = "PICK"
    destination: Coordinate | None = None


class ReprioritiseOrderCommand(BrainBaseCommand):
    command_type: Literal["reprioritise_order"] = "reprioritise_order"
    order_id: str
    new_priority: int = Field(ge=1, le=10, description="Priority tier (10 = highest express)")


class BatchOrdersCommand(BrainBaseCommand):
    command_type: Literal["batch_orders"] = "batch_orders"
    order_ids: list[str] = Field(min_length=1)
    target_station_id: str


class RerouteRobotCommand(BrainBaseCommand):
    command_type: Literal["reroute_robot"] = "reroute_robot"
    robot_id: str
    avoid_cells: list[Coordinate] = Field(default_factory=list)


class SendToChargeCommand(BrainBaseCommand):
    command_type: Literal["send_to_charge"] = "send_to_charge"
    robot_id: str
    charger_id: str | None = None


class YieldRobotCommand(BrainBaseCommand):
    command_type: Literal["yield_robot"] = "yield_robot"
    robot_id: str
    yield_cell: Coordinate | None = None
    hold_ticks: int = Field(default=15, ge=1, le=200)
    priority_robot_id: str | None = None


class ReassignTaskCommand(BrainBaseCommand):
    command_type: Literal["reassign_task"] = "reassign_task"
    robot_id: str
    target_robot_id: str | None = None
    order_id: str | None = None


class SubstituteItemCommand(BrainBaseCommand):
    command_type: Literal["substitute_item"] = "substitute_item"
    order_id: str
    sku_id: str
    quantity: int = Field(default=1, ge=1, le=100)


class RerouteStationCommand(BrainBaseCommand):
    command_type: Literal["reroute_station"] = "reroute_station"
    station_id: str


class ClearFaultBrainCommand(BrainBaseCommand):
    command_type: Literal["clear_fault"] = "clear_fault"
    target_id: str


class HoldZoneCommand(BrainBaseCommand):
    command_type: Literal["hold_zone"] = "hold_zone"
    zone_id: str
    duration_ticks: int = Field(default=300, ge=1)


class ReleaseZoneCommand(BrainBaseCommand):
    command_type: Literal["release_zone"] = "release_zone"
    zone_id: str


class SetStationPolicyCommand(BrainBaseCommand):
    command_type: Literal["set_station_policy"] = "set_station_policy"
    station_id: str
    max_queue_depth: int = Field(default=6, ge=1, le=20)
    batch_window_sec: float = Field(default=30.0, ge=0.0)


class SetStrategyParamsCommand(BrainBaseCommand):
    command_type: Literal["set_strategy_params"] = "set_strategy_params"
    strategy_name: str
    params: dict[str, Any] = Field(default_factory=dict)


class EscalateToHumanCommand(BrainBaseCommand):
    command_type: Literal["escalate_to_human"] = "escalate_to_human"
    action_description: str
    action_command: dict[str, Any] = Field(default_factory=dict)
    severity: Literal["INFO", "WARN", "CRITICAL"] = "WARN"
    timeout_ticks: int = Field(default=50, ge=10)
    default_action: Literal["deny", "approve_safe_alternative"] = "deny"


class NoActionCommand(BrainBaseCommand):
    command_type: Literal["no_action"] = "no_action"


type BrainCommandUnion = (
    AssignTaskCommand
    | ReprioritiseOrderCommand
    | BatchOrdersCommand
    | RerouteRobotCommand
    | SendToChargeCommand
    | YieldRobotCommand
    | ReassignTaskCommand
    | SubstituteItemCommand
    | RerouteStationCommand
    | ClearFaultBrainCommand
    | HoldZoneCommand
    | ReleaseZoneCommand
    | SetStationPolicyCommand
    | SetStrategyParamsCommand
    | EscalateToHumanCommand
    | NoActionCommand
)


COMMAND_TYPE_MODELS: dict[str, type[BrainBaseCommand]] = {
    "assign_task": AssignTaskCommand,
    "reprioritise_order": ReprioritiseOrderCommand,
    "batch_orders": BatchOrdersCommand,
    "reroute_robot": RerouteRobotCommand,
    "send_to_charge": SendToChargeCommand,
    "yield_robot": YieldRobotCommand,
    "reassign_task": ReassignTaskCommand,
    "substitute_item": SubstituteItemCommand,
    "reroute_station": RerouteStationCommand,
    "clear_fault": ClearFaultBrainCommand,
    "hold_zone": HoldZoneCommand,
    "release_zone": ReleaseZoneCommand,
    "set_station_policy": SetStationPolicyCommand,
    "set_strategy_params": SetStrategyParamsCommand,
    "escalate_to_human": EscalateToHumanCommand,
    "no_action": NoActionCommand,
}


def validate_brain_command(raw_cmd: dict[str, Any]) -> BrainBaseCommand:
    """Strictly validate an arbitrary dict against known typed Brain commands."""
    if not isinstance(raw_cmd, dict):
        raise ValueError("Command must be a JSON object")
    cmd_type = raw_cmd.get("command_type")
    if not isinstance(cmd_type, str) or cmd_type not in COMMAND_TYPE_MODELS:
        raise ValueError(f"Unsupported or missing command_type: {cmd_type!r}")
    model_cls = COMMAND_TYPE_MODELS[cmd_type]
    return model_cls.model_validate(raw_cmd)


# ---------------------------------------------------------------------------
# 2. Situation Brief (Bounded, deterministic state summary)
# ---------------------------------------------------------------------------

class BriefKPIs(RoboFleetBaseModel):
    queue_depth: int = 0
    throughput_per_hr: float = 0.0
    at_risk_count: int = 0
    active_alerts_count: int = 0
    robots_moving: int = 0
    robots_idle: int = 0
    robots_charging: int = 0
    fleet_utilization_pct: float = 0.0
    avg_waiting_ticks: float = 0.0
    active_deadlocks_count: int = 0


class BriefOrderSummary(RoboFleetBaseModel):
    order_id: str
    lines_count: int
    sla_remaining_ticks: int
    priority: int
    assigned_robot_id: str | None = None
    state: str


class BriefStationQueue(RoboFleetBaseModel):
    station_id: str
    queue_length: int
    active_robot_id: str | None = None
    avg_service_time_ticks: float = 30.0
    is_active: bool = True


class BriefRobotSummary(RoboFleetBaseModel):
    robot_id: str
    state: str
    battery_percent: float
    current_coord: Coordinate
    current_task_type: str | None = None
    carrying_tote: bool = False
    destination: Coordinate | None = None
    blocked_ticks: int = 0
    waiting_for_robot_id: str | None = None
    nearest_charger_distance: int | None = None
    has_valid_route: bool = True
    fault: str | None = None


class BriefDeadlockInfo(RoboFleetBaseModel):
    conflict_id: str
    conflict_type: Literal[
        "facing_corridor",
        "intersection_conflict",
        "circular_deadlock",
        "blocked_route",
        "stuck_no_route",
    ]
    robots_involved: list[str] = Field(default_factory=list)
    cycle_chain: list[str] = Field(default_factory=list)
    conflict_cells: list[Coordinate] = Field(default_factory=list)
    recommended_yield_robot: str | None = None
    recommended_yield_cell: Coordinate | None = None
    recommended_priority_robot: str | None = None
    no_route_available: bool = False
    max_blocked_ticks: int = 0
    description: str = ""


class BriefOutcomeSummary(RoboFleetBaseModel):
    decision_id: str
    tick: int
    provider: str
    commands: list[str] = Field(default_factory=list)
    observed_outcome: str = "unknown"
    summary: str = ""


class SituationBrief(RoboFleetBaseModel):
    tick: int
    trigger: str
    kpis: BriefKPIs
    at_risk_orders: list[BriefOrderSummary] = Field(default_factory=list)
    station_queues: list[BriefStationQueue] = Field(default_factory=list)
    critical_robots: list[BriefRobotSummary] = Field(default_factory=list)
    robots_overview: list[BriefRobotSummary] = Field(default_factory=list)
    congested_cells: list[Coordinate] = Field(default_factory=list)
    deadlocks_detected: list[BriefDeadlockInfo] = Field(default_factory=list)
    active_alert_ids: list[str] = Field(default_factory=list)
    held_zone_ids: list[str] = Field(default_factory=list)
    available_zones: list[str] = Field(default_factory=list)
    available_chargers: list[str] = Field(default_factory=list)
    recent_decision_ids: list[str] = Field(default_factory=list)
    recent_outcomes: list[BriefOutcomeSummary] = Field(default_factory=list)
    failed_command_hints: list[str] = Field(default_factory=list)
    specialist_summary: list[DecisionProposal] = Field(default_factory=list)
    battery_thresholds: dict[str, float] = Field(default_factory=dict)
    brief_hash: str = ""

    def compute_hash(self) -> str:
        """Deterministic SHA256 content hash."""
        dumped = self.model_dump(exclude={"brief_hash"})
        serialized = json.dumps(dumped, sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# 3. Specialist Proposals & Unified Decision Record
# ---------------------------------------------------------------------------

class DecisionProposal(RoboFleetBaseModel):
    specialist: Literal["planner", "traffic", "exceptions", "explainer", "human", "orchestrator"]
    action: str
    command: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    rationale: str = ""


class Decision(RoboFleetBaseModel):
    decision_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    tick: int = Field(ge=0)
    trigger: str
    brief_hash: str
    proposals: list[DecisionProposal] = Field(default_factory=list)
    final_commands: list[dict[str, Any]] = Field(default_factory=list)
    rejected_commands: list[dict[str, Any]] = Field(default_factory=list)
    governance_outcome: Literal["approved", "require_human", "denied"] = "approved"
    execution_result: Literal["success", "partial", "failed", "rejected_by_safety"] = "success"
    observed_outcome: Literal["improved", "neutral", "worsened", "unknown"] = "unknown"
    latency_ms: float = 0.0
    token_usage: dict[str, int] = Field(default_factory=dict)
    cost_usd: float = 0.0
    operating_mode: Literal["heuristic", "ai", "local_llm", "replay"] = "heuristic"
    provider_mode: Literal[
        "heuristic", "ai", "local_llm", "replay", "anthropic", "heuristic_fallback"
    ] = "heuristic"
    provider_name: str = "Heuristic"
    model_name: str = ""
    fallback_used: bool = False
    fallback_reason: str = ""
    attribution: str = ""
    situation_summary: str = ""
    traffic_plan: dict[str, Any] = Field(default_factory=dict)
    unresolved_risks: list[str] = Field(default_factory=list)
    confidence: float = 1.0
    outcome_metrics: dict[str, Any] = Field(default_factory=dict)
    decision_version: int = 0
    rationale: str = ""


# ---------------------------------------------------------------------------
# 4. Approvals Queue (Human-in-the-loop Governance)
# ---------------------------------------------------------------------------

class ApprovalRequest(RoboFleetBaseModel):
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    decision_id: str
    command: dict[str, Any]
    timeout_tick: int
    default_action: Literal["deny", "approve_safe_alternative"] = "deny"
    created_tick: int
    status: Literal["pending", "approved", "rejected", "timed_out"] = "pending"
    reason: str = ""


# ---------------------------------------------------------------------------
# 5. Natural Language Supervisor Interaction
# ---------------------------------------------------------------------------

class SupervisorQuery(RoboFleetBaseModel):
    query_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    tick: int
    raw_text: str
    query_type: Literal["command", "question", "clarification_needed"] = "command"
    parsed_command: dict[str, Any] | None = None
    requires_confirmation: bool = False
    clarification_prompt: str | None = None
    response_text: str = ""
    evidence_citations: list[str] = Field(default_factory=list)
