"""RoboFleet Core Simulation Engine.
Implements the strict 9-step tick execution contract (SR-5, SR-7),
cooperative traffic management, pluggable fulfillment dispatchers,
order lifecycle progression, and real-time operations KPI tracking.
"""

from __future__ import annotations

from typing import Any
import numpy as np

from robofleet.audit.database import AuditDatabase
from robofleet.audit.exceptions_queue import ExceptionsQueue
from robofleet.chaos.engine import ChaosEngine
from robofleet.config.models import ScenarioConfig
from robofleet.contracts.alert import Alert, AlertCategory, AlertSeverity
from robofleet.contracts.catalogue import Bin, Sku
from robofleet.contracts.chaos import ExceptionItem, PickOutcome
from robofleet.contracts.commands import (
    BlockCellsCommand,
    ClearFaultCommand,
    CommandUnion,
    EmergencyStopCommand,
    InjectFaultCommand,
    ResumeCommand,
    ScaleFleetCommand,
    UnblockCellsCommand,
)
from robofleet.contracts.common import Coordinate, Heading
from robofleet.contracts.events import Event
from robofleet.contracts.layout import Layout
from robofleet.contracts.order import Order, OrderStatus
from robofleet.contracts.robot import Robot, RobotState
from robofleet.contracts.state import DynamicState, StaticWorld
from robofleet.fleet.dispatch_bay import DispatchBayManager
from robofleet.fleet.metrics import OperationsMetricTracker
from robofleet.fleet.station import PickingStationManager
from robofleet.fleet.task_manager import TaskManager
from robofleet.interfaces.protocols import OrderSource
from robofleet.registry.generic import planner_registry, strategy_registry
from robofleet.replenishment.recommender import ReplenishmentManager, ReslottingRecommender
from robofleet.rules.engine import RuleEngine
from robofleet.sim.clock import SimClock
from robofleet.sim.dispatcher import WanderDispatcher
from robofleet.sim.planner import AStarFlowPlanner
from robofleet.sim.reservation_planner import ReservationAStarPlanner
from robofleet.sim.rng import RandomStreamManager
from robofleet.sim.safety import SafetyGuard
import robofleet.fleet.strategies  # noqa: F401 (trigger strategy registrations)


