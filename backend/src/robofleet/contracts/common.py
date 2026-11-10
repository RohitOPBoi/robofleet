"""Common types, environment metadata, and base models for RoboFleet contracts."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION: str = "1.0.0"


class RoboFleetBaseModel(BaseModel):
    """Base model enforcing contract conventions: ignore unknown fields, allow ext."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)
    ext: dict[str, Any] = Field(
        default_factory=dict, description="Extension dictionary for backward compatibility"
    )


class EnvironmentMeta(BaseModel):
    """Environment metadata surface required on all top-level payloads."""

    mode: str = Field(default="digital_twin", description="Operating mode, e.g. digital_twin")
    data_source: str = Field(
        default="Synthetic Demand Engine", description="Source of demand/order data"
    )
    robot_layer: str = Field(
        default="simulated", description="Underlying robot layer, e.g. simulated"
    )
    schema_version: str = Field(default=SCHEMA_VERSION, description="SemVer schema version")


class Coordinate(BaseModel):
    """2D grid coordinates (x East, y South)."""

    x: int = Field(ge=0, description="Column index (East)")
    y: int = Field(ge=0, description="Row index (South)")

    def as_tuple(self) -> tuple[int, int]:
        return (self.x, self.y)

    def manhattan_distance(self, other: Coordinate) -> int:
        return abs(self.x - other.x) + abs(self.y - other.y)


class Heading(str, Enum):
    """Grid orientation. N is y-1 (North), S is y+1 (South), E is x+1 (East), W is x-1 (West)."""

    N = "N"
    E = "E"
    S = "S"
    W = "W"

    @property
    def delta(self) -> tuple[int, int]:
        match self:
            case Heading.N:
                return (0, -1)
            case Heading.E:
                return (1, 0)
            case Heading.S:
                return (0, 1)
            case Heading.W:
                return (-1, 0)
