"""Simulation clock. Discrete integer ticks only.
Never reads the real wall clock inside the simulation core (SR-5, P1-R3).
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class SimClock(BaseModel):
    tick: int = Field(default=0, ge=0)
    tick_hz: int = Field(default=10, ge=1)

    @property
    def sim_time_ms(self) -> int:
        return (self.tick * 1000) // self.tick_hz

    @property
    def sim_time_s(self) -> float:
        return self.tick / float(self.tick_hz)

    def advance(self) -> int:
        self.tick += 1
        return self.tick

    def reset(self) -> None:
        self.tick = 0
