"""Declared change axes (CA-1 to CA-9) extension protocols.
No speculative abstractions: each protocol maps directly to a declared change axis.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Protocol, runtime_checkable

from robofleet.contracts.catalogue import Sku
from robofleet.contracts.common import Coordinate
from robofleet.contracts.events import Event
from robofleet.contracts.layout import Layout
from robofleet.contracts.order import Order, Task
from robofleet.contracts.robot import Robot


# CA-1: World Layout
@runtime_checkable
class WorldGenerator(Protocol):
    def generate(self) -> Layout: ...


# CA-2: Catalogue Source
@runtime_checkable
class CatalogueSource(Protocol):
    def load(self) -> list[Sku]: ...


# CA-2: Order Source
@runtime_checkable
class OrderSource(Protocol):
    def poll_orders(self, current_tick: int) -> list[Order]: ...


# CA-5: Movement Planner
@runtime_checkable
class MovementPlanner(Protocol):
    def plan_next_step(
        self,
        robot: Robot,
        target: Coordinate,
        layout: Layout,
        reserved_cells: set[Coordinate],
    ) -> Coordinate | None: ...


# CA-5: Task Dispatcher
@runtime_checkable
class TaskDispatcher(Protocol):
    def dispatch(
        self,
        idle_robots: list[Robot],
        pending_tasks: list[Task],
        layout: Layout,
        current_tick: int,
    ) -> list[tuple[str, str]]:  # list of (robot_id, task_id)
        ...


# CA-3: Constraint
@runtime_checkable
class Constraint(Protocol):
    def validate(self, context: dict[str, Any]) -> tuple[bool, str | None]: ...


# CA-7: Metric Provider
@runtime_checkable
class MetricProvider(Protocol):
    def compute(self, events: Sequence[Event], state: Any) -> dict[str, float]: ...


# CA-8: Fault Injector
@runtime_checkable
class FaultInjector(Protocol):
    def check_and_inject(self, current_tick: int) -> list[dict[str, Any]]: ...


# CA-6: Brain
@runtime_checkable
class Brain(Protocol):
    def step(self, current_tick: int, situation_brief: dict[str, Any]) -> list[dict[str, Any]]: ...


# Event Sink
@runtime_checkable
class EventSink(Protocol):
    def emit(self, event: Event) -> None: ...
