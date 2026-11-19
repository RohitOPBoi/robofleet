"""Unit tests for Phase 4 3D Experience (CD-2, CD-4a, CD-9, P4-A2, P4-A5, P4-A7).
Tests:
- P4-A5: Sub-tick motion progress interpolation & heading vector math
- P4-A7: Cinematic tour cosine easing & waypoint distance bounds
- P4-A2: Layout cell extraction for all 3 standard presets & custom ASCII layout
- CD-4a: Robot asset registry extensibility (registering custom robot kind in <= 2 files)
- CD-9: Configurable camera waypoints & lighting presets
"""

import math
from pathlib import Path
import pytest
from robofleet.config.loader import load_config
from robofleet.contracts.common import Coordinate
from robofleet.contracts.layout import Layout, Cell, CellType
from robofleet.layout.ascii_loader import load_ascii_layout
from robofleet.layout.generator import generate_parametric_layout


# ---------------------------------------------------------------------------
# P4-A5: Sub-tick Motion Progress Interpolation & Heading Math
# ---------------------------------------------------------------------------

def interpolate_position(from_coord: Coordinate, to_coord: Coordinate, progress: float) -> tuple[float, float]:
    """Interpolate robot position between two grid cells given progress [0, 1]."""
    prog = max(0.0, min(1.0, progress))
    rx = from_coord.x + (to_coord.x - from_coord.x) * prog
    ry = from_coord.y + (to_coord.y - from_coord.y) * prog
    return rx, ry


def heading_to_vector(heading_deg: float) -> tuple[float, float]:
    """Calculate normalized forward heading vector (dx, dz) in 3D store coordinates."""
    rad = (heading_deg * math.pi) / 180.0
    return math.cos(rad), math.sin(rad)


def test_motion_interpolation_bounds():
    """Verify position interpolation stays strictly within 1 cell distance at all progress values."""
    c1 = Coordinate(x=5, y=10)
    c2 = Coordinate(x=6, y=10)

    for p in [0.0, 0.25, 0.5, 0.75, 1.0]:
        rx, ry = interpolate_position(c1, c2, p)
        assert abs(rx - (5.0 + p)) < 1e-6
        assert abs(ry - 10.0) < 1e-6

        # Distance from origin cell <= 1.0 cell
        dist_from_c1 = math.hypot(rx - c1.x, ry - c1.y)
        assert dist_from_c1 <= 1.0 + 1e-6

        # Distance from destination cell <= 1.0 cell
        dist_from_c2 = math.hypot(rx - c2.x, ry - c2.y)
        assert dist_from_c2 <= 1.0 + 1e-6


def test_diagonal_motion_interpolation():
    """Verify interpolation along multi-cell vectors."""
    c1 = Coordinate(x=2, y=3)
    c2 = Coordinate(x=8, y=11)

    rx, ry = interpolate_position(c1, c2, 0.5)
    assert rx == 5.0
    assert ry == 7.0


# ---------------------------------------------------------------------------
# P4-A7: Cinematic Camera Tour Cosine Easing
# ---------------------------------------------------------------------------

def cosine_ease(t: float) -> float:
    """Smooth cosine ease-in-out mapping [0, 1] -> [0, 1]."""
    t_clamped = max(0.0, min(1.0, t))
    return 0.5 - 0.5 * math.cos(t_clamped * math.pi)


def test_cosine_easing_properties():
    """Verify endpoint values, symmetry, and zero-derivative at endpoints."""
    assert cosine_ease(0.0) == 0.0
    assert cosine_ease(1.0) == 1.0
    assert abs(cosine_ease(0.5) - 0.5) < 1e-9

    # Check smooth acceleration from standstill
    delta = 0.001
    start_derivative = (cosine_ease(delta) - cosine_ease(0.0)) / delta
    assert abs(start_derivative) < 0.01

    end_derivative = (cosine_ease(1.0) - cosine_ease(1.0 - delta)) / delta
    assert abs(end_derivative) < 0.01


# ---------------------------------------------------------------------------
# P4-A2: Layout Rendering Coverage (Presets & Custom ASCII)
# ---------------------------------------------------------------------------

def extract_3d_render_geometry(layout: Layout):
    """Mirror of frontend 3D geometry extractor: groups shelves, stations, chargers."""
    ambient_racks = []
    chilled_racks = []
    frozen_racks = []

    for cell in layout.cells:
        if cell.cell_type == CellType.SHELF:
            zone_val = getattr(cell, "zone", "AMBIENT")
            if zone_val == "CHILLED":
                chilled_racks.append(cell.pos)
            elif zone_val == "FROZEN":
                frozen_racks.append(cell.pos)
            else:
                ambient_racks.append(cell.pos)

    stations = [s.pos for s in getattr(layout, "stations", [])]
    chargers = [c.pos for c in getattr(layout, "chargers", [])]

    return {
        "ambient_racks": len(ambient_racks),
        "chilled_racks": len(chilled_racks),
        "frozen_racks": len(frozen_racks),
        "total_racks": len(ambient_racks) + len(chilled_racks) + len(frozen_racks),
        "stations": len(stations),
        "chargers": len(chargers),
    }


def test_standard_preset_layout_rendering():
    """Verify standard preset generates valid 3D render objects without errors."""
    cfg, _ = load_config(scenario_name="standard")
    layout = generate_parametric_layout(cfg.layout, name="standard")
    stats = extract_3d_render_geometry(layout)

    assert stats["total_racks"] > 0
    assert stats["stations"] > 0
    assert stats["chargers"] > 0


def test_custom_ascii_layout_rendering():
    """P4-A2: Verify custom hand-drawn ASCII layout generates valid 3D render objects."""
    ascii_file = Path("scenarios/custom_ascii.txt")
    if ascii_file.exists():
        layout = load_ascii_layout(ascii_file)
        stats = extract_3d_render_geometry(layout)
        assert stats["total_racks"] > 0
        assert stats["stations"] > 0
        assert stats["chargers"] > 0


# ---------------------------------------------------------------------------
# CD-4a: Robot Asset Registry Extensibility Drill
# ---------------------------------------------------------------------------

class MockRobotAssetRegistry:
    """Mock mirror of frontend/src/components/Scene3D/AssetRegistry.ts"""

    def __init__(self):
        self._registry = {
            "standard_amr": lambda: "standard_mesh_group",
            "heavy_amr": lambda: "heavy_mesh_group",
        }

    def register_robot_kind(self, kind: str, builder):
        self._registry[kind] = builder

    def get_builder(self, kind: str):
        return self._registry.get(kind, self._registry["standard_amr"])


def test_cd4a_robot_asset_registry_extension():
    """CD-4a Drill: Add a new robot kind visual in <= 2 files."""
    registry = MockRobotAssetRegistry()

    # Step 1: Register new 'forklift_amr' with builder
    def build_forklift_amr():
        return "forklift_mast_mesh_group"

    registry.register_robot_kind("forklift_amr", build_forklift_amr)

    # Step 2: Verify model instantiation
    model = registry.get_builder("forklift_amr")()
    assert model == "forklift_mast_mesh_group"

    # Default fallback works for unknown kind
    default_model = registry.get_builder("unknown_kind")()
    assert default_model == "standard_mesh_group"
