"""Catalogue, SKU, and inventory bin contracts."""

from __future__ import annotations

from enum import Enum

from pydantic import Field

from robofleet.contracts.common import Coordinate, RoboFleetBaseModel


class TemperatureClass(str, Enum):
    AMBIENT = "ambient"
    CHILLED = "chilled"
    FROZEN = "frozen"


class HazardClass(str, Enum):
    NONE = "none"
    CHEMICAL = "chemical"
    FLAMMABLE = "flammable"


class Sku(RoboFleetBaseModel):
    sku_id: str
    name: str
    category: str
    pack_size: str
    mrp_inr: float = Field(ge=0.0)
    popularity_rank: int = Field(ge=1)
    size_class: str = "medium"  # small, medium, large
    fragile: bool = False
    handling_difficulty: float = Field(default=1.0, ge=0.5, le=5.0)
    unit_weight_g: int = Field(ge=1)
    dimensions_mm: list[int] = Field(default_factory=lambda: [100, 100, 100])
    temperature_class: TemperatureClass = TemperatureClass.AMBIENT
    shelf_life_days: int = Field(default=180, ge=1)
    hazard_class: HazardClass = HazardClass.NONE


class Bin(RoboFleetBaseModel):
    bin_id: str
    cell: Coordinate
    level: int = Field(ge=1, description="Rack shelf level (1 = bottom)")
    sku_id: str | None = None
    quantity: int = Field(default=0, ge=0)
    capacity: int = Field(default=50, ge=1)
    max_weight_g: int = Field(default=25000, ge=1000)
