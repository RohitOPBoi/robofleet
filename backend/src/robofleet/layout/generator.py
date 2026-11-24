"""Parametric layout generator producing Layout contracts.
Builds dark store layouts with rack rows, one-way/two-way aisles, stations, chargers, parking, and zones.
"""

from __future__ import annotations

from robofleet.config.models import LayoutPresetConfig
from robofleet.contracts.common import Coordinate
from robofleet.contracts.layout import Cell, CellType, Charger, Flow, Layout, Station, Zone


def generate_parametric_layout(
    config: LayoutPresetConfig, name: str = "parametric_layout", cell_size_m: float = 0.8
) -> Layout:
    width = config.width
    height = config.height
    effective_cell_size = getattr(config, "cell_size_m", cell_size_m)

    # Initialize grid map with WALLs on perimeter and FLOOR inside
    grid: dict[tuple[int, int], Cell] = {}
    for y in range(height):
        for x in range(width):
            pos = Coordinate(x=x, y=y)
            if x == 0 or x == width - 1 or y == 0 or y == height - 1:
                grid[(x, y)] = Cell(pos=pos, cell_type=CellType.WALL, flow=Flow.BOTH)
            else:
                grid[(x, y)] = Cell(pos=pos, cell_type=CellType.FLOOR, flow=Flow.BOTH)

    stations: list[Station] = []
    chargers: list[Charger] = []
    parking_cells: list[Coordinate] = []
    dispatch_cells: list[Coordinate] = []
    supervisor_cells: list[Coordinate] = []

    # South edge perimeter: stations, dispatch, supervisor desk, chargers
    bottom_y = height - 2

    # 1. Supervisor Desk
    sup_pos = Coordinate(x=2, y=bottom_y)
    grid[(sup_pos.x, sup_pos.y)] = Cell(
        pos=sup_pos, cell_type=CellType.SUPERVISOR_DESK, flow=Flow.BOTH, zone="supervisor_area"
    )
    supervisor_cells.append(sup_pos)

    # 2. Dispatch Bays
    disp_pos1 = Coordinate(x=4, y=bottom_y)
    disp_pos2 = Coordinate(x=5, y=bottom_y)
    grid[(disp_pos1.x, disp_pos1.y)] = Cell(
        pos=disp_pos1, cell_type=CellType.DISPATCH, flow=Flow.BOTH, zone="dispatch_zone"
    )
    grid[(disp_pos2.x, disp_pos2.y)] = Cell(
        pos=disp_pos2, cell_type=CellType.DISPATCH, flow=Flow.BOTH, zone="dispatch_zone"
    )
    dispatch_cells.extend([disp_pos1, disp_pos2])

    # 3. Stations
    st_start_x = 7
    for s_idx in range(config.station_count):
        st_x = st_start_x + s_idx * 3
        if st_x < width - 6:
            st_pos = Coordinate(x=st_x, y=bottom_y)
            grid[(st_x, bottom_y)] = Cell(
                pos=st_pos, cell_type=CellType.STATION, flow=Flow.BOTH, zone="picking_stations"
            )
            # Queue cells leading up north (offset by x-1 so dock exit remains clear)
            q_cells = [
                Coordinate(x=st_x - 1, y=bottom_y - 1),
                Coordinate(x=st_x - 1, y=bottom_y - 2),
                Coordinate(x=st_x - 1, y=bottom_y - 3),
            ]
            stations.append(
                Station(
                    station_id=f"ST-{s_idx + 1:02d}",
                    pos=st_pos,
                    queue_cells=q_cells,
                    worker_count=1,
                )
            )

    # 4. Chargers along East wall
    ch_x = width - 2
    for c_idx in range(config.charger_count):
        c_y = 2 + c_idx * 2
        if c_y < height - 3:
            c_pos = Coordinate(x=ch_x, y=c_y)
            grid[(ch_x, c_y)] = Cell(
                pos=c_pos, cell_type=CellType.CHARGER, flow=Flow.BOTH, zone="charger_bay"
            )
            chargers.append(Charger(charger_id=f"CHG-{c_idx + 1:02d}", pos=c_pos))

    # 5. Parking Bays along North wall (rows y=1 and y=2 if needed)
    park_count = 0
    for py in range(1, 3):
        for p_x in range(2, width - 4):
            if park_count >= config.parking_count:
                break
            p_pos = Coordinate(x=p_x, y=py)
            grid[(p_x, py)] = Cell(
                pos=p_pos, cell_type=CellType.PARKING, flow=Flow.BOTH, zone="parking_area"
            )
            parking_cells.append(p_pos)
            park_count += 1
        if park_count >= config.parking_count:
            break

    # 6. Storage Racks (SHELF) arranged in rows with aisles
    rack_start_y = 4
    rack_start_x = 3
    rack_end_x = min(width - 5, rack_start_x + config.rack_length)

    current_y = rack_start_y
    for row_idx in range(config.rack_rows):
        if current_y + 3 >= bottom_y - 2:
            break
        # Create double-rack row (two adjacent shelf cells)
        temp_zone = "ambient"
        if row_idx == 0:
            temp_zone = "chilled"
        elif row_idx == 1 and config.rack_rows > 3:
            temp_zone = "frozen"

        for rx in range(rack_start_x, rack_end_x):
            shelf_pos1 = Coordinate(x=rx, y=current_y)
            shelf_pos2 = Coordinate(x=rx, y=current_y + 1)
            zone_name = f"racks_row_{row_idx + 1}"
            grid[(rx, current_y)] = Cell(
                pos=shelf_pos1,
                cell_type=CellType.SHELF,
                flow=Flow.BOTH,
                zone=zone_name,
                level_count=config.rack_levels,
                metadata={"temperature_zone": temp_zone},
            )
            grid[(rx, current_y + 1)] = Cell(
                pos=shelf_pos2,
                cell_type=CellType.SHELF,
                flow=Flow.BOTH,
                zone=zone_name,
                level_count=config.rack_levels,
                metadata={"temperature_zone": temp_zone},
            )

        # Flow lanes for aisle if right_hand_traffic is enabled (only inside rack aisles; cross-aisles and station zones remain Flow.BOTH)
        aisle_top_y = current_y - 1
        aisle_bottom_y = current_y + 2
        if config.right_hand_traffic:
            for rx in range(rack_start_x, rack_end_x):
                if (
                    (rx, aisle_top_y) in grid
                    and grid[(rx, aisle_top_y)].cell_type == CellType.FLOOR
                    and aisle_top_y < bottom_y - 2
                ):
                    grid[(rx, aisle_top_y)].flow = Flow.E
                if (
                    (rx, aisle_bottom_y) in grid
                    and grid[(rx, aisle_bottom_y)].cell_type == CellType.FLOOR
                    and aisle_bottom_y < bottom_y - 2
                ):
                    grid[(rx, aisle_bottom_y)].flow = Flow.W

        current_y += 2 + config.aisle_width

    zones = [
        Zone(
            name="supervisor_area",
            description="Supervisor Desk and Office",
            top_left=Coordinate(x=1, y=bottom_y - 1),
            bottom_right=Coordinate(x=3, y=bottom_y),
            restricted=True,
        ),
        Zone(
            name="dispatch_zone",
            description="Order Dispatch Staging",
            top_left=Coordinate(x=4, y=bottom_y - 1),
            bottom_right=Coordinate(x=6, y=bottom_y),
        ),
        Zone(
            name="picking_stations",
            description="Goods to person picking stations",
            top_left=Coordinate(x=7, y=bottom_y - 2),
            bottom_right=Coordinate(x=width - 5, y=bottom_y),
        ),
        Zone(
            name="charger_bay",
            description="AMR Battery Charging Bays",
            top_left=Coordinate(x=width - 3, y=1),
            bottom_right=Coordinate(x=width - 2, y=height - 2),
        ),
        Zone(
            name="parking_area",
            description="AMR Staging and Parking",
            top_left=Coordinate(x=1, y=1),
            bottom_right=Coordinate(x=width - 4, y=2),
        ),
    ]

    return Layout(
        name=name,
        width=width,
        height=height,
        cell_size_m=effective_cell_size,
        cells=list(grid.values()),
        zones=zones,
        stations=stations,
        chargers=chargers,
        parking_cells=parking_cells,
        dispatch_cells=dispatch_cells,
        supervisor_cells=supervisor_cells,
    )
