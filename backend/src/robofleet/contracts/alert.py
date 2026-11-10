"""System alerts contract."""

from __future__ import annotations

from enum import Enum

from pydantic import Field

from robofleet.contracts.common import Coordinate, RoboFleetBaseModel


class AlertSeverity(str, Enum):
    INFO = "INFO"
    WARN = "WARN"
    CRITICAL = "CRITICAL"


class AlertCategory(str, Enum):
    SAFETY = "SAFETY"
    BATTERY = "BATTERY"
    DEADLOCK = "DEADLOCK"
    ROBOT = "ROBOT"
    ORDER = "ORDER"
    STATION = "STATION"
    INVENTORY = "INVENTORY"


class Alert(RoboFleetBaseModel):
    alert_id: str
    severity: AlertSeverity
    category: AlertCategory
    message: str
    entity_ids: list[str] = Field(default_factory=list)
    cell: Coordinate | None = None
    raised_tick: int = Field(ge=0)
    resolved_tick: int | None = None
    requires_human: bool = False
    auto_resolved: bool = True
