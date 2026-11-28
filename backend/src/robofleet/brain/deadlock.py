"""Intelligent Multi-Robot Deadlock Detection and Recovery Analyzer.

Distinguishes normal brief waiting from genuine operational conflicts:
- Facing corridors (2-robot head-on lock)
- Intersection conflicts (converging on shared junction)
- Circular dependency cycles (3+ robots waiting in a ring)
- Blocked routes with and without valid detours
- Permanently stuck robots requiring human escalation
"""

from __future__ import annotations

from typing import Any, Literal

from robofleet.contracts.brain import BriefDeadlockInfo
from robofleet.contracts.common import Coordinate
from robofleet.contracts.layout import Cell, Layout
from robofleet.contracts.order import OrderStatus
from robofleet.contracts.robot import Robot, RobotState
from robofleet.sim.planner import _get_flow_neighbors, astar_path


def _infer_next_step(
    robot: Robot,
    dest: Coordinate | None,
    grid: dict[tuple[int, int], Cell],
    hard_blocked: set[tuple[int, int]],
    planner: Any,
) -> tuple[Coordinate | None, bool]:
    """Infer intended next cell and whether a valid route to dest exists."""
    if dest is None or (robot.cell.x == dest.x and robot.cell.y == dest.y):
        return None, True

    # 1. Check reservation/flow planner cached paths first
    for cache_attr in ("planned_paths", "_cached_paths"):
        cache = getattr(planner, cache_attr, None)
        if isinstance(cache, dict):
            path = cache.get(robot.robot_id)
            if isinstance(path, list) and len(path) >= 2:
                # Find step immediately after current cell (or index 0 if consumed)
                if path[0].x == robot.cell.x and path[0].y == robot.cell.y:
                    return path[1], True
                if path[0].manhattan_distance(robot.cell) == 1:
                    return path[0], True

    # 2. Compute flow-compliant A* avoiding hard blocks (excluding occupied moving robots)
    path = astar_path(robot.cell, dest, grid, hard_blocked)
    if path and len(path) >= 2:
        return path[1], True
    return None, False


def _robot_priority_score(
    robot: Robot,
    orders: list[Any],
    low_battery_thresh: float,
) -> tuple[float, int, str]:
    """Higher tuple (negated in sort? No, higher wins priority) determines who passes first."""
    score = 0.0
    # 1. Critical battery gets preference to reach charger safely
    if robot.battery_pct <= low_battery_thresh:
        score += 40.0
    # 2. Carrying payload bin / urgent order SLA urgency
    if robot.carrying:
        score += 15.0
    for ord_obj in orders:
        st = getattr(ord_obj, "status", None)
        if st in (OrderStatus.HANDED_OVER, OrderStatus.CANCELLED, OrderStatus.FAILED):
            continue
        assigned = getattr(ord_obj, "assigned_robot_ids", []) or []
        if robot.robot_id in assigned:
            prio = float(getattr(ord_obj, "priority", 1))
            score += prio * 5.0
            if getattr(ord_obj, "at_risk", False):
                score += 30.0
            break
    # 3. Waiting-time aging prevents permanent starvation of yielded robots
    score += min(25.0, float(robot.blocked_ticks) * 0.5)
    return (score, robot.blocked_ticks, robot.robot_id)


def _find_safe_yield_cell(
    robot: Robot,
    grid: dict[tuple[int, int], Cell],
    occupied_cells: set[tuple[int, int]],
    hard_blocked: set[tuple[int, int]],
    priority_next_cell: Coordinate | None = None,
) -> Coordinate | None:
    """Find an adjacent walkable, unoccupied cell adhering to warehouse flow rules."""
    avoid = set(hard_blocked) | (occupied_cells - {(robot.cell.x, robot.cell.y)})
    neighbors = _get_flow_neighbors(robot.cell, grid, avoid)
    if not neighbors:
        return None
    if priority_next_cell is not None:
        non_blocking = [
            n for n in neighbors if (n.x, n.y) != (priority_next_cell.x, priority_next_cell.y)
        ]
        if non_blocking:
            return non_blocking[0]
    return neighbors[0]


