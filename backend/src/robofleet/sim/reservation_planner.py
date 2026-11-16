"""Cooperative Space-Time Reservation A* Planner (CA-5 / Phase 3).
Computes collision-free trajectories respecting dark store flow constraints,
maintains a rolling space-time reservation table, and deterministically resolves wait-for deadlocks.
"""

from __future__ import annotations

import heapq
from typing import Any
import numpy as np

from robofleet.contracts.common import Coordinate, Heading
from robofleet.contracts.layout import Cell, Flow, Layout
from robofleet.contracts.robot import Robot, RobotState
from robofleet.sim.safety import MoveIntent


class ReservationTable:
    """Rolling space-time reservation table preventing vertex and edge swap collisions."""

    def __init__(self, horizon: int = 25) -> None:
        self.horizon = horizon
        # (x, y, tick) -> robot_id
        self._vertex_res: dict[tuple[int, int, int], str] = {}
        # (from_x, from_y, to_x, to_y, tick) -> robot_id
        self._edge_res: dict[tuple[int, int, int, int, int], str] = {}

    def is_vertex_free(self, x: int, y: int, tick: int, robot_id: str) -> bool:
        occupant = self._vertex_res.get((x, y, tick))
        return occupant is None or occupant == robot_id

    def is_edge_free(self, fx: int, fy: int, tx: int, ty: int, tick: int, robot_id: str) -> bool:
        # Check reverse edge swap: another robot moving tx,ty -> fx,fy at same tick
        reverse_occupant = self._edge_res.get((tx, ty, fx, fy, tick))
        return reverse_occupant is None or reverse_occupant == robot_id

    def reserve(self, robot_id: str, trajectory: list[tuple[Coordinate, int]]) -> None:
        for i, (pos, tick) in enumerate(trajectory):
            self._vertex_res[(pos.x, pos.y, tick)] = robot_id
            if i > 0:
                prev_pos, prev_tick = trajectory[i - 1]
                self._edge_res[(prev_pos.x, prev_pos.y, pos.x, pos.y, prev_tick)] = robot_id

    def clear_robot(self, robot_id: str) -> None:
        self._vertex_res = {k: v for k, v in self._vertex_res.items() if v != robot_id}
        self._edge_res = {k: v for k, v in self._edge_res.items() if v != robot_id}

    def prune_old_ticks(self, current_tick: int) -> None:
        self._vertex_res = {k: v for k, v in self._vertex_res.items() if k[2] >= current_tick}
        self._edge_res = {k: v for k, v in self._edge_res.items() if k[4] >= current_tick}


