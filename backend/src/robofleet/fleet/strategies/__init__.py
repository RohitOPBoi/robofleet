"""Fleet fulfillment strategies package (CA-5)."""

from __future__ import annotations

from robofleet.fleet.strategies.base import FulfilmentStrategy
from robofleet.fleet.strategies.batch_greedy import BatchGreedyStrategy
from robofleet.fleet.strategies.edf_deadline import EDFDeadlineStrategy
from robofleet.fleet.strategies.fcfs_nearest import FCFSNearestStrategy
from robofleet.fleet.strategies.random_strategy import RandomStrategy
from robofleet.registry.generic import dispatcher_registry, strategy_registry

# Register baseline fulfillment strategies into CA-5 registries
strategy_registry.register("fcfs_nearest", FCFSNearestStrategy)
strategy_registry.register("edf_deadline", EDFDeadlineStrategy)
strategy_registry.register("batch_greedy", BatchGreedyStrategy)
strategy_registry.register("random", RandomStrategy)

dispatcher_registry.register("fcfs_nearest", FCFSNearestStrategy)
dispatcher_registry.register("edf_deadline", EDFDeadlineStrategy)
dispatcher_registry.register("batch_greedy", BatchGreedyStrategy)
dispatcher_registry.register("random", RandomStrategy)

__all__ = [
    "FulfilmentStrategy",
    "FCFSNearestStrategy",
    "EDFDeadlineStrategy",
    "BatchGreedyStrategy",
    "RandomStrategy",
]
