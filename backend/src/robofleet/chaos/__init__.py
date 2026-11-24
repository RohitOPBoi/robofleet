"""RoboFleet Chaos Engineering, Failure Taxonomy, and Resilience Module (Phase 6)."""

from robofleet.chaos.engine import ChaosEngine
from robofleet.chaos.faults import BaseFault
from robofleet.chaos.recovery import SelfHealingManager
from robofleet.chaos.registry import FaultRegistry, fault_registry

__all__ = [
    "ChaosEngine",
    "BaseFault",
    "SelfHealingManager",
    "FaultRegistry",
    "fault_registry",
]
