"""Order source adapters and factory registrations (CA-2)."""

from robofleet.adapters.csv_replay import CsvReplayOrderSource
from robofleet.adapters.demand_engine import SyntheticDemandEngine
from robofleet.adapters.webhook import WebhookOrderSource
from robofleet.registry.generic import order_source_registry

# Register order source adapters in declared seam registry
order_source_registry.register("demand_engine", SyntheticDemandEngine)
order_source_registry.register("csv_replay", CsvReplayOrderSource)
order_source_registry.register("webhook", WebhookOrderSource)

__all__ = [
    "SyntheticDemandEngine",
    "CsvReplayOrderSource",
    "WebhookOrderSource",
]
