"""RoboFleet contracts package."""

from robofleet.contracts.alert import Alert, AlertCategory, AlertSeverity
from robofleet.contracts.catalogue import Bin, HazardClass, Sku, TemperatureClass
from robofleet.contracts.commands import (
    BlockCellsCommand,
    ClearFaultCommand,
    CommandUnion,
    EmergencyStopCommand,
    InjectFaultCommand,
    ResumeCommand,
    UnblockCellsCommand,
)
from robofleet.contracts.common import (
    SCHEMA_VERSION,
    Coordinate,
    EnvironmentMeta,
    Heading,
    RoboFleetBaseModel,
)
from robofleet.contracts.decision import Decision, DecisionProposal
from robofleet.contracts.events import Event
from robofleet.contracts.layout import Cell, CellType, Charger, Flow, Layout, Station, Zone
from robofleet.contracts.migrations import migrate, register_migration
from robofleet.contracts.order import Order, OrderLine, OrderStatus, Task, TaskState, TaskType
from robofleet.contracts.robot import MotionProgress, Robot, RobotState
from robofleet.contracts.state import DynamicState, StaticWorld, WorldSnapshot

__all__ = [
    "SCHEMA_VERSION",
    "Alert",
    "AlertCategory",
    "AlertSeverity",
    "Bin",
    "BlockCellsCommand",
    "Cell",
    "CellType",
    "Charger",
    "ClearFaultCommand",
    "CommandUnion",
    "Coordinate",
    "Decision",
    "DecisionProposal",
    "DynamicState",
    "EmergencyStopCommand",
    "EnvironmentMeta",
    "Event",
    "Flow",
    "HazardClass",
    "Heading",
    "InjectFaultCommand",
    "Layout",
    "MotionProgress",
    "Order",
    "OrderLine",
    "OrderStatus",
    "ResumeCommand",
    "RoboFleetBaseModel",
    "Robot",
    "RobotState",
    "Sku",
    "StaticWorld",
    "Station",
    "Task",
    "TaskState",
    "TaskType",
    "TemperatureClass",
    "UnblockCellsCommand",
    "WorldSnapshot",
    "Zone",
    "migrate",
    "register_migration",
]
