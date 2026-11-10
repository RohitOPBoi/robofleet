"""World snapshot contracts: StaticWorld, DynamicState, WorldSnapshot."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from robofleet.contracts.alert import Alert
from robofleet.contracts.catalogue import Bin, Sku
from robofleet.contracts.common import Coordinate, EnvironmentMeta, RoboFleetBaseModel
from robofleet.contracts.layout import Layout
from robofleet.contracts.order import Order
from robofleet.contracts.robot import Robot


class StaticWorld(RoboFleetBaseModel):
    """Static world state transmitted once or on full reload."""

    meta: EnvironmentMeta = Field(default_factory=EnvironmentMeta)
    layout: Layout
    catalogue: list[Sku] = Field(default_factory=list)
    bins: list[Bin] = Field(default_factory=list)
    config_summary: dict[str, Any] = Field(default_factory=dict)


class DynamicState(RoboFleetBaseModel):
    """Dynamic world state updated every tick or delta."""

    meta: EnvironmentMeta = Field(default_factory=EnvironmentMeta)
    tick: int = Field(ge=0, description="Current discrete simulation tick")
    sim_time_ms: int = Field(ge=0, description="Current simulation time in ms")
    seq: int = Field(ge=0, description="Highest emitted event sequence number")
    robots: list[Robot] = Field(default_factory=list)
    orders: list[Order] = Field(default_factory=list)
    alerts: list[Alert] = Field(default_factory=list)
    blocked_cells: list[Coordinate] = Field(default_factory=list)
    kpis: dict[str, float] = Field(default_factory=dict)


class WorldSnapshot(RoboFleetBaseModel):
    """Combined static world and dynamic state."""

    meta: EnvironmentMeta = Field(default_factory=EnvironmentMeta)
    static: StaticWorld
    dynamic: DynamicState
