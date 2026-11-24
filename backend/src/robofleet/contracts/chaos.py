"""Chaos, Resilience, Verification and Audit Contracts (Phase 6).
Defines typed schemas for failure taxonomy, pick verification outcomes,
degraded modes, supervisor exceptions, audit entries, and re-slotting recommendations.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal
import uuid

from pydantic import Field

from robofleet.contracts.common import Coordinate, RoboFleetBaseModel


class PickOutcome(str, Enum):
    COMMANDED = "COMMANDED"
    VERIFIED = "VERIFIED"
    MISMATCH = "MISMATCH"
    UNVERIFIED = "UNVERIFIED"


class FaultType(str, Enum):
    ROBOT_BREAKDOWN = "robot_breakdown"
    ROBOT_COMMS_DROP = "robot_comms_drop"
    BATTERY_CASCADE = "battery_cascade"
    AISLE_BLOCKED = "aisle_blocked"
    BIN_MISSING_STOCK = "bin_missing_stock"
    ITEM_DAMAGED = "item_damaged"
    STATION_SLOWDOWN = "station_slowdown"
    STATION_OFFLINE = "station_offline"
    URGENT_ORDER_BURST = "urgent_order_burst"
    SUPERVISOR_UNAVAILABLE = "supervisor_unavailable"


class ChaosFault(RoboFleetBaseModel):
    fault_id: str = Field(default_factory=lambda: f"FLT-{uuid.uuid4().hex[:6]}")
    fault_type: str
    target_id: str
    target_type: Literal["robot", "aisle", "station", "bin", "fleet", "system"] = "robot"
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] = "MEDIUM"
    injected_tick: int = 0
    duration_ticks: int = 200
    resolved_tick: int | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    degraded_mode_name: str = ""
    is_active: bool = True


class DegradedMode(RoboFleetBaseModel):
    mode_id: str = Field(default_factory=lambda: f"DEG-{uuid.uuid4().hex[:6]}")
    fault_id: str
    name: str
    description: str
    active_since_tick: int
    resolved_tick: int | None = None


class ExceptionItem(RoboFleetBaseModel):
    exception_id: str = Field(default_factory=lambda: f"EXC-{uuid.uuid4().hex[:6]}")
    exception_type: str  # damaged_item, physical_tote_recovery, stockout_shortage, robot_breakdown
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] = "HIGH"
    entity_id: str
    location: Coordinate | None = None
    raised_tick: int
    deadline_tick: int
    timeout_ticks: int = 300
    default_action: str
    recommended_action: str
    available_actions: list[str] = Field(default_factory=list)
    status: Literal["PENDING", "RESOLVED", "TIMED_OUT"] = "PENDING"
    resolved_by: str | None = None
    resolved_action: str | None = None
    resolved_tick: int | None = None


class AuditEntry(RoboFleetBaseModel):
    audit_id: str = Field(default_factory=lambda: f"AUD-{uuid.uuid4().hex[:8]}")
    timestamp_iso: str
    tick: int
    actor: str
    role: Literal["viewer", "supervisor", "admin"]
    action: str
    entity_type: str
    entity_id: str
    before_state: dict[str, Any] = Field(default_factory=dict)
    after_state: dict[str, Any] = Field(default_factory=dict)
    reason: str
    result: Literal["SUCCESS", "REJECTED", "FAILED"]
    rejection_reason: str | None = None


class ReslotRecommendation(RoboFleetBaseModel):
    recommendation_id: str = Field(default_factory=lambda: f"REC-{uuid.uuid4().hex[:6]}")
    sku_id: str
    current_bin_id: str
    recommended_bin_id: str
    velocity_score: float
    travel_distance_reduction: float
    congestion_proxy_delta: float
    status: Literal["RECOMMENDED", "APPROVED", "REJECTED"] = "RECOMMENDED"
    reason: str
