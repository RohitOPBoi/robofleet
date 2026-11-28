"""A* Flow Planner for dark store directed flow graphs (CA-5).
Finds shortest paths obeying cell flow constraints and proposes MoveIntents.
Handles replanning wait thresholds, yield, and deadlock detection.
"""

from __future__ import annotations

import heapq

import numpy as np

from robofleet.contracts.common import Coordinate, Heading
from robofleet.contracts.layout import Cell, Flow, Layout
from robofleet.contracts.robot import Robot, RobotState
from robofleet.sim.safety import MoveIntent


def _get_flow_neighbors(
    curr: Coordinate, grid: dict[tuple[int, int], Cell], blocked: set[tuple[int, int]]
) -> list[Coordinate]:
    cell = grid.get((curr.x, curr.y))
    if not cell or not cell.is_walkable:
        return []

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
    for h in allowed_headings:
        dx, dy = h.delta
        nx, ny = curr.x + dx, curr.y + dy
        if (nx, ny) in blocked:
            continue
        n_cell = grid.get((nx, ny))
        if n_cell and n_cell.is_walkable:
            neighbors.append(Coordinate(x=nx, y=ny))
    return neighbors


def astar_path(
    start: Coordinate,
    goal: Coordinate,
    grid: dict[tuple[int, int], Cell],
    blocked: set[tuple[int, int]],
) -> list[Coordinate] | None:
    if start.x == goal.x and start.y == goal.y:
        return [start]

    frontier: list[tuple[int, int, Coordinate, list[Coordinate]]] = []
    # (f_score, tie_breaker, current_pos, path)
    heapq.heappush(frontier, (start.manhattan_distance(goal), 0, start, [start]))
    visited: set[tuple[int, int]] = {(start.x, start.y)}
    tie = 0

    while frontier:
        f, _, current, path = heapq.heappop(frontier)
        if current.x == goal.x and current.y == goal.y:
            return path

        for neighbor in _get_flow_neighbors(current, grid, blocked):
            n_key = (neighbor.x, neighbor.y)
            if n_key not in visited:
                visited.add(n_key)
                g = len(path)
                h = neighbor.manhattan_distance(goal)
                tie += 1
                heapq.heappush(frontier, (g + h, tie, neighbor, path + [neighbor]))

    return None


