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
    | HoldZoneCommand
    | ReleaseZoneCommand
    | SetStationPolicyCommand
    | SetStrategyParamsCommand
    | EscalateToHumanCommand
    | NoActionCommand
)


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


class BriefRobotSummary(RoboFleetBaseModel):
    robot_id: str
    state: str
    battery_percent: float
    current_coord: Coordinate
    current_task_type: str | None = None
    carrying_tote: bool = False


class SituationBrief(RoboFleetBaseModel):
    tick: int
    trigger: str
    kpis: BriefKPIs
    at_risk_orders: list[BriefOrderSummary] = Field(default_factory=list)
    station_queues: list[BriefStationQueue] = Field(default_factory=list)
    critical_robots: list[BriefRobotSummary] = Field(default_factory=list)
    congested_cells: list[Coordinate] = Field(default_factory=list)
    active_alert_ids: list[str] = Field(default_factory=list)
    held_zone_ids: list[str] = Field(default_factory=list)
    recent_decision_ids: list[str] = Field(default_factory=list)
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
    specialist: Literal["planner", "traffic", "exceptions", "explainer", "human"]
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
    governance_outcome: Literal["approved", "require_human", "denied"] = "approved"
    execution_result: Literal["success", "partial", "failed", "rejected_by_safety"] = "success"
    observed_outcome: Literal["improved", "neutral", "worsened", "unknown"] = "unknown"
    latency_ms: float = 0.0
    token_usage: dict[str, int] = Field(default_factory=dict)
    cost_usd: float = 0.0
    provider_mode: Literal["anthropic", "heuristic", "replay"] = "heuristic"
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
