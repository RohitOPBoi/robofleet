"""RoboFleet Core Simulation Engine.
Implements the strict 9-step tick execution contract (SR-5, SR-7).
"""

from __future__ import annotations

from typing import Any

from robofleet.config.models import ScenarioConfig
from robofleet.contracts.alert import Alert, AlertCategory, AlertSeverity
from robofleet.contracts.catalogue import Bin, Sku
from robofleet.contracts.commands import (
    BlockCellsCommand,
    ClearFaultCommand,
    CommandUnion,
    EmergencyStopCommand,
    InjectFaultCommand,
    ResumeCommand,
    UnblockCellsCommand,
)
from robofleet.contracts.common import Coordinate, Heading
from robofleet.contracts.events import Event
from robofleet.contracts.layout import Layout
from robofleet.contracts.robot import Robot, RobotState
from robofleet.contracts.state import DynamicState, StaticWorld
from robofleet.rules.engine import RuleEngine
from robofleet.sim.clock import SimClock
from robofleet.sim.dispatcher import WanderDispatcher
from robofleet.sim.planner import AStarFlowPlanner
from robofleet.sim.rng import RandomStreamManager
from robofleet.sim.safety import SafetyGuard


class SimEngine:
    def __init__(
        self,
        config: ScenarioConfig,
        layout: Layout,
        skus: list[Sku],
        bins: list[Bin],
        rule_engine: RuleEngine | None = None,
    ) -> None:
        self.config = config
        self.layout = layout
        self.skus = skus
        self.bins = bins
        self.rule_engine = rule_engine or RuleEngine(config.rules.rules_dir)

        # Discrete clock
        self.clock = SimClock(tick_hz=config.timing.tick_hz)

        # RNG manager
        self.rng_mgr = RandomStreamManager(root_seed=config.seed)
        self.sim_rng = self.rng_mgr.get_stream("sim")
        self.planner_rng = self.rng_mgr.get_stream("planner")
        self.disp_rng = self.rng_mgr.get_stream("dispatcher")

        # Exclusive safety boundary
        self.safety_guard = SafetyGuard(layout=self.layout)

        # Pluggable planner and dispatcher
        self.planner = AStarFlowPlanner(
            replan_wait_ticks=config.planner.params.get("replan_wait_ticks", 10),
            yield_wait_ticks=config.planner.params.get("yield_wait_ticks", 30),
            deadlock_threshold_ticks=config.planner.params.get("deadlock_threshold_ticks", 60),
        )
        self.dispatcher = WanderDispatcher(
            dwell_ticks=config.dispatcher.params.get("dwell_ticks", 20),
            recharge_target_pct=config.battery.recharge_target_pct,
        )

        # Queues and state
        self.command_queue: list[CommandUnion] = []
        self.events: list[Event] = []
        self.alerts: list[Alert] = []
        self.seq: int = 0
        self.visited_cells_per_robot: dict[str, set[tuple[int, int]]] = {}

        # Charger locations
        self.charger_cells = {c.pos.as_tuple() for c in layout.chargers}

        # Initialize robots at parking cells
        self.robots: list[Robot] = []
        parking_candidates = sorted(layout.parking_cells, key=lambda c: (c.y, c.x))
        for i in range(config.robot_count):
            r_id = f"R-{i + 1:03d}"
            # Place in parking cell or fallback floor cell
            spawn_pos = (
                parking_candidates[i % len(parking_candidates)]
                if parking_candidates
                else Coordinate(x=1, y=1)
            )
            robot = Robot(
                robot_id=r_id,
                kind="standard_amr",
                cell=spawn_pos,
                heading=Heading.N,
                state=RobotState.IDLE,
                battery_pct=float(self.sim_rng.uniform(85.0, 100.0)),
            )
            self.robots.append(robot)
            self.visited_cells_per_robot[r_id] = {(spawn_pos.x, spawn_pos.y)}

        self.emit_event(
            "sim.started", {"scenario": config.scenario_name, "robot_count": config.robot_count}
        )

    def emit_event(self, event_type: str, payload: dict[str, Any]) -> None:
        self.seq += 1
        ev = Event(
            seq=self.seq,
            tick=self.clock.tick,
            sim_time_ms=self.clock.sim_time_ms,
            event_type=event_type,
            payload=payload,
        )
        self.events.append(ev)

    def queue_command(self, cmd: CommandUnion) -> None:
        self.command_queue.append(cmd)

    def step(self) -> None:
        """Executes one simulation tick according to the 9-step contract."""
        # Step 1: Apply queued commands
        while self.command_queue:
            cmd = self.command_queue.pop(0)
            self._apply_command(cmd)

        # Step 2: Brain (null in Phase 1)
        # Step 3: Order source (null in Phase 1)

        # Step 4: Dispatcher
        destinations = self.dispatcher.get_destinations(
            robots=self.robots,
            layout=self.layout,
            low_battery_threshold=self.config.battery.low_battery_threshold,
            rng=self.disp_rng,
        )

        # Step 5: Planner proposes move intents
        intents, deadlocked_robots = self.planner.plan_intents(
            robots=self.robots,
            destinations=destinations,
            layout=self.layout,
            blocked_cells=self.safety_guard.blocked_cells,
            rng=self.planner_rng,
        )
        for d_id in deadlocked_robots:
            self.emit_event("sim.deadlock_detected", {"robot_id": d_id})

        # Step 6: SafetyGuard validates and commits moves
        denials = self.safety_guard.validate_and_apply_moves(
            robots=self.robots,
            intents=intents,
        )
        for denial in denials:
            self.emit_event("safety.move_denied", denial)

        # Step 7: Update motion, battery, and states
        for robot in self.robots:
            # Track visited destinations
            self.visited_cells_per_robot[robot.robot_id].add(robot.cell.as_tuple())

            # Battery charging check
            if robot.cell.as_tuple() in self.charger_cells:
                robot.state = RobotState.CHARGING
                robot.battery_pct = min(
                    100.0,
                    robot.battery_pct + self.config.battery.charge_rate_per_tick,
                )
                if robot.battery_pct >= self.config.battery.recharge_target_pct:
                    robot.state = RobotState.IDLE
            else:
                # Battery drain
                if robot.state == RobotState.MOVING:
                    robot.battery_pct = max(
                        0.0, robot.battery_pct - self.config.battery.drain_moving_per_tick
                    )
                else:
                    robot.battery_pct = max(
                        0.0, robot.battery_pct - self.config.battery.drain_idle_per_tick
                    )

        # Step 8: Evaluate alert rules
        self._evaluate_alerts()

        # Step 9: Emit lifecycle events & advance tick
        self.clock.advance()

    def _apply_command(self, cmd: CommandUnion) -> None:
        if isinstance(cmd, EmergencyStopCommand):
            self.safety_guard.set_emergency_stop(cmd.scope, cmd.target_id)
            self.emit_event(
                "safety.emergency_stop", {"scope": cmd.scope, "target_id": cmd.target_id}
            )
        elif isinstance(cmd, ResumeCommand):
            self.safety_guard.resume_emergency_stop(cmd.scope, cmd.target_id)
            self.emit_event("safety.resume", {"scope": cmd.scope, "target_id": cmd.target_id})
        elif isinstance(cmd, BlockCellsCommand):
            self.safety_guard.block_cells(cmd.cells)
            self.emit_event("layout.cells_blocked", {"cells": [c.model_dump() for c in cmd.cells]})
        elif isinstance(cmd, UnblockCellsCommand):
            self.safety_guard.unblock_cells(cmd.cells)
            self.emit_event(
                "layout.cells_unblocked", {"cells": [c.model_dump() for c in cmd.cells]}
            )
        elif isinstance(cmd, InjectFaultCommand):
            for r in self.robots:
                if r.robot_id == cmd.target_id:
                    r.fault = cmd.fault_type
                    r.state = RobotState.UNAVAILABLE
                    self.emit_event(
                        "sim.fault_injected", {"robot_id": r.robot_id, "fault": cmd.fault_type}
                    )
        elif isinstance(cmd, ClearFaultCommand):
            for r in self.robots:
                if r.robot_id == cmd.target_id:
                    r.fault = None
                    r.state = RobotState.IDLE
                    self.emit_event("sim.fault_cleared", {"robot_id": r.robot_id})

    def _evaluate_alerts(self) -> None:
        active_alerts: list[Alert] = []
        for robot in self.robots:
            context = {
                "robot": {
                    "robot_id": robot.robot_id,
                    "state": robot.state.value,
                    "battery_pct": robot.battery_pct,
                    "blocked_ticks": robot.blocked_ticks,
                    "cell": robot.cell.as_tuple(),
                }
            }
            matched_rules = self.rule_engine.evaluate("alert", context)
            for rule in matched_rules:
                alert_id = f"ALT-{rule.id}-{robot.robot_id}"
                alert = Alert(
                    alert_id=alert_id,
                    severity=AlertSeverity(rule.severity),
                    category=AlertCategory.BATTERY if "battery" in rule.id else AlertCategory.ROBOT,
                    message=f"{rule.description} for {robot.robot_id}",
                    entity_ids=[robot.robot_id],
                    cell=robot.cell,
                    raised_tick=self.clock.tick,
                    requires_human=rule.effect == "require_human",
                )
                active_alerts.append(alert)
        self.alerts = active_alerts

    def get_dynamic_state(self) -> DynamicState:
        return DynamicState(
            tick=self.clock.tick,
            sim_time_ms=self.clock.sim_time_ms,
            seq=self.seq,
            robots=[r.model_copy() for r in self.robots],
            orders=[],
            alerts=[a.model_copy() for a in self.alerts],
            blocked_cells=[
                Coordinate(x=x, y=y) for x, y in sorted(self.safety_guard.blocked_cells)
            ],
            kpis={
                "robot_count": float(len(self.robots)),
                "deadlock_incidents": float(self.planner.deadlock_incidents),
            },
        )

    def get_static_world(self) -> StaticWorld:
        return StaticWorld(
            layout=self.layout,
            catalogue=self.skus,
            bins=self.bins,
            config_summary={
                "robot_count": self.config.robot_count,
                "scenario": self.config.scenario_name,
            },
        )
