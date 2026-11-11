"""Tests for layout presets, ASCII loader, graph validation, and shelf access."""

from __future__ import annotations

from pathlib import Path

from robofleet.config.loader import load_config
from robofleet.contracts.common import Coordinate
from robofleet.contracts.layout import Cell, CellType, Flow, Layout
from robofleet.layout.ascii_loader import load_ascii_layout
from robofleet.layout.generator import generate_parametric_layout
from robofleet.layout.renderer import render_ascii_layout
from robofleet.layout.validator import validate_layout


def test_three_layout_presets_generate_and_validate() -> None:
    for preset_name in ("small", "standard", "large"):
        cfg, _ = load_config(scenario_name=preset_name)
        layout = generate_parametric_layout(cfg.layout, name=preset_name)
        ok, errors = validate_layout(layout, required_robots=cfg.robot_count)
        assert ok, f"Preset '{preset_name}' failed validation: {errors}"
        assert layout.width > 0
        assert layout.height > 0
        # Check rendered output
        rendered = render_ascii_layout(layout)
        assert "Layout: " in rendered
        assert "#" in rendered


def test_ascii_layout_loader_and_validation() -> None:
    ascii_file = Path("scenarios/custom_ascii.txt")
    layout = load_ascii_layout(ascii_file)
    ok, errors = validate_layout(layout, required_robots=10)
    assert ok, f"Custom ASCII layout failed validation: {errors}"
    assert layout.width == 20
    assert layout.height == 10


def test_layout_validator_catches_disconnected_islands() -> None:
    # Create layout with an unreachable walkable island
    cells = [
        Cell(pos=Coordinate(x=0, y=0), cell_type=CellType.FLOOR, flow=Flow.BOTH),
        Cell(pos=Coordinate(x=1, y=0), cell_type=CellType.WALL, flow=Flow.BOTH),
        Cell(pos=Coordinate(x=2, y=0), cell_type=CellType.FLOOR, flow=Flow.BOTH),  # Isolated!
    ]
    bad_layout = Layout(name="bad_island", width=3, height=1, cells=cells)
    ok, errors = validate_layout(bad_layout)
    assert not ok
    assert any("not strongly connected" in e for e in errors)


def test_layout_validator_catches_inaccessible_shelves() -> None:
    # Shelf completely surrounded by walls, with a disconnected floor cell present
    cells = [
        Cell(pos=Coordinate(x=0, y=0), cell_type=CellType.WALL, flow=Flow.BOTH),
        Cell(pos=Coordinate(x=1, y=0), cell_type=CellType.SHELF, flow=Flow.BOTH),
        Cell(pos=Coordinate(x=2, y=0), cell_type=CellType.WALL, flow=Flow.BOTH),
        Cell(pos=Coordinate(x=0, y=1), cell_type=CellType.FLOOR, flow=Flow.BOTH),
    ]
    bad_layout = Layout(name="blocked_shelf", width=3, height=2, cells=cells)
    ok, errors = validate_layout(bad_layout)
    assert not ok
    assert any("no adjacent walkable access cell" in e for e in errors)
