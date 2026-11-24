"""Tests for contracts, serialization, SemVer, migrations, and schema compatibility."""

from __future__ import annotations

import pytest
from robofleet.contracts.common import SCHEMA_VERSION, Coordinate, EnvironmentMeta, Heading
from robofleet.contracts.layout import Cell, CellType, Layout
from robofleet.contracts.migrations import migrate, register_migration
from robofleet.contracts.robot import Robot, RobotState
from robofleet.contracts.state import DynamicState, StaticWorld, WorldSnapshot
from robofleet.tools.schema_compat import check_compatibility


def test_schema_version_and_environment_meta() -> None:
    meta = EnvironmentMeta()
    assert meta.schema_version == SCHEMA_VERSION
    assert meta.mode == "digital_twin"
    assert meta.robot_layer == "simulated"


def test_extra_fields_ignored_for_backwards_compatibility() -> None:
    # Clients must tolerate unknown fields without raising ValidationError
    payload = {
        "robot_id": "R-999",
        "cell": {"x": 5, "y": 5},
        "heading": "N",
        "state": "IDLE",
        "battery_pct": 98.5,
        "future_unreleased_field": "some_value",
        "ext": {"custom_tag": "experimental"},
    }
    robot = Robot.model_validate(payload)
    assert robot.robot_id == "R-999"
    assert robot.ext.get("custom_tag") == "experimental"


def test_world_snapshot_roundtrip() -> None:
    layout = Layout(
        name="test_grid",
        width=10,
        height=10,
        cells=[Cell(pos=Coordinate(x=0, y=0), cell_type=CellType.FLOOR)],
    )
    static_world = StaticWorld(layout=layout)
    dynamic_state = DynamicState(
        tick=42,
        sim_time_ms=4200,
        seq=10,
        robots=[
            Robot(
                robot_id="R-001",
                cell=Coordinate(x=0, y=0),
                heading=Heading.N,
                state=RobotState.IDLE,
            )
        ],
    )
    snapshot = WorldSnapshot(static=static_world, dynamic=dynamic_state)

    json_data = snapshot.model_dump_json()
    reconstructed = WorldSnapshot.model_validate_json(json_data)
    assert reconstructed.dynamic.tick == 42
    assert reconstructed.dynamic.robots[0].robot_id == "R-001"
    assert reconstructed.static.layout.name == "test_grid"


def test_migration_registry() -> None:
    def migrate_1_to_2(payload: dict[str, object]) -> dict[str, object]:
        copy = dict(payload)
        copy["migrated"] = True
        return copy

    register_migration("1.0.0", "2.0.0", migrate_1_to_2)
    sample = {"version": "1.0.0", "data": 123}
    migrated = migrate(sample, "1.0.0", "2.0.0")
    assert migrated["migrated"] is True

    # Same version returns unchanged
    assert migrate(sample, "1.0.0", "1.0.0") == sample

    with pytest.raises(ValueError, match="No registered migration path"):
        migrate(sample, "1.0.0", "9.9.9")


def test_schema_compatibility_with_committed_schemas() -> None:
    ok, results = check_compatibility()
    assert ok, f"Schema compatibility check failed: {results}"
    for model_name, status in results.items():
        assert status in ("NONE", "PATCH", "MINOR"), (
            f"Model {model_name} had breaking change: {status}"
        )


def test_generated_typescript_types_up_to_date() -> None:
    from pathlib import Path

    from robofleet.tools.export_types import TYPESCRIPT_HEADER

    ts_file = Path("frontend/src/types/generated.ts")
    assert ts_file.exists(), "frontend/src/types/generated.ts does not exist! Run 'make types'."
    current_content = ts_file.read_text(encoding="utf-8")
    expected_content = TYPESCRIPT_HEADER.strip() + "\n"
    assert current_content == expected_content, (
        "frontend/src/types/generated.ts is stale! Run 'make types'."
    )
