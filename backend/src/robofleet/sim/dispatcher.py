"""Wander Dispatcher (CA-5).
Placeholder dispatcher that keeps idle robots moving to reachable dark store destinations.
Automatically directs low-battery robots to free charging bays.
"""

from __future__ import annotations

import numpy as np

from robofleet.contracts.common import Coordinate
from robofleet.contracts.layout import CellType, Layout
from robofleet.contracts.robot import Robot


class WanderDispatcher:
    def __init__(
        self,
        dwell_ticks: int = 20,
        recharge_target_pct: float = 95.0,
        park_when_idle: bool = False,
    ) -> None:
        self.dwell_ticks = dwell_ticks
        self.recharge_target_pct = recharge_target_pct
        self.park_when_idle = park_when_idle
        self._robot_dwell: dict[str, int] = {}
        self._robot_destinations: dict[str, Coordinate] = {}

    def get_destinations(
        self,
        robots: list[Robot],
        layout: Layout,
        low_battery_threshold: float,
        rng: np.random.Generator,
    ) -> dict[str, Coordinate]:
        destinations: dict[str, Coordinate] = {}

        # Valid candidate target cells: floor, parking, dispatch, station (exclude chargers)
        candidate_cells: list[Coordinate] = []
        for c in layout.cells:
            if c.is_walkable and c.cell_type in (
                CellType.FLOOR,
                CellType.PARKING,
                CellType.DISPATCH,
                CellType.STATION,
            ):
                candidate_cells.append(c.pos)

        charger_cells = [c.pos for c in layout.chargers]
        charger_tuples = {c.as_tuple() for c in charger_cells}

        # Track which chargers are occupied by charging robots
        occupied_chargers = {
            r.cell.as_tuple()
            for r in robots
            if r.cell.as_tuple() in charger_tuples and r.battery_pct < self.recharge_target_pct
        }
        assigned_chargers: set[tuple[int, int]] = set()

        # Phase 1: Handle charging and low-battery robots first
        low_battery_robots = sorted(
            [
                r
                for r in robots
                if r.battery_pct <= low_battery_threshold or r.cell.as_tuple() in charger_tuples
            ],
            key=lambda r: r.battery_pct,
        )

        for robot in low_battery_robots:
            r_id = robot.robot_id
            # If robot reached full charge, vacate charger
            if (
                robot.cell.as_tuple() in charger_tuples
                and robot.battery_pct >= self.recharge_target_pct
            ):
                self._robot_dwell[r_id] = 0
                free_cand = [c for c in candidate_cells if c.as_tuple() not in charger_tuples]
                pool = free_cand if free_cand else candidate_cells
                new_tgt = pool[rng.integers(0, len(pool))]
                self._robot_destinations[r_id] = new_tgt
                destinations[r_id] = new_tgt
                continue

            # If already at charger and still charging (< 95%), stay put
            if robot.cell.as_tuple() in charger_tuples:
                destinations[r_id] = robot.cell
                self._robot_destinations[r_id] = robot.cell
                assigned_chargers.add(robot.cell.as_tuple())
                continue

            # Low battery needing charger: pick free unassigned charger
            available_chargers = [
                ch
                for ch in charger_cells
                if ch.as_tuple() not in occupied_chargers and ch.as_tuple() not in assigned_chargers
            ]
            if available_chargers:
                chosen = min(available_chargers, key=lambda ch: ch.manhattan_distance(robot.cell))
                self._robot_destinations[r_id] = chosen
                destinations[r_id] = chosen
                assigned_chargers.add(chosen.as_tuple())
            else:
                # All chargers currently occupied or assigned:
                # Pick charger with fewest waiting robots and stage at approach cell (2 units west)
                charger_counts = {
                    ch.as_tuple(): sum(
                        1 for d in destinations.values() if d.as_tuple() == ch.as_tuple()
                    )
                    for ch in charger_cells
                }
                best_charger = min(
                    charger_cells,
                    key=lambda ch: (
                        charger_counts[ch.as_tuple()],
                        ch.manhattan_distance(robot.cell),
                    ),
                )
                staging_pos = Coordinate(x=max(1, best_charger.x - 2), y=best_charger.y)
                destinations[r_id] = staging_pos
                self._robot_destinations[r_id] = staging_pos

        # Phase 2: All other robots (parking / resting when idle)
        sorted_all_robots = sorted(robots, key=lambda r: r.robot_id)
        parking_cells = layout.parking_cells or []

        for idx, robot in enumerate(sorted_all_robots):
            r_id = robot.robot_id
            if r_id in destinations:
                continue

            # If park_when_idle is enabled and parking bays are configured, rest in assigned bay
            if self.park_when_idle and parking_cells:
                home_slot = parking_cells[idx % len(parking_cells)]
                if robot.cell.as_tuple() == home_slot.as_tuple():
                    # Rest at designated home parking spot without aimless roaming
                    destinations[r_id] = robot.cell
                    self._robot_destinations[r_id] = robot.cell
                    self._robot_dwell[r_id] = 0
                else:
                    destinations[r_id] = home_slot
                    self._robot_destinations[r_id] = home_slot
                continue

            curr_target = self._robot_destinations.get(r_id)
            if curr_target is None or (
                curr_target.x == robot.cell.x and curr_target.y == robot.cell.y
            ):
                dwell = self._robot_dwell.get(r_id, 0)
                if dwell < self.dwell_ticks:
                    self._robot_dwell[r_id] = dwell + 1
                    destinations[r_id] = robot.cell
                    continue
                else:
                    self._robot_dwell[r_id] = 0
                    if candidate_cells:
                        already_targeted = {c.as_tuple() for c in destinations.values()}
                        free_candidates = [
                            c
                            for c in candidate_cells
                            if c.as_tuple() not in already_targeted
                            and c.as_tuple() not in charger_tuples
                        ]
                        pool = free_candidates if free_candidates else candidate_cells
                        new_target = pool[rng.integers(0, len(pool))]
                        self._robot_destinations[r_id] = new_target
                        destinations[r_id] = new_target
                    else:
                        destinations[r_id] = robot.cell
            else:
                destinations[r_id] = curr_target

        return destinations

    def dispatch(
        self,
        orders: list[Any],
        robots: list[Robot],
        layout: Layout,
        bins: dict[str, Any],
        skus: dict[str, Any],
        task_mgr: Any,
        station_mgr: Any,
        current_tick: int,
        rng: np.random.Generator,
    ) -> dict[str, Coordinate]:
        """Dispatch with intelligent Robot Supervisor when orders exist; fallback to wander when empty."""
        from robofleet.contracts.order import OrderStatus
        from robofleet.fleet.strategies.supervisor import RobotSupervisorStrategy

        active_orders = [
            o
            for o in orders
            if getattr(o, "status", None)
            in (
                OrderStatus.RECEIVED,
                OrderStatus.QUEUED,
                OrderStatus.PLANNED,
                OrderStatus.RETRIEVING,
                OrderStatus.AT_STATION,
                OrderStatus.PICKING,
            )
        ]
        active_tasks = any(r.current_task_id is not None for r in robots)
        if active_orders or active_tasks:
            if not hasattr(self, "_supervisor_delegate"):
                self._supervisor_delegate = RobotSupervisorStrategy(
                    low_battery_threshold=20.0,
                    recharge_target_pct=self.recharge_target_pct,
                )
            return self._supervisor_delegate.dispatch(
                orders=orders,
                robots=robots,
                layout=layout,
                bins=bins,
                skus=skus,
                task_mgr=task_mgr,
                station_mgr=station_mgr,
                current_tick=current_tick,
                rng=rng,
            )

        return self.get_destinations(
            robots=robots,
            layout=layout,
            low_battery_threshold=20.0,
            rng=rng,
        )

