"""SafetyGuard: Non-bypassable physical movement boundary (SR-7, CA-3).
The ONLY code in RoboFleet permitted to mutate a robot's cell.
Enforces physical invariants: no collisions, no cell sharing, no swaps, flow directions, emergency stop.
"""

from __future__ import annotations

from typing import Any

from robofleet.contracts.common import Coordinate, Heading
from robofleet.contracts.layout import Cell, Flow, Layout
from robofleet.contracts.robot import MotionProgress, Robot, RobotState


class SafetyViolation(Exception):
    """Raised whenever an invariant is physically broken or attempted to be bypassed."""

    pass


class MoveIntent:
    """Proposal from a planner. Planners NEVER mutate coordinates directly."""

    def __init__(self, robot_id: str, to_cell: Coordinate, progress_permille: int = 1000) -> None:
        self.robot_id = robot_id
        self.to_cell = to_cell
        self.progress_permille = progress_permille


class SafetyGuard:
    def __init__(self, layout: Layout) -> None:
        self.layout = layout
        self.grid: dict[tuple[int, int], Cell] = {(c.pos.x, c.pos.y): c for c in layout.cells}

        # State tracking
        self.e_stop_all: bool = False
        self.e_stop_robots: set[str] = set()
        self.e_stop_zones: set[str] = set()
        self.blocked_cells: set[tuple[int, int]] = set()

    def set_emergency_stop(self, scope: str = "all", target_id: str | None = None) -> None:
        if scope == "all":
            self.e_stop_all = True
        elif scope == "robot" and target_id:
            self.e_stop_robots.add(target_id)
        elif scope == "zone" and target_id:
            self.e_stop_zones.add(target_id)

    def resume_emergency_stop(self, scope: str = "all", target_id: str | None = None) -> None:
        if scope == "all":
            self.e_stop_all = False
            self.e_stop_robots.clear()
            self.e_stop_zones.clear()
        elif scope == "robot" and target_id:
            self.e_stop_robots.discard(target_id)
        elif scope == "zone" and target_id:
            self.e_stop_zones.discard(target_id)

    def block_cells(self, cells: list[Coordinate]) -> None:
        for c in cells:
            self.blocked_cells.add((c.x, c.y))

    def unblock_cells(self, cells: list[Coordinate]) -> None:
        for c in cells:
            self.blocked_cells.discard((c.x, c.y))

    def is_cell_walkable(self, pos: Coordinate) -> bool:
        if (pos.x, pos.y) in self.blocked_cells:
            return False
        cell = self.grid.get((pos.x, pos.y))
        return cell is not None and cell.is_walkable

    def check_flow_compliance(self, from_pos: Coordinate, to_pos: Coordinate) -> bool:
        if from_pos.x == to_pos.x and from_pos.y == to_pos.y:
            return True
        from_cell = self.grid.get((from_pos.x, from_pos.y))
        if not from_cell:
            return False
        if from_cell.flow == Flow.BOTH:
            return True
        dx = to_pos.x - from_pos.x
        dy = to_pos.y - from_pos.y
        if dx == 1 and dy == 0:
            return from_cell.flow in (Flow.E, Flow.EW)
        if dx == -1 and dy == 0:
            return from_cell.flow in (Flow.W, Flow.EW)
        if dx == 0 and dy == 1:
            return from_cell.flow in (Flow.S, Flow.NS)
        if dx == 0 and dy == -1:
            return from_cell.flow in (Flow.N, Flow.NS)
        return False

    def validate_and_apply_moves(
        self,
        robots: list[Robot],
        intents: dict[str, MoveIntent],
    ) -> list[dict[str, Any]]:
        """Atomically validates move intents and commits valid moves.
        Guarantees zero shared cells, zero swaps, flow compliance, and e-stop enforcement.
        """
        denials: list[dict[str, Any]] = []
        robot_map = {r.robot_id: r for r in robots}

        # 1. Check E-stop conditions
        active_intents: dict[str, MoveIntent] = {}
        for r_id, intent in intents.items():
            robot = robot_map.get(r_id)
            if not robot:
                continue

            # Unavailable or faulted robots cannot move
            if robot.state == RobotState.UNAVAILABLE or robot.fault is not None:
                denials.append({"robot_id": r_id, "reason": "ROBOT_UNAVAILABLE_OR_FAULTED"})
                continue

            # Check E-stop
            curr_cell = self.grid.get((robot.cell.x, robot.cell.y))
            curr_zone = curr_cell.zone if curr_cell else None
            if (
                self.e_stop_all
                or r_id in self.e_stop_robots
                or (curr_zone and curr_zone in self.e_stop_zones)
            ):
                denials.append({"robot_id": r_id, "reason": "EMERGENCY_STOP_ACTIVE"})
                continue

            active_intents[r_id] = intent

        # 2. Check destination validity & flow rules
        valid_intents: dict[str, MoveIntent] = {}
        for r_id, intent in active_intents.items():
            robot = robot_map[r_id]
            dest = intent.to_cell

            # Same cell (staying put) is always valid
            if dest.x == robot.cell.x and dest.y == robot.cell.y:
                valid_intents[r_id] = intent
                continue

            # Must be adjacent (distance = 1)
            if dest.manhattan_distance(robot.cell) != 1:
                denials.append({"robot_id": r_id, "reason": "NON_ADJACENT_MOVE"})
                continue

            # Walkable & not blocked
            if not self.is_cell_walkable(dest):
                denials.append({"robot_id": r_id, "reason": "DESTINATION_NOT_WALKABLE_OR_BLOCKED"})
                continue

            # Flow compliance
            if not self.check_flow_compliance(robot.cell, dest):
                denials.append({"robot_id": r_id, "reason": "FLOW_RULE_VIOLATION"})
                continue

            valid_intents[r_id] = intent

        # 3. Collision and Swap Prevention:
        # A moving robot reserves both its current and next cell.
        # Zero sharing and zero swapping by construction.
        current_occupied_cells: dict[tuple[int, int], str] = {
            (r.cell.x, r.cell.y): r.robot_id for r in robots
        }
        reserved_target_cells: set[tuple[int, int]] = set()
        approved_intents: dict[str, MoveIntent] = {}

        # Process intents deterministically sorted by priority
        for r_id in sorted(valid_intents.keys()):
            intent = valid_intents[r_id]
            robot = robot_map[r_id]
            target_tuple = (intent.to_cell.x, intent.to_cell.y)
            origin_tuple = (robot.cell.x, robot.cell.y)

            # If staying put, intent is already satisfied
            if target_tuple == origin_tuple:
                approved_intents[r_id] = intent
                continue

            # Check if target cell is currently occupied by any robot
            occupant = current_occupied_cells.get(target_tuple)
            if occupant is not None and occupant != r_id:
                denials.append({"robot_id": r_id, "reason": "DESTINATION_CURRENTLY_OCCUPIED"})
                continue

            # Check if target cell is already reserved by another mover this tick
            if target_tuple in reserved_target_cells:
                denials.append({"robot_id": r_id, "reason": "DESTINATION_ALREADY_RESERVED"})
                continue

            # Approved to move: reserve target
            reserved_target_cells.add(target_tuple)
            approved_intents[r_id] = intent

        # 4. Commit approved moves (The only point where robot.cell is mutated!)
        for r_id in sorted(approved_intents.keys()):
            intent = approved_intents[r_id]
            robot = robot_map[r_id]
            if intent.to_cell.x != robot.cell.x or intent.to_cell.y != robot.cell.y:
                # Update heading
                dx = intent.to_cell.x - robot.cell.x
                dy = intent.to_cell.y - robot.cell.y
                if dx == 1:
                    robot.heading = Heading.E
                elif dx == -1:
                    robot.heading = Heading.W
                elif dy == 1:
                    robot.heading = Heading.S
                elif dy == -1:
                    robot.heading = Heading.N

                robot.motion = MotionProgress(
                    from_cell=robot.cell,
                    to_cell=intent.to_cell,
                    progress_permille=intent.progress_permille,
                )
                robot.cell = intent.to_cell
                robot.state = RobotState.MOVING
            else:
                robot.motion = None
                if robot.state == RobotState.MOVING:
                    robot.state = RobotState.IDLE

        # Update blocked robots count and state for unapproved / denied intents
        denied_robot_ids = {d["robot_id"] for d in denials}
        for r in robots:
            if r.robot_id in denied_robot_ids:
                r.motion = None
                if r.state not in (RobotState.UNAVAILABLE, RobotState.CHARGING):
                    r.state = RobotState.WAITING
                r.blocked_ticks += 1
            else:
                r.blocked_ticks = 0

        # Post-condition self-check: verify 0 shared cells across all robots
        cells_occupied = [r.cell.as_tuple() for r in robots]
        if len(cells_occupied) != len(set(cells_occupied)):
            raise SafetyViolation(
                f"CRITICAL SAFETY VIOLATION: Duplicate robot cells detected: {cells_occupied}"
            )

        return denials
