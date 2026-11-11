# RoboFleet Layout Specification & ASCII Renders

## Overview
RoboFleet layouts represent realistic compact robot-assisted quick-commerce dark stores.
All walkable areas follow strict right-hand traffic flow lanes (E/W in horizontal aisles) to prevent traffic jams.

## Standard Dark Store Layout (28 x 20 cells, 20 Robots)
- **Footprint**: 28 x 20 cells @ 0.8m = 22.4m x 16.0m (~358 sq m, matching ASM-001).
- **Racks**: 4 double-rows (8 rack rows total), 14 cells long, 4 vertical levels per cell.
- **Stations**: 3 pick/pack stations on the South side with dedicated approach queues.
- **Dispatch Bay**: 2 dispatch handoff bays adjacent to supervisor desk.
- **Supervisor Area**: Restricted keep-out zone at (2, 18).
- **Chargers**: 4 fast charging bays on the East wall.
- **Parking**: 25 staging and parking bays on the North wall.

```
Layout: standard (28x20 cells)
Legend: # Wall | . Floor | S Shelf | T Station | D Dispatch | K Supervisor | C Charger | A Parking | > ^ < v Flow
------------------------------
#AAAAAAAAAAAAAAAAAAAAAAAAA#..#
#.........................C..#
#..>>>>>>>>>>>>>>>>>......#..#
#..SSSSSSSSSSSSSSSS.......C..#
#..SSSSSSSSSSSSSSSS.......#..#
#..<<<<<<<<<<<<<<<<<......C..#
#.........................#..#
#..>>>>>>>>>>>>>>>>>......C..#
#..SSSSSSSSSSSSSSSS.......#..#
#..SSSSSSSSSSSSSSSS..........#
#..<<<<<<<<<<<<<<<<<.........#
#............................#
#..>>>>>>>>>>>>>>>>>.........#
#..SSSSSSSSSSSSSSSS..........#
#..SSSSSSSSSSSSSSSS..........#
#..<<<<<<<<<<<<<<<<<.........#
#............................#
#.K.DD.T..T..T...............#
##############################
```

## Small Dark Store (20 x 14 cells, 10 Robots)
- **Footprint**: ~180 sq m. 2 double-rack rows, 2 stations, 3 chargers, 15 parking bays.

## Large Dark Store (44 x 28 cells, 50 Robots)
- **Footprint**: ~788 sq m. 6 double-rack rows, 6 stations, 8 chargers, 60 parking bays.
