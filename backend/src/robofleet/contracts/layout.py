"""Layout contracts for cells, zones, and world grid."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import Field

from robofleet.contracts.common import Coordinate, RoboFleetBaseModel


class CellType(str, Enum):
    WALL = "WALL"
    FLOOR = "FLOOR"
    SHELF = "SHELF"
    STATION = "STATION"
    PACK = "PACK"
    DISPATCH = "DISPATCH"
    SUPERVISOR_DESK = "SUPERVISOR_DESK"
    CHARGER = "CHARGER"
    PARKING = "PARKING"


class Flow(str, Enum):
    """Flow direction allowed on walkable cells."""

    BOTH = "BOTH"
    N = "N"
    E = "E"
    S = "S"
    W = "W"
    NS = "NS"
    EW = "EW"


class Cell(RoboFleetBaseModel):
    pos: Coordinate
    cell_type: CellType
    flow: Flow = Flow.BOTH
    zone: str | None = None
    level_count: int = Field(default=1, ge=1, description="Number of rack levels if SHELF")
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def is_walkable(self) -> bool:
        # Robots can traverse floor, station dock, charger, parking, and dispatch bays
        return self.cell_type in (
            CellType.FLOOR,
            CellType.CHARGER,
            CellType.PARKING,
            CellType.DISPATCH,
            CellType.STATION,
            CellType.PACK,
        )


class Zone(RoboFleetBaseModel):
    name: str
    description: str = ""
    top_left: Coordinate
    bottom_right: Coordinate
    restricted: bool = False


class Station(RoboFleetBaseModel):
    station_id: str
    pos: Coordinate
    queue_cells: list[Coordinate] = Field(default_factory=list)
    worker_count: int = 1
    worker_kind: str = "simulated_human"


class Charger(RoboFleetBaseModel):
    charger_id: str
    pos: Coordinate
    max_power_kw: float = 3.0


class Layout(RoboFleetBaseModel):
    name: str
    width: int = Field(ge=1, description="Grid width in cells")
    height: int = Field(ge=1, description="Grid height in cells")
    cell_size_m: float = Field(default=0.8, ge=0.1, description="Physical size of cell in metres")
    cells: list[Cell] = Field(default_factory=list)
    zones: list[Zone] = Field(default_factory=list)
    stations: list[Station] = Field(default_factory=list)
    chargers: list[Charger] = Field(default_factory=list)
    parking_cells: list[Coordinate] = Field(default_factory=list)
    dispatch_cells: list[Coordinate] = Field(default_factory=list)
    supervisor_cells: list[Coordinate] = Field(default_factory=list)
