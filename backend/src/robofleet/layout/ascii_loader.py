"""ASCII Layout loader for hand-drawn layout files.
Parses ASCII map, legend, and creates validated Layout contract.
"""

from __future__ import annotations

from pathlib import Path

from robofleet.contracts.common import Coordinate
from robofleet.contracts.layout import Cell, CellType, Charger, Flow, Layout, Station

CHAR_TO_TYPE: dict[str, CellType] = {
    "#": CellType.WALL,
    ".": CellType.FLOOR,
    "S": CellType.SHELF,
    "T": CellType.STATION,
    "P": CellType.PACK,
    "D": CellType.DISPATCH,
    "K": CellType.SUPERVISOR_DESK,
    "C": CellType.CHARGER,
    "A": CellType.PARKING,
}

CHAR_TO_FLOW: dict[str, Flow] = {
    "^": Flow.N,
    ">": Flow.E,
    "v": Flow.S,
    "<": Flow.W,
}


def load_ascii_layout(file_path: Path | str, cell_size_m: float = 0.8) -> Layout:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"ASCII layout file not found: {file_path}")

    lines = [line.rstrip("\r\n") for line in path.read_text(encoding="utf-8").splitlines()]
    # Filter empty lines
    grid_lines = [l for l in lines if l and not l.startswith("//")]
    if not grid_lines:
        raise ValueError(f"ASCII layout file '{file_path}' is empty.")

    height = len(grid_lines)
    width = max(len(l) for l in grid_lines)

    cells: list[Cell] = []
    stations: list[Station] = []
    chargers: list[Charger] = []
    parking: list[Coordinate] = []
    dispatch: list[Coordinate] = []
    supervisor: list[Coordinate] = []

    st_id = 1
    chg_id = 1

    for y, line in enumerate(grid_lines):
        for x in range(width):
            ch = line[x] if x < len(line) else "#"
            pos = Coordinate(x=x, y=y)

            flow = Flow.BOTH
            if ch in CHAR_TO_FLOW:
                flow = CHAR_TO_FLOW[ch]
                cell_type = CellType.FLOOR
            else:
                cell_type = CHAR_TO_TYPE.get(ch, CellType.WALL)

            zone = None
            if cell_type == CellType.SUPERVISOR_DESK:
                zone = "supervisor_area"
                supervisor.append(pos)
            elif cell_type == CellType.DISPATCH:
                zone = "dispatch_zone"
                dispatch.append(pos)
            elif cell_type == CellType.CHARGER:
                zone = "charger_bay"
                chargers.append(Charger(charger_id=f"CHG-{chg_id:02d}", pos=pos))
                chg_id += 1
            elif cell_type == CellType.PARKING:
                zone = "parking_area"
                parking.append(pos)
            elif cell_type == CellType.STATION:
                zone = "picking_stations"
                stations.append(
                    Station(
                        station_id=f"ST-{st_id:02d}",
                        pos=pos,
                        queue_cells=[Coordinate(x=x, y=max(0, y - 1))],
                    )
                )
                st_id += 1
            elif cell_type == CellType.SHELF:
                zone = "shelf_storage"

            cells.append(Cell(pos=pos, cell_type=cell_type, flow=flow, zone=zone))

    return Layout(
        name=path.stem,
        width=width,
        height=height,
        cell_size_m=cell_size_m,
        cells=cells,
        stations=stations,
        chargers=chargers,
        parking_cells=parking,
        dispatch_cells=dispatch,
        supervisor_cells=supervisor,
    )
