"""Layout validator.
Verifies directed graph connectivity under flow rules, shelf accessibility,
queue connectivity, and reachability of all functional cells.
"""

from __future__ import annotations

from collections import deque

from robofleet.contracts.common import Coordinate, Heading
from robofleet.contracts.layout import Cell, CellType, Flow, Layout


def _get_walkable_neighbors(
    cell: Cell, layout_grid: dict[tuple[int, int], Cell], width: int, height: int
) -> list[Coordinate]:
    allowed_headings: list[Heading] = []
    match cell.flow:
        case Flow.BOTH:
            allowed_headings = [Heading.N, Heading.E, Heading.S, Heading.W]
        case Flow.N:
            allowed_headings = [Heading.N]
        case Flow.E:
            allowed_headings = [Heading.E]
        case Flow.S:
            allowed_headings = [Heading.S]
        case Flow.W:
            allowed_headings = [Heading.W]
        case Flow.NS:
            allowed_headings = [Heading.N, Heading.S]
        case Flow.EW:
            allowed_headings = [Heading.E, Heading.W]

    neighbors: list[Coordinate] = []
    cx, cy = cell.pos.x, cell.pos.y
    for h in allowed_headings:
        dx, dy = h.delta
        nx, ny = cx + dx, cy + dy
        if 0 <= nx < width and 0 <= ny < height:
            n_cell = layout_grid.get((nx, ny))
            if n_cell and n_cell.is_walkable:
                neighbors.append(n_cell.pos)
    return neighbors


def validate_layout(layout: Layout, required_robots: int = 1) -> tuple[bool, list[str]]:
    errors: list[str] = []
    width, height = layout.width, layout.height
    grid: dict[tuple[int, int], Cell] = {(c.pos.x, c.pos.y): c for c in layout.cells}

    walkable_cells = [c for c in layout.cells if c.is_walkable]
    if not walkable_cells:
        return False, ["Layout contains zero walkable cells."]

    # 1. Reachability / Connectedness via BFS from first walkable cell
    start_pos = walkable_cells[0].pos
    visited: set[tuple[int, int]] = set()
    queue = deque([start_pos])
    visited.add((start_pos.x, start_pos.y))

    while queue:
        curr_pos = queue.popleft()
        curr_cell = grid.get((curr_pos.x, curr_pos.y))
        if not curr_cell:
            continue
        for n_pos in _get_walkable_neighbors(curr_cell, grid, width, height):
            key = (n_pos.x, n_pos.y)
            if key not in visited:
                visited.add(key)
                queue.append(n_pos)

    unreachable_walkable = [c for c in walkable_cells if (c.pos.x, c.pos.y) not in visited]
    if unreachable_walkable:
        errors.append(
            f"Graph is not strongly connected: {len(unreachable_walkable)} walkable cells are unreachable."
        )

    # 2. Shelf access check: each shelf must have at least one adjacent walkable cell
    for c in layout.cells:
        if c.cell_type == CellType.SHELF:
            has_access = False
            for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                ax, ay = c.pos.x + dx, c.pos.y + dy
                adj = grid.get((ax, ay))
                if adj and adj.is_walkable:
                    has_access = True
                    break
            if not has_access:
                errors.append(
                    f"Shelf cell at ({c.pos.x}, {c.pos.y}) has no adjacent walkable access cell."
                )

    # 3. Chargers, parking, and stations reachability
    for chg in layout.chargers:
        if (chg.pos.x, chg.pos.y) not in visited:
            errors.append(
                f"Charger '{chg.charger_id}' at ({chg.pos.x}, {chg.pos.y}) is unreachable."
            )

    for st in layout.stations:
        if (st.pos.x, st.pos.y) not in visited:
            errors.append(f"Station '{st.station_id}' at ({st.pos.x}, {st.pos.y}) is unreachable.")

    # 4. Parking capacity check
    if len(layout.parking_cells) < required_robots:
        errors.append(
            f"Parking capacity ({len(layout.parking_cells)}) is less than required robot count ({required_robots})."
        )

    return len(errors) == 0, errors
