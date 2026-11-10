"""Append-only simulation events contract."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from robofleet.contracts.common import RoboFleetBaseModel


class Event(RoboFleetBaseModel):
    seq: int = Field(ge=0, description="Strictly increasing sequential event index")
    tick: int = Field(ge=0, description="Simulation discrete integer tick")
    sim_time_ms: int = Field(ge=0, description="Derived simulation time in milliseconds")
    event_type: str = Field(description="Dotted event type string, e.g. sim.started, robot.arrived")
    payload: dict[str, Any] = Field(default_factory=dict, description="Event payload dictionary")