class SimEngine:
    def __init__(
        self,
        config: ScenarioConfig,
        layout: Layout,
        skus: list[Sku],
        bins: list[Bin],
        rule_engine: RuleEngine | None = None,
        order_source: OrderSource | None = None,
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

        # Phase 3 & 6: Station, Dispatch, Task Managers and Pick Verification
        fulfil_cfg = getattr(config, "fulfilment", None)
        base_pick_ticks = getattr(fulfil_cfg, "base_pick_time_ticks", 30) if fulfil_cfg else 30
        cons_ticks = getattr(fulfil_cfg, "consolidation_time_ticks", 20) if fulfil_cfg else 20
        max_q = getattr(fulfil_cfg, "max_station_queue_capacity", 6) if fulfil_cfg else 6
        handoff_ticks = getattr(fulfil_cfg, "supervisor_handoff_base_ticks", 40) if fulfil_cfg else 40
        rider_rate = getattr(fulfil_cfg, "rider_arrival_rate_per_hr", 120.0) if fulfil_cfg else 120.0

        verif_cfg = getattr(config, "verification", None)
        self.station_mgr = PickingStationManager(
            station_defs=layout.stations,
            base_pick_time_ticks=base_pick_ticks,
            consolidation_time_ticks=cons_ticks,
            max_queue_capacity=max_q,
            verification_cfg=verif_cfg,
            picker_rng=self.rng_mgr.get_stream("picker"),
            event_emitter=self.emit_event,
        )
        self.dispatch_mgr = DispatchBayManager(
            dispatch_cells=layout.dispatch_cells,
            supervisor_cells=layout.supervisor_cells,
            base_handoff_ticks=handoff_ticks,
            rider_arrival_rate_per_hr=rider_rate,
            tick_hz=config.timing.tick_hz,
            seed=config.seed,
        )
        self.task_mgr = TaskManager(
            layout=layout,
            skus=skus,
            bins=bins,
            station_mgr=self.station_mgr,
            dispatch_mgr=self.dispatch_mgr,
        )
        self.metric_tracker = OperationsMetricTracker(tick_hz=config.timing.tick_hz)

        # Phase 6: Chaos Engine, Audit Ledger, Exceptions Queue, Replenishment and Reslotting
        self.audit_db = AuditDatabase()
        self.exceptions_queue = ExceptionsQueue(audit_db=self.audit_db)
        scenario_file = getattr(getattr(config, "chaos", None), "scenario_file", None)
        self.chaos_engine = ChaosEngine(engine=self, scenario_path=scenario_file)

        rep_cfg = getattr(config, "replenishment", None)
        low_stock_th = getattr(rep_cfg, "low_stock_threshold", 3) if rep_cfg else 3
        restock_qty = getattr(rep_cfg, "restock_quantity", 10) if rep_cfg else 10
        stocker_spd = getattr(rep_cfg, "stocker_speed_ticks", 40) if rep_cfg else 40
        rep_enabled = getattr(rep_cfg, "enabled", True) if rep_cfg else True
        self.replenishment_mgr = ReplenishmentManager(
            engine=self,
            low_stock_threshold=low_stock_th,
            restock_quantity=restock_qty,
            stocker_speed_ticks=stocker_spd,
            enabled=rep_enabled,
        )

        reslot_cfg = getattr(config, "reslotting", None)
        reslot_interval = getattr(reslot_cfg, "evaluation_interval_ticks", 250) if reslot_cfg else 250
        max_recs = getattr(reslot_cfg, "max_recommendations", 5) if reslot_cfg else 5
        cong_limit = getattr(reslot_cfg, "max_congestion_proxy_limit", 0.75) if reslot_cfg else 0.75
        reslot_enabled = getattr(reslot_cfg, "enabled", True) if reslot_cfg else True
        self.reslot_recommender = ReslottingRecommender(
            engine=self,
            audit_db=self.audit_db,
            evaluation_interval_ticks=reslot_interval,
            max_recommendations=max_recs,
            max_congestion_proxy_limit=cong_limit,
            enabled=reslot_enabled,
        )

        # Pluggable planner
        planner_type = getattr(config.planner, "type", "astar_flow")
        if planner_type == "reservation_astar":
            self.planner = ReservationAStarPlanner(
                horizon_ticks=config.planner.params.get("horizon_ticks", 25),
                replan_wait_ticks=config.planner.params.get("replan_wait_ticks", 8),
                yield_wait_ticks=config.planner.params.get("yield_wait_ticks", 20),
                deadlock_threshold_ticks=config.planner.params.get("deadlock_threshold_ticks", 40),
            )
        else:
            self.planner = AStarFlowPlanner(
                replan_wait_ticks=config.planner.params.get("replan_wait_ticks", 10),
                yield_wait_ticks=config.planner.params.get("yield_wait_ticks", 30),
                deadlock_threshold_ticks=config.planner.params.get("deadlock_threshold_ticks", 60),
            )

        # Pluggable dispatcher / strategy
        disp_type = getattr(config.dispatcher, "type", "wander")
        if disp_type in strategy_registry.list_registered():
            self.dispatcher = strategy_registry.create(
                {"type": disp_type, "params": config.dispatcher.params}
            )
        else:
            self.dispatcher = WanderDispatcher(
                dwell_ticks=config.dispatcher.params.get("dwell_ticks", 20),
                recharge_target_pct=config.battery.recharge_target_pct,
            )

        # Pluggable order source
        self.orders: list[Order] = []
        self.orders_received_count: int = 0
        if order_source is not None:
            self.order_source: OrderSource | None = order_source
        else:
            self.order_source = self._init_order_source()

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

    def reset(self) -> None:
        """Resets simulation back to initial state at tick 0 and reinitializes fleet."""
        self.__init__(
            config=self.config,
            layout=self.layout,
            skus=self.skus,
            bins=self.bins,
            rule_engine=self.rule_engine,
            order_source=None,
        )

    def _init_order_source(self) -> OrderSource | None:
        orders_cfg = getattr(self.config, "orders", None)
        if not orders_cfg:
            return None
        from robofleet.adapters.csv_replay import CsvReplayOrderSource
        from robofleet.adapters.demand_engine import SyntheticDemandEngine
        from robofleet.adapters.webhook import WebhookOrderSource

        if orders_cfg.adapter == "demand_engine":
            slotted_sku_ids = {b.sku_id for b in self.bins if b.sku_id and b.quantity > 0}
            active_skus = [s for s in self.skus if s.sku_id in slotted_sku_ids] if slotted_sku_ids else self.skus
            return SyntheticDemandEngine(
                profile_path=orders_cfg.demand_profile,
                skus=active_skus,
                seed=self.config.seed,
                tick_hz=self.config.timing.tick_hz,
                urgent_share=orders_cfg.urgent_share,
                rush_multiplier=orders_cfg.rush_multiplier,
            )
        elif orders_cfg.adapter == "csv_replay":
            return CsvReplayOrderSource(
                csv_path=orders_cfg.csv_file or "scenarios/sample_orders.csv",
                tick_hz=self.config.timing.tick_hz,
            )
        elif orders_cfg.adapter == "webhook":
            return WebhookOrderSource()
        return None

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

    def scale_fleet(self, target_count: int) -> None:
        """Dynamically scales active AMR fleet size at runtime (P3-A10)."""
        target_count = max(1, min(100, target_count))
        curr_count = len(self.robots)
        if target_count == curr_count:
            return

        if target_count > curr_count:
            parking_candidates = sorted(self.layout.parking_cells, key=lambda c: (c.y, c.x))
            for i in range(curr_count, target_count):
                r_id = f"R-{i + 1:03d}"
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
                    battery_pct=100.0,
                )
                self.robots.append(robot)
                self.visited_cells_per_robot[r_id] = {(spawn_pos.x, spawn_pos.y)}
                self.emit_event("fleet.robot_spawned", {"robot_id": r_id, "cell": spawn_pos.model_dump()})
        else:
            # Safely retire idle robots without active orders
            removable = [
                r for r in self.robots if r.current_task_id is None and r.state in (RobotState.IDLE, RobotState.CHARGING)
            ]
            to_retire = removable[: (curr_count - target_count)]
            for r in to_retire:
                self.robots.remove(r)
                self.emit_event("fleet.robot_retired", {"robot_id": r.robot_id})

    def step(self) -> None:
        """Executes one simulation tick according to the 9-step contract."""
        # Step 1: Apply queued commands
        while self.command_queue:
            cmd = self.command_queue.pop(0)
            self._apply_command(cmd)

        # Step 2: Chaos Engine, Exceptions Queue, Replenishment and Reslotting (Phase 6)
        self.chaos_engine.step(self.clock.tick)
        self.exceptions_queue.step(self.clock.tick)
        self.replenishment_mgr.step(self.clock.tick)
        self.reslot_recommender.step(self.clock.tick)

        # Step 3: Order source polling
        if self.order_source:
            new_orders = self.order_source.poll_orders(self.clock.tick)
            for order in new_orders:
                self.orders.append(order)
                self.orders_received_count += 1
                self.emit_event(
                    "order.received",
                    {
                        "order_id": order.order_id,
                        "line_count": len(order.lines),
                        "priority": order.priority,
                        "sla_tier": order.sla_tier,
                        "deadline_tick": order.deadline_tick,
                    },
                )

        # Check deadline & at_risk status for active orders
        at_risk_threshold = getattr(
            getattr(self.config, "orders", None), "at_risk_threshold_ticks", 150
        )
        for order in self.orders:
            if order.status in (OrderStatus.RECEIVED, OrderStatus.QUEUED, OrderStatus.PLANNED, OrderStatus.RETRIEVING):
                remaining = order.deadline_tick - self.clock.tick
                if remaining <= at_risk_threshold and not order.at_risk:
                    order.at_risk = True
                    self.emit_event(
                        "order.at_risk",
                        {
                            "order_id": order.order_id,
                            "remaining_ticks": remaining,
                            "deadline_tick": order.deadline_tick,
                        },
                    )

        # Step 4: Dispatcher / Strategy
        if hasattr(self.dispatcher, "dispatch"):
            destinations = self.dispatcher.dispatch(
                orders=self.orders,
                robots=self.robots,
                layout=self.layout,
                bins=self.task_mgr.bins,
                skus=self.task_mgr.skus,
                task_mgr=self.task_mgr,
                station_mgr=self.station_mgr,
                current_tick=self.clock.tick,
                rng=self.disp_rng,
            )
        else:
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
            current_tick=self.clock.tick,
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

        # Step 7: Station, consolidation, dispatch, battery, and motion updates
        orders_by_id = {o.order_id: o for o in self.orders}

        # 7a: Advance active station picks and inventory decrements
        completed_picks = self.station_mgr.step_picks(self.clock.tick, orders_by_id)
        for ord_id, sku_id, qty in completed_picks:
            order = orders_by_id.get(ord_id)
            if order:
                for line in order.lines:
                    if line.sku_id == sku_id and line.status == "PENDING":
                        line.status = "PICKED"
                        line.picked_quantity += qty
                        self.task_mgr.units_in_flight += qty
                        # Decrement bin physical inventory
                        for b in self.bins:
                            if b.sku_id == sku_id and b.quantity >= qty:
                                b.quantity -= qty
                                break
                        self.emit_event(
                            "station.pick_completed",
                            {"order_id": ord_id, "sku_id": sku_id, "quantity": qty},
                        )
                        break

                if (
                    self.station_mgr.is_order_fully_consolidated(order)
                    and order.status in (
                        OrderStatus.RECEIVED,
                        OrderStatus.QUEUED,
                        OrderStatus.PLANNED,
                        OrderStatus.RETRIEVING,
                        OrderStatus.AT_STATION,
                        OrderStatus.PICKING,
                    )
                ):
                    order.status = OrderStatus.CONSOLIDATING
                    self.task_mgr.record_stage_time(order.order_id, "CONSOLIDATING", self.clock.tick)
                    self.emit_event("order.consolidating", {"order_id": ord_id})

        # 7a-bis: Handle Pick Verification Exceptions (Phase 6 SO-101 Pattern)
        for ord_id, sku_id, qty, reason, outcome in getattr(self.station_mgr, "last_failed_picks", []):
            order = orders_by_id.get(ord_id)
            if order:
                for line in order.lines:
                    if line.sku_id == sku_id and line.status == "PENDING":
                        line.status = "DAMAGED" if reason == "damaged_item" else "MISMATCH"
                        break

                # Attempt autonomous item substitution from replica bin
                substituted = self.chaos_engine.recovery_mgr.substitute_missing_or_damaged_item(
                    order_id=ord_id,
                    sku_id=sku_id,
                    quantity=qty,
                    reason=reason,
                    tick=self.clock.tick,
                )
                if not substituted:
                    # Escalate unresolvable exception to supervisor queue
                    exc = ExceptionItem(
                        exception_type="damaged_item" if reason == "damaged_item" else "pick_verification_failed",
                        severity="HIGH",
                        entity_id=ord_id,
                        raised_tick=self.clock.tick,
                        deadline_tick=self.clock.tick + 200,
                        default_action="approve_partial",
                        recommended_action=f"Verification {outcome.value} ({reason}); approve partial or delay",
                        available_actions=["approve_partial", "delay_order", "cancel_order"],
                    )
                    self.exceptions_queue.add_exception(exc)

        # 7b: Enqueue PACKED orders into dispatch bay
        for order in self.orders:
            if order.status == OrderStatus.PACKED and order.ready_tick is None:
                self.dispatch_mgr.enqueue_ready_order(order, self.clock.tick)
                self.task_mgr.record_stage_time(order.order_id, "PACKED", self.clock.tick)
                self.emit_event("order.ready_for_dispatch", {"order_id": order.order_id})

        # 7c: Advance supervisor rider handovers
        handed_over_ids = self.dispatch_mgr.step(self.clock.tick, orders_by_id)
        for h_id in handed_over_ids:
            order = orders_by_id.get(h_id)
            if order:
                picked_units = sum(l.quantity for l in order.lines if l.status == "PICKED")
                self.task_mgr.units_in_flight = max(0, self.task_mgr.units_in_flight - picked_units)
                self.task_mgr.units_completed += picked_units
                order.delay_attribution = self.task_mgr.compute_delay_attribution(order, self.clock.tick)
                self.emit_event(
                    "order.handed_over",
                    {
                        "order_id": h_id,
                        "ready_tick": order.ready_tick,
                        "handover_tick": order.handover_tick,
                    },
                )

        # 7d: Handle stock-out restock for terminal FAILED_PARTIAL orders
        for order in self.orders:
            if order.status == OrderStatus.FAILED_PARTIAL and not getattr(order, "_restocked", False):
                setattr(order, "_restocked", True)
                for line in order.lines:
                    if line.picked_quantity > 0:
                        self.task_mgr.units_in_flight = max(0, self.task_mgr.units_in_flight - line.picked_quantity)
                        candidate_b_ids = self.task_mgr.sku_to_bins.get(line.sku_id, [])
                        if candidate_b_ids:
                            self.task_mgr.bins[candidate_b_ids[0]].quantity += line.picked_quantity
                        line.picked_quantity = 0

        # 7e: Update robot battery & visited cells
        for robot in self.robots:
            self.visited_cells_per_robot[robot.robot_id].add(robot.cell.as_tuple())
            if robot.cell.as_tuple() in self.charger_cells:
                robot.state = RobotState.CHARGING
                robot.battery_pct = min(
                    100.0,
                    robot.battery_pct + self.config.battery.charge_rate_per_tick,
                )
                if robot.battery_pct >= self.config.battery.recharge_target_pct:
                    robot.state = RobotState.IDLE
            else:
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
        elif isinstance(cmd, ScaleFleetCommand):
            self.scale_fleet(cmd.target_count)
        elif isinstance(cmd, InjectFaultCommand):
            self.chaos_engine.inject_fault(
                fault_type=cmd.fault_type,
                target_id=cmd.target_id,
                duration_ticks=cmd.duration_ticks,
                tick=self.clock.tick,
            )
        elif isinstance(cmd, ClearFaultCommand):
            for r in self.robots:
                if r.robot_id == cmd.target_id:
                    r.fault = None
                    r.state = RobotState.IDLE
                    self.emit_event("sim.fault_cleared", {"robot_id": r.robot_id})
            self.chaos_engine.clear_and_heal_all(tick=self.clock.tick)

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
                if "battery" in rule.id:
                    msg = f"Robot {robot.robot_id}: Low battery ({robot.battery_pct:.0f}%) - route to charger"
                elif "waiting" in rule.id or "blocked" in rule.id:
                    msg = f"Robot {robot.robot_id}: Blocked in transit / excessive waiting ({robot.blocked_ticks} ticks)"
                elif robot.fault:
                    msg = f"Robot {robot.robot_id}: Hardware fault detected ({robot.fault})"
                else:
                    msg = f"Robot {robot.robot_id}: {rule.description}"

                alert = Alert(
                    alert_id=alert_id,
                    severity=AlertSeverity(rule.severity),
                    category=AlertCategory.BATTERY if "battery" in rule.id else AlertCategory.ROBOT,
                    message=msg,
                    entity_ids=[robot.robot_id],
                    cell=robot.cell,
                    raised_tick=self.clock.tick,
                    requires_human=rule.effect == "require_human",
                )
                active_alerts.append(alert)
        self.alerts = active_alerts

    @property
    def dynamic_state(self) -> DynamicState:
        return self.get_dynamic_state()

    def get_dynamic_state(self) -> DynamicState:
        # Station utilization across all stations
        avg_st_util = float(
            np.mean([self.station_mgr.get_station_utilization(s.station_id) for s in self.layout.stations])
        ) if self.layout.stations else 0.0

        # Phase 6 Resilience KPIs
        mttr_map = self.chaos_engine.get_mttr_by_type()
        avg_mttr = float(np.mean(list(mttr_map.values()))) if mttr_map else 0.0
        human_per_100 = self.exceptions_queue.compute_human_interventions_per_100_orders(len(self.orders))
        queue_age = self.exceptions_queue.get_queue_average_age_ticks(self.clock.tick)
        degraded_time = sum(
            (self.clock.tick - m.active_since_tick) / max(1, self.clock.tick_hz)
            for m in self.chaos_engine.get_active_degraded_modes()
        )

        kpis = self.metric_tracker.get_live_kpis(
            orders=self.orders,
            robots=self.robots,
            current_tick=self.clock.tick,
            station_util=avg_st_util,
            supervisor_util=self.dispatch_mgr.supervisor_utilization,
            deadlocks=self.planner.deadlock_incidents,
            alerts_count=len(self.alerts),
            mttd_s=0.5,
            mttr_s=avg_mttr,
            human_interventions_per_100=human_per_100,
            exceptions_queue_age=queue_age,
            degraded_mode_time_s=degraded_time,
        )

        return DynamicState(
            tick=self.clock.tick,
            sim_time_ms=self.clock.sim_time_ms,
            seq=self.seq,
            robots=[r.model_copy() for r in self.robots],
            orders=[o.model_copy() for o in self.orders],
            alerts=[a.model_copy() for a in self.alerts],
            blocked_cells=[
                Coordinate(x=x, y=y) for x, y in sorted(self.safety_guard.blocked_cells)
            ],
            kpis=kpis,
        )

    def get_static_world(self) -> StaticWorld:
        return StaticWorld(
            layout=self.layout,
            catalogue=self.skus,
            bins=self.bins,
            config_summary={
                "robot_count": len(self.robots),
                "scenario": self.config.scenario_name,
                "strategy": getattr(self.config.dispatcher, "type", "wander"),
                "planner": getattr(self.config.planner, "type", "astar_flow"),
            },
        )