class ReservationAStarPlanner:
    """Cooperative Space-Time A* with wait-for graph cycle detection."""

    def __init__(
        self,
        horizon_ticks: int = 25,
        replan_wait_ticks: int = 8,
        yield_wait_ticks: int = 20,
        deadlock_threshold_ticks: int = 40,
    ) -> None:
        self.horizon_ticks = horizon_ticks
        self.replan_wait_ticks = replan_wait_ticks
        self.yield_wait_ticks = yield_wait_ticks
        self.deadlock_threshold_ticks = deadlock_threshold_ticks
        self.deadlock_incidents: int = 0

        self.table = ReservationTable(horizon=horizon_ticks)
        self.planned_paths: dict[str, list[Coordinate]] = {}
        self.wait_for_graph: dict[str, str] = {}  # robot_id -> waiting_for_robot_id

    def _get_flow_neighbors(
        self,
        curr: Coordinate,
        grid: dict[tuple[int, int], Cell],
        blocked: set[tuple[int, int]],
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

    def _space_time_astar(
        self,
        robot: Robot,
        goal: Coordinate,
        grid: dict[tuple[int, int], Cell],
        blocked: set[tuple[int, int]],
        start_tick: int,
    ) -> list[Coordinate] | None:
        start = robot.cell
        if start.x == goal.x and start.y == goal.y:
            return [start]

        # Priority queue item: (f_score, tie_breaker, current_coord, tick_offset, path)
        frontier: list[tuple[int, int, Coordinate, int, list[Coordinate]]] = []
        start_h = start.manhattan_distance(goal)
        heapq.heappush(frontier, (start_h, 0, start, 0, [start]))

        visited: set[tuple[int, int, int]] = {(start.x, start.y, 0)}
        tie = 0

        while frontier:
            f, _, current, t_offset, path = heapq.heappop(frontier)
            curr_tick = start_tick + t_offset

            if current.x == goal.x and current.y == goal.y:
                return path

            if t_offset >= self.horizon_ticks:
                # Return partial progress towards goal within horizon
                return path

            next_t_offset = t_offset + 1
            next_tick = curr_tick + 1

            # Candidate 1: Wait in place (if cell is free at next tick)
            if self.table.is_vertex_free(current.x, current.y, next_tick, robot.robot_id):
                v_key = (current.x, current.y, next_t_offset)
                if v_key not in visited:
                    visited.add(v_key)
                    g = next_t_offset + 1  # slight penalty for waiting
                    h = current.manhattan_distance(goal)
                    tie += 1
                    heapq.heappush(frontier, (g + h, tie, current, next_t_offset, path + [current]))

            # Candidates: Move to flow neighbors
            for neighbor in self._get_flow_neighbors(current, grid, blocked):
                if not self.table.is_vertex_free(neighbor.x, neighbor.y, next_tick, robot.robot_id):
                    continue
                if not self.table.is_edge_free(current.x, current.y, neighbor.x, neighbor.y, curr_tick, robot.robot_id):
                    continue

                v_key = (neighbor.x, neighbor.y, next_t_offset)
                if v_key not in visited:
                    visited.add(v_key)
                    g = next_t_offset
                    h = neighbor.manhattan_distance(goal)
                    tie += 1
                    heapq.heappush(frontier, (g + h, tie, neighbor, next_t_offset, path + [neighbor]))

        return None

    def plan_intents(
        self,
        robots: list[Robot],
        destinations: dict[str, Coordinate],
        layout: Layout,
        blocked_cells: set[tuple[int, int]],
        rng: np.random.Generator,
        current_tick: int = 0,
    ) -> tuple[dict[str, MoveIntent], list[str]]:
        self.table.prune_old_ticks(current_tick)
        grid_lookup: dict[tuple[int, int], Cell] = {c.pos.as_tuple(): c for c in layout.cells}
        intents: dict[str, MoveIntent] = {}
        deadlocked_robots: list[str] = []

        # Deterministic sorting of robots by age / battery / id
        ordered_robots = sorted(
            robots,
            key=lambda r: (r.blocked_ticks, -r.battery_pct, r.robot_id),
            reverse=True,
        )

        occupied_now = {r.cell.as_tuple(): r.robot_id for r in robots}

        for robot in ordered_robots:
            r_id = robot.robot_id
            goal = destinations.get(r_id, robot.cell)

            # Fast path: already at goal
            if robot.cell.as_tuple() == goal.as_tuple():
                intents[r_id] = MoveIntent(robot_id=r_id, to_cell=robot.cell)
                self.planned_paths.pop(r_id, None)
                self.wait_for_graph.pop(r_id, None)
                continue

            # Replan path if needed
            cached_path = self.planned_paths.get(r_id)
            needs_replan = (
                cached_path is None
                or len(cached_path) < 2
                or cached_path[-1].as_tuple() != goal.as_tuple()
                or (len(cached_path) > 0 and cached_path[0].as_tuple() != robot.cell.as_tuple())
                or (len(cached_path) > 1 and cached_path[1].as_tuple() in blocked_cells)
                or robot.blocked_ticks >= self.replan_wait_ticks
            )

            if needs_replan:
                self.table.clear_robot(r_id)
                new_path = self._space_time_astar(
                    robot=robot,
                    goal=goal,
                    grid=grid_lookup,
                    blocked=blocked_cells,
                    start_tick=current_tick,
                )
                if new_path and len(new_path) >= 1:
                    self.planned_paths[r_id] = new_path
                    traj = [(p, current_tick + idx) for idx, p in enumerate(new_path)]
                    self.table.reserve(r_id, traj)
                else:
                    self.planned_paths[r_id] = [robot.cell]

            path = self.planned_paths.get(r_id, [robot.cell])
            # Consume redundant stay-in-place prefix
            while len(path) > 1 and path[0].as_tuple() == robot.cell.as_tuple() and path[1].as_tuple() == robot.cell.as_tuple():
                path.pop(0)

            if len(path) > 1:
                next_cell = path[1]
                occupant = occupied_now.get(next_cell.as_tuple())
                if occupant and occupant != r_id:
                    self.wait_for_graph[r_id] = occupant
                else:
                    self.wait_for_graph.pop(r_id, None)

                intents[r_id] = MoveIntent(robot_id=r_id, to_cell=next_cell, progress_permille=1000)
                path.pop(0)
            else:
                intents[r_id] = MoveIntent(robot_id=r_id, to_cell=robot.cell, progress_permille=1000)

        # Detect wait-for graph cycles (deadlocks)
        for r_id in list(self.wait_for_graph.keys()):
            visited_chain = []
            curr: str | None = r_id
            while curr and curr in self.wait_for_graph:
                if curr in visited_chain:
                    # Deadlock cycle detected!
                    self.deadlock_incidents += 1
                    deadlocked_robots.append(curr)
                    # Break cycle: lowest priority yields by clearing path and replanning with detour
                    self.planned_paths.pop(curr, None)
                    break
                visited_chain.append(curr)
                curr = self.wait_for_graph.get(curr)

        return intents, deadlocked_robots


from robofleet.registry.generic import planner_registry

planner_registry.register("reservation_astar", ReservationAStarPlanner)
