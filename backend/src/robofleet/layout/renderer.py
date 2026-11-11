"""ASCII renderer for dark store layouts.
Generates readable ASCII maps with symbols and lane flow markers for documentation and CLI.
"""

from __future__ import annotations

from robofleet.contracts.layout import CellType, Flow, Layout

TYPE_TO_CHAR = {
    CellType.WALL: "#",
    CellType.FLOOR: ".",
    CellType.SHELF: "S",
    CellType.STATION: "T",
    CellType.PACK: "P",
    CellType.DISPATCH: "D",
    CellType.SUPERVISOR_DESK: "K",
    CellType.CHARGER: "C",
    CellType.PARKING: "A",
}

FLOW_TO_CHAR = {
    Flow.N: "^",
    Flow.E: ">",
    Flow.S: "v",
    Flow.W: "<",
}


def render_ascii_layout(
    layout: Layout,
    show_flow: bool = True,
    robot_positions: dict[tuple[int, int], str] | None = None,
) -> str:
    grid = {(c.pos.x, c.pos.y): c for c in layout.cells}
    lines: list[str] = []

    # Legend header
    lines.append(f"Layout: {layout.name} ({layout.width}x{layout.height} cells)")
    lines.append(
        "Legend: # Wall | . Floor | S Shelf | T Station | D Dispatch | K Supervisor | C Charger | A Parking | > ^ < v Flow"
    )
    lines.append("-" * (layout.width + 2))

    for y in range(layout.height):
        row_chars: list[str] = []
        for x in range(layout.width):
            if robot_positions and (x, y) in robot_positions:
                row_chars.append("R")
                continue

            cell = grid.get((x, y))
            if not cell:
                row_chars.append(" ")
            elif show_flow and cell.cell_type == CellType.FLOOR and cell.flow in FLOW_TO_CHAR:
                row_chars.append(FLOW_TO_CHAR[cell.flow])
            else:
                row_chars.append(TYPE_TO_CHAR.get(cell.cell_type, "?"))
        lines.append("".join(row_chars))

    lines.append("-" * (layout.width + 2))
    return "\n".join(lines)