class AStarFlowPlanner:
    def __init__(
        self,
        replan_wait_ticks: int = 10,
        yield_wait_ticks: int = 30,
        deadlock_threshold_ticks: int = 60,
    ) -> None:
        self.replan_wait_ticks = replan_wait_ticks
        self.yield_wait_ticks = yield_wait_ticks
        self.deadlock_threshold_ticks = deadlock_threshold_ticks
        self.deadlock_incidents: int = 0
        self._cached_paths: dict[str, list[Coordinate]] = {}

    def plan_intents(
        self,
        robots: list[Robot],
        destinations: dict[str, Coordinate],
        layout: Layout,
        blocked_cells: set[tuple[int, int]],
        rng: np.random.Generator,
        current_tick: int = 0,
        per_robot_avoid: dict[str, set[tuple[int, int]]] | None = None,
        priority_robots: set[str] | None = None,
    ) -> tuple[dict[str, MoveIntent], list[str]]:
        grid = {(c.pos.x, c.pos.y): c for c in layout.cells}
        intents: dict[str, MoveIntent] = {}
        deadlocked_robot_ids: list[str] = []
        prio_set = priority_robots or set()

        # Sort robots by priority: AI priority boost first, longest blocked first, then ID
        sorted_robots = sorted(
            robots,
            key=lambda r: (0 if r.robot_id in prio_set else 1, -r.blocked_ticks, r.robot_id),
        )

        robot_cells = {(r.cell.x, r.cell.y) for r in robots}
        # Hard obstacles: blocked cells, faulted robots, and actively charging robots
        hard_obstacles = set(blocked_cells)
        for r in robots:
            if r.state in (RobotState.UNAVAILABLE, RobotState.CHARGING):
                hard_obstacles.add((r.cell.x, r.cell.y))

        for robot in sorted_robots:
            robot_extra_avoid = (
                per_robot_avoid.get(robot.robot_id, set()) if per_robot_avoid else set()
            )
            robot_hard_obs = hard_obstacles | robot_extra_avoid
            target = destinations.get(robot.robot_id)
            if not target or (robot.cell.x == target.x and robot.cell.y == target.y):
                # Idle or already arrived
                self._cached_paths.pop(robot.robot_id, None)
                intents[robot.robot_id] = MoveIntent(robot_id=robot.robot_id, to_cell=robot.cell)
                continue

            # Check deadlock threshold (flag once when crossing threshold)
            if robot.blocked_ticks == self.deadlock_threshold_ticks:
                self.deadlock_incidents += 1
                deadlocked_robot_ids.append(robot.robot_id)

            other_robots = robot_cells - {(robot.cell.x, robot.cell.y)}

            # Fast path: check cached path hit if unblocked
            cached = self._cached_paths.get(robot.robot_id)
            if (
                cached
                and len(cached) > 1
                and cached[0].x == robot.cell.x
                and cached[0].y == robot.cell.y
                and cached[-1].x == target.x
                and cached[-1].y == target.y
                and (cached[1].x, cached[1].y) not in robot_hard_obs
                and (cached[1].x, cached[1].y) not in other_robots
                and robot.blocked_ticks < self.replan_wait_ticks
            ):
                next_cell = cached[1]
                self._cached_paths[robot.robot_id] = cached[1:]
                intents[robot.robot_id] = MoveIntent(
                    robot_id=robot.robot_id,
                    to_cell=next_cell,
                    progress_permille=1000,
                )
                continue

            # Avoid other robots' cells to path around congestion
            dyn_blocked = set(robot_hard_obs) | other_robots
            dyn_blocked.discard((target.x, target.y))

            # Replan path avoiding other robots
            path = astar_path(robot.cell, target, grid, dyn_blocked)
            if not path or len(path) <= 1:
                # Fallback: avoid hard obstacles only
                dyn_blocked_soft = set(robot_hard_obs)
                dyn_blocked_soft.discard((target.x, target.y))
                path = astar_path(robot.cell, target, grid, dyn_blocked_soft)

            if path and len(path) > 1:
                self._cached_paths[robot.robot_id] = path[1:]
                next_cell = path[1]
                # If next cell is occupied by another robot, do not attempt to walk into it
                if (next_cell.x, next_cell.y) in other_robots:
                    self._cached_paths.pop(robot.robot_id, None)
                    # Look for immediate adjacent walkable bypass toward target
                    free_neighbors = _get_flow_neighbors(
                        robot.cell, grid, set(robot_hard_obs) | other_robots
                    )
                    if free_neighbors:
                        bypass_cell = min(free_neighbors, key=lambda n: n.manhattan_distance(target))
                        intents[robot.robot_id] = MoveIntent(
                            robot_id=robot.robot_id, to_cell=bypass_cell
                        )
                        continue

                    # If trapped with no bypass, wait in place cleanly without causing safety denial
                    intents[robot.robot_id] = MoveIntent(robot_id=robot.robot_id, to_cell=robot.cell)
                    continue

                intents[robot.robot_id] = MoveIntent(
                    robot_id=robot.robot_id,
                    to_cell=next_cell,
                    progress_permille=1000,
                )
            else:
                # If blocked and reached yield threshold, try adjacent walkable yield cell
                if robot.blocked_ticks >= self.yield_wait_ticks:
                    neighbors = _get_flow_neighbors(
                        robot.cell, grid, set(robot_hard_obs) | other_robots
                    )
                    if neighbors:
                        yield_cell = neighbors[rng.integers(0, len(neighbors))]
                        intents[robot.robot_id] = MoveIntent(
                            robot_id=robot.robot_id, to_cell=yield_cell
                        )
                        continue

                # Stay put and wait
                intents[robot.robot_id] = MoveIntent(robot_id=robot.robot_id, to_cell=robot.cell)

        return intents, deadlocked_robot_ids


from robofleet.registry.generic import planner_registry

planner_registry.register("astar_flow", AStarFlowPlanner)
