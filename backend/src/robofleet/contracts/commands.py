"""Simulation and supervisor commands contract."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from robofleet.contracts.common import Coordinate, RoboFleetBaseModel


class BaseCommand(RoboFleetBaseModel):
    command_id: str
    command_type: str
    issued_tick: int = Field(default=0, ge=0)
    reason: str = ""


class EmergencyStopCommand(BaseCommand):
    command_type: Literal["emergency_stop"] = "emergency_stop"
    scope: Literal["all", "robot", "zone"] = "all"
    target_id: str | None = None


class ResumeCommand(BaseCommand):
    command_type: Literal["resume"] = "resume"
    scope: Literal["all", "robot", "zone"] = "all"
    target_id: str | None = None


class BlockCellsCommand(BaseCommand):
    command_type: Literal["block_cells"] = "block_cells"
    cells: list[Coordinate] = Field(default_factory=list)


class UnblockCellsCommand(BaseCommand):
    command_type: Literal["unblock_cells"] = "unblock_cells"
    cells: list[Coordinate] = Field(default_factory=list)


class InjectFaultCommand(BaseCommand):
    command_type: Literal["inject_fault"] = "inject_fault"
    fault_type: str
    target_id: str
    duration_ticks: int = 100


class ClearFaultCommand(BaseCommand):
    command_type: Literal["clear_fault"] = "clear_fault"
    target_id: str


# Union of all supported commands in Phase 1
type CommandUnion = (
    EmergencyStopCommand
    | ResumeCommand
    | BlockCellsCommand
    | UnblockCellsCommand
    | InjectFaultCommand
    | ClearFaultCommand
)
