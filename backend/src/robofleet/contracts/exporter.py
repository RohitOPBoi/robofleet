"""Tool to export JSON Schemas and sample payloads to contracts/jsonschema/ and contracts/examples/."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from robofleet.contracts.alert import Alert
from robofleet.contracts.catalogue import Bin, Sku
from robofleet.contracts.common import Coordinate, Heading
from robofleet.contracts.events import Event
from robofleet.contracts.layout import Cell, CellType, Flow, Layout
from robofleet.contracts.order import Order, Task
from robofleet.contracts.robot import Robot, RobotState
from robofleet.contracts.state import DynamicState, StaticWorld, WorldSnapshot


def export_all_schemas(output_dir: Path | None = None) -> list[str]:
    target_dir = output_dir or Path("contracts/jsonschema")
    target_dir.mkdir(parents=True, exist_ok=True)

    models: dict[str, type[BaseModel]] = {
        "StaticWorld": StaticWorld,
        "DynamicState": DynamicState,
        "WorldSnapshot": WorldSnapshot,
        "Layout": Layout,
        "Robot": Robot,
        "Order": Order,
        "Task": Task,
        "Alert": Alert,
        "Event": Event,
        "Sku": Sku,
        "Bin": Bin,
    }

    exported: list[str] = []
    for name, model_cls in models.items():
        schema_path = target_dir / f"{name}.json"
        schema_dict = model_cls.model_json_schema()
        schema_path.write_text(json.dumps(schema_dict, indent=2), encoding="utf-8")
        exported.append(str(schema_path))

    return exported


def export_sample_payloads(examples_dir: Path | None = None) -> None:
    target_dir = examples_dir or Path("contracts/examples")
    target_dir.mkdir(parents=True, exist_ok=True)

    # Create valid sample objects
    layout = Layout(
        name="sample_layout",
        width=5,
        height=5,
        cells=[
            Cell(pos=Coordinate(x=0, y=0), cell_type=CellType.FLOOR, flow=Flow.BOTH),
            Cell(pos=Coordinate(x=1, y=0), cell_type=CellType.SHELF, flow=Flow.BOTH),
        ],
    )
    static_world = StaticWorld(layout=layout)
    (target_dir / "static_world.json").write_text(
        static_world.model_dump_json(indent=2), encoding="utf-8"
    )

    dynamic_state = DynamicState(
        tick=0,
        sim_time_ms=0,
        seq=1,
        robots=[
            Robot(
                robot_id="R-001",
                cell=Coordinate(x=0, y=0),
                heading=Heading.N,
                state=RobotState.IDLE,
                battery_pct=100.0,
            )
        ],
    )
    (target_dir / "dynamic_state.json").write_text(
        dynamic_state.model_dump_json(indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    export_all_schemas()
    export_sample_payloads()
    print("Exported JSON Schemas and sample payloads.")
