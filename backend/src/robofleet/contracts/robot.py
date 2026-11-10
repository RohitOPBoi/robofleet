"""Robot status, physics, and kinematic state contracts."""

from __future__ import annotations

from enum import Enum

from pydantic import Field

from robofleet.contracts.common import Coordinate, Heading, RoboFleetBaseModel


class RobotState(str, Enum):
    IDLE = "IDLE"
    MOVING = "MOVING"
    WAITING = "WAITING"
    CHARGING = "CHARGING"
    UNAVAILABLE = "UNAVAILABLE"
    # Reserved for future phases
    PICKING = "PICKING"
    MAINTENANCE = "MAINTENANCE"


class MotionProgress(RoboFleetBaseModel):
    from_cell: Coordinate
    to_cell: Coordinate
    progress_permille: int = Field(
        ge=0, le=1000, description="Movement progress in permille (0 to 1000)"
    )


class Robot(RoboFleetBaseModel):
    robot_id: str
    kind: str = "standard_amr"
    cell: Coordinate
    heading: Heading = Heading.N
    state: RobotState = RobotState.IDLE
    battery_pct: float = Field(default=100.0, ge=0.0, le=100.0)
    motion: MotionProgress | None = None
    current_task_id: str | None = None
    carrying: list[str] = Field(default_factory=list, description="IDs of totes/items carried")
    blocked_ticks: int = Field(default=0, ge=0)
    fault: str | None = None