class DeadlockAnalyzer:
    """Detects and classifies multi-robot conflicts and proposes grounded recovery plans."""

    @classmethod
    def analyze(
        cls,
        engine: Any,
        no_progress_ticks: int = 12,
    ) -> list[BriefDeadlockInfo]:
        layout: Layout | None = getattr(engine, "layout", None)
        robots: list[Robot] = list(getattr(engine, "robots", []))
        if not layout or not robots:
            return []

        grid: dict[tuple[int, int], Cell] = {(c.pos.x, c.pos.y): c for c in layout.cells}
        planner = getattr(engine, "planner", None)
        orders = list(getattr(engine, "orders", []))
        safety_guard = getattr(engine, "safety_guard", None)
        blocked_cells: set[tuple[int, int]] = (
            set(getattr(safety_guard, "blocked_cells", set())) if safety_guard else set()
        )
        destinations: dict[str, Coordinate] = dict(getattr(engine, "last_destinations", {}))

        # Fill destinations from TaskManager if engine hasn't stepped with dispatcher yet
        task_mgr = getattr(engine, "task_mgr", None)
        if not destinations and task_mgr:
            destinations = dict(getattr(task_mgr, "robot_target_cells", {}))

        battery_cfg = getattr(getattr(engine, "config", None), "battery", None)
        low_bat = float(getattr(battery_cfg, "low_battery_threshold", 20.0)) if battery_cfg else 20.0

        hard_obstacles = set(blocked_cells)
        for r in robots:
            if r.state in (RobotState.UNAVAILABLE, RobotState.CHARGING) or r.fault is not None:
                hard_obstacles.add((r.cell.x, r.cell.y))

        robot_by_id = {r.robot_id: r for r in robots}
        occupied_by: dict[tuple[int, int], str] = {(r.cell.x, r.cell.y): r.robot_id for r in robots}
        occupied_set = set(occupied_by.keys())

        next_step: dict[str, Coordinate | None] = {}
        has_route: dict[str, bool] = {}
        wait_for: dict[str, str] = {}

        # Merge reservation planner's wait-for graph if available
        planner_wfg = getattr(planner, "wait_for_graph", None)
        if isinstance(planner_wfg, dict):
            for rid, blk_id in planner_wfg.items():
                if rid in robot_by_id and blk_id in robot_by_id and rid != blk_id:
                    wait_for[rid] = blk_id

        for r in robots:
            if r.state in (RobotState.UNAVAILABLE, RobotState.CHARGING) or r.fault is not None:
                next_step[r.robot_id] = None
                has_route[r.robot_id] = True
                continue
            dest = destinations.get(r.robot_id)
            nxt, valid = _infer_next_step(r, dest, grid, hard_obstacles, planner)
            next_step[r.robot_id] = nxt
            has_route[r.robot_id] = valid
            if nxt is not None:
                occ = occupied_by.get((nxt.x, nxt.y))
                if occ and occ != r.robot_id:
                    wait_for[r.robot_id] = occ

        conflicts: list[BriefDeadlockInfo] = []
        handled_robots: set[str] = set()

        # 1. Detect Cycles in wait_for (covers 2-robot facing deadlocks & 3+ robot circular deadlocks)
        for start_rid in sorted(wait_for.keys()):
            if start_rid in handled_robots:
                continue
            chain: list[str] = []
            visited: set[str] = set()
            curr: str | None = start_rid
            while curr and curr in wait_for and curr not in visited:
                visited.add(curr)
                chain.append(curr)
                curr = wait_for.get(curr)

            if curr and curr in visited:
                cycle_start = chain.index(curr)
                cycle = chain[cycle_start:]
                cycle_robots = [robot_by_id[rid] for rid in cycle if rid in robot_by_id]
                if len(cycle_robots) < 2:
                    continue

                max_blk = max(r.blocked_ticks for r in cycle_robots)
                # Require corroborating evidence: either stalled >= threshold OR confirmed mutual swap lock with >=2 wait ticks
                head_on_locked = len(cycle) == 2 and all(r.blocked_ticks >= 2 for r in cycle_robots)
                if max_blk < no_progress_ticks and not head_on_locked:
                    continue

                # Determine Priority Robot vs Best Yielding Robot
                scored = sorted(
                    cycle_robots,
                    key=lambda r: _robot_priority_score(r, orders, low_bat),
                    reverse=True,
                )
                prio_robot = scored[0]
                prio_next = next_step.get(prio_robot.robot_id)

                yield_robot: Robot | None = None
                yield_cell: Coordinate | None = None
                # Choose lowest priority cycle member that has a valid safe yield cell
                for candidate in reversed(scored[1:]):
                    y_cell = _find_safe_yield_cell(
                        candidate, grid, occupied_set, hard_obstacles, prio_next
                    )
                    if y_cell is not None:
                        yield_robot = candidate
                        yield_cell = y_cell
                        break

                no_route = yield_robot is None
                if len(cycle) == 2:
                    c_type: Literal[
                        "facing_corridor",
                        "intersection_conflict",
                        "circular_deadlock",
                        "blocked_route",
                        "stuck_no_route",
                    ] = "facing_corridor"
                else:
                    c_type = "circular_deadlock"

                conflict_cells = [r.cell for r in cycle_robots]
                desc = (
                    f"{c_type.replace('_', ' ').title()} involving {' -> '.join(cycle)} -> {cycle[0]} "
                    f"(max stalled {max_blk} ticks)."
                )
                if yield_robot and yield_cell:
                    desc += f" Recommend {yield_robot.robot_id} yield to ({yield_cell.x},{yield_cell.y}) so {prio_robot.robot_id} passes."
                else:
                    desc += " No adjacent escape cell available; escalate for manual clearing."

                conflicts.append(
                    BriefDeadlockInfo(
                        conflict_id=f"DL-{prio_robot.robot_id}-{len(conflicts) + 1}",
                        conflict_type=c_type,
                        robots_involved=[r.robot_id for r in cycle_robots],
                        cycle_chain=cycle + [cycle[0]],
                        conflict_cells=conflict_cells,
                        recommended_yield_robot=yield_robot.robot_id if yield_robot else None,
                        recommended_yield_cell=yield_cell,
                        recommended_priority_robot=prio_robot.robot_id,
                        no_route_available=no_route,
                        max_blocked_ticks=max_blk,
                        description=desc,
                    )
                )
                handled_robots.update(r.robot_id for r in cycle_robots)

        # 2. Detect Intersection Conflicts (2+ stalled robots targeting same next cell)
        target_buckets: dict[tuple[int, int], list[Robot]] = {}
        for r in robots:
            if r.robot_id in handled_robots or r.blocked_ticks < no_progress_ticks:
                continue
            nxt = next_step.get(r.robot_id)
            if nxt is not None:
                target_buckets.setdefault((nxt.x, nxt.y), []).append(r)

        for cell_tup, contending in sorted(target_buckets.items()):
            if len(contending) >= 2:
                scored = sorted(
                    contending,
                    key=lambda r: _robot_priority_score(r, orders, low_bat),
                    reverse=True,
                )
                prio_robot = scored[0]
                yield_robot = None
                yield_cell = None
                for cand in reversed(scored[1:]):
                    y_cell = _find_safe_yield_cell(
                        cand, grid, occupied_set, hard_obstacles, Coordinate(x=cell_tup[0], y=cell_tup[1])
                    )
                    if y_cell is not None:
                        yield_robot = cand
                        yield_cell = y_cell
                        break

                conflicts.append(
                    BriefDeadlockInfo(
                        conflict_id=f"INT-{cell_tup[0]}-{cell_tup[1]}",
                        conflict_type="intersection_conflict",
                        robots_involved=[r.robot_id for r in contending],
                        conflict_cells=[Coordinate(x=cell_tup[0], y=cell_tup[1])],
                        recommended_yield_robot=yield_robot.robot_id if yield_robot else None,
                        recommended_yield_cell=yield_cell,
                        recommended_priority_robot=prio_robot.robot_id,
                        no_route_available=yield_robot is None,
                        max_blocked_ticks=max(r.blocked_ticks for r in contending),
                        description=(
                            f"Intersection contention at {cell_tup} among {[r.robot_id for r in contending]}. "
                            f"Grant intersection to {prio_robot.robot_id}."
                        ),
                    )
                )
                handled_robots.update(r.robot_id for r in contending)

        # 3. Detect Blocked / Permanently Stuck Robots beyond no_progress_ticks
        for r in robots:
            if r.robot_id in handled_robots or r.state in (RobotState.UNAVAILABLE, RobotState.CHARGING):
                continue
            if r.blocked_ticks >= no_progress_ticks:
                dest = destinations.get(r.robot_id)
                route_ok = has_route.get(r.robot_id, True)
                nxt = next_step.get(r.robot_id)
                blocker_id = occupied_by.get((nxt.x, nxt.y)) if nxt else None

                # Check if robot can detour around other stalled robots
                other_occupied = occupied_set - {(r.cell.x, r.cell.y)}
                alt_path = (
                    astar_path(r.cell, dest, grid, hard_obstacles | other_occupied)
                    if dest
                    else None
                )
                if not route_ok or alt_path is None:
                    # Check adjacent yield escape
                    y_cell = _find_safe_yield_cell(r, grid, occupied_set, hard_obstacles)
                    c_type_stuck: Literal[
                        "facing_corridor",
                        "intersection_conflict",
                        "circular_deadlock",
                        "blocked_route",
                        "stuck_no_route",
                    ] = "stuck_no_route" if not route_ok else "blocked_route"
                    conflicts.append(
                        BriefDeadlockInfo(
                            conflict_id=f"BLK-{r.robot_id}",
                            conflict_type=c_type_stuck,
                            robots_involved=[r.robot_id] + ([blocker_id] if blocker_id else []),
                            conflict_cells=[r.cell],
                            recommended_yield_robot=r.robot_id if y_cell else None,
                            recommended_yield_cell=y_cell,
                            no_route_available=(not route_ok and y_cell is None),
                            max_blocked_ticks=r.blocked_ticks,
                            description=(
                                f"AMR {r.robot_id} stalled for {r.blocked_ticks} ticks "
                                f"({'no reachable route' if not route_ok else 'corridor blocked'})."
                            ),
                        )
                    )
                elif blocker_id:
                    y_cell = _find_safe_yield_cell(r, grid, occupied_set, hard_obstacles)
                    conflicts.append(
                        BriefDeadlockInfo(
                            conflict_id=f"WAIT-{r.robot_id}",
                            conflict_type="blocked_route",
                            robots_involved=[r.robot_id, blocker_id],
                            conflict_cells=[r.cell],
                            recommended_yield_robot=r.robot_id if y_cell else None,
                            recommended_yield_cell=y_cell,
                            recommended_priority_robot=blocker_id,
                            no_route_available=False,
                            max_blocked_ticks=r.blocked_ticks,
                            description=f"AMR {r.robot_id} waiting behind {blocker_id} for {r.blocked_ticks} ticks; detour available.",
                        )
                    )

        return conflicts
