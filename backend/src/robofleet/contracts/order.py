"""Order, order lines, and task lifecycle contracts."""

from __future__ import annotations

from enum import Enum

from pydantic import Field

from robofleet.contracts.common import Coordinate, RoboFleetBaseModel


class OrderStatus(str, Enum):
    RECEIVED = "RECEIVED"
    QUEUED = "QUEUED"
    PLANNED = "PLANNED"
    RETRIEVING = "RETRIEVING"
    AT_STATION = "AT_STATION"
    PICKING = "PICKING"
    CONSOLIDATING = "CONSOLIDATING"
    PACKED = "PACKED"
    READY_FOR_DISPATCH = "READY_FOR_DISPATCH"
    HANDED_OVER = "HANDED_OVER"
    # Terminal exception states
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"
    FAILED_PARTIAL = "FAILED_PARTIAL"


class OrderLine(RoboFleetBaseModel):
    sku_id: str
    quantity: int = Field(ge=1)
    picked_quantity: int = Field(default=0, ge=0)
    status: str = "PENDING"  # PENDING, PICKED, SHORT, DAMAGED


class DelayAttribution(RoboFleetBaseModel):
    """WareMax delay attribution model (P3-A8).
    Attributes delay to specific fulfillment stages so the sum matches total lateness.
    """

    waiting_for_robot_ticks: int = 0
    travel_ticks: int = 0
    station_queue_ticks: int = 0
    picking_ticks: int = 0
    consolidation_ticks: int = 0
    supervisor_handoff_ticks: int = 0
    total_lateness_ticks: int = 0


class Order(RoboFleetBaseModel):
    order_id: str
    lines: list[OrderLine] = Field(default_factory=list)
    status: OrderStatus = OrderStatus.RECEIVED
    priority: int = Field(default=1, ge=1, le=10)
    created_tick: int = Field(ge=0)
    deadline_tick: int = Field(ge=0)
    at_risk: bool = False
    assigned_station_id: str | None = None
    sla_tier: str = "standard"  # standard, express, scheduled
    tote_id: str | None = None
    ready_tick: int | None = None
    handover_tick: int | None = None
    assigned_robot_ids: list[str] = Field(default_factory=list)
    delay_attribution: DelayAttribution | None = None


class TaskType(str, Enum):
    FETCH_BIN = "FETCH_BIN"
    DELIVER_TO_STATION = "DELIVER_TO_STATION"
    RETURN_BIN = "RETURN_BIN"
    CARRY_ORDER_TOTE = "CARRY_ORDER_TOTE"
    CHARGE = "CHARGE"
    PARK = "PARK"
    WANDER = "WANDER"  # Placeholder dispatcher task


class TaskState(str, Enum):
    PENDING = "PENDING"
    ASSIGNED = "ASSIGNED"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class Task(RoboFleetBaseModel):
    task_id: str
    task_type: TaskType
    state: TaskState = TaskState.PENDING
    target_cell: Coordinate
    robot_id: str | None = None
    order_ids: list[str] = Field(default_factory=list)
    bin_id: str | None = None
    sku_id: str | None = None
    quantity: int = 1
    station_id: str | None = None
    dwell_ticks: int = Field(default=0, ge=0)
    created_tick: int = Field(ge=0)
    deadline_tick: int | None = None
