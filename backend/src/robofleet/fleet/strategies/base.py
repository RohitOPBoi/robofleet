"""Base Protocol and Contracts for Fleet Fulfilment Strategies (CA-5)."""

from __future__ import annotations

from typing import Any, Protocol
import numpy as np

from robofleet.contracts.catalogue import Bin, Sku
from robofleet.contracts.common import Coordinate
from robofleet.contracts.layout import Layout
from robofleet.contracts.order import Order
from robofleet.contracts.robot import Robot
from robofleet.fleet.station import PickingStationManager
from robofleet.fleet.task_manager import TaskManager


class FulfilmentStrategy(Protocol):
    """Protocol for pluggable fleet dispatch and fulfillment strategies."""

    name: str

    def dispatch(
        self,
        orders: list[Order],
        robots: list[Robot],
        layout: Layout,
        bins: dict[str, Bin],
        skus: dict[str, Sku],
        task_mgr: TaskManager,
        station_mgr: PickingStationManager,
        current_tick: int,
        rng: np.random.Generator,
    ) -> dict[str, Coordinate]:
        """Plans destinations for robots to progress orders through fulfillment lifecycle."""
        ...
