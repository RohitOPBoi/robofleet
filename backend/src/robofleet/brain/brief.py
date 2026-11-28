"""Situation Brief Builder (Phase 5 - Upgraded).

Constructs bounded, deterministic world briefs for the AI Operations Brain.
Distills live KPIs, deadlocks, fleet telemetry, station queues, battery bounds,
recent outcome feedback, and specialist proposals within a compact context budget.
"""

from __future__ import annotations

from typing import Any

from robofleet.brain.deadlock import DeadlockAnalyzer
from robofleet.contracts.brain import (
    BriefDeadlockInfo,
    BriefKPIs,
    BriefOrderSummary,
    BriefOutcomeSummary,
    BriefRobotSummary,
    BriefStationQueue,
    SituationBrief,
)
from robofleet.contracts.common import Coordinate


class SituationBriefBuilder:
    """Builds a compact, deterministic SituationBrief from live simulation state."""

    def __init__(self, max_at_risk: int = 10, max_robots: int = 12) -> None:
        self.max_at_risk = max_at_risk
        self.max_robots = max_robots

    def build(
        self,
        tick: int,
        trigger: str,
        engine: Any,
        recent_decision_ids: list[str] | None = None,
        held_zone_ids: list[str] | None = None,
        recent_outcomes: list[BriefOutcomeSummary] | None = None,
        failed_command_hints: list[str] | None = None,
    ) -> SituationBrief:
        dynamic = engine.dynamic_state if hasattr(engine, "dynamic_state") else engine.get_dynamic_state()
        kpi_obj = dynamic.kpis

        config = getattr(engine, "config", None)
        battery_cfg = getattr(config, "battery", None)
        brain_cfg = getattr(config, "brain", None)
        no_progress_ticks = getattr(brain_cfg, "deadlock_no_progress_ticks", 12) if brain_cfg else 12
        low_bat_thresh = float(getattr(battery_cfg, "low_battery_threshold", 20.0)) if battery_cfg else 20.0
        crit_bat_thresh = float(getattr(battery_cfg, "critical_battery_threshold", 10.0)) if battery_cfg else 10.0

        # 1. Deadlock & conflict analysis
        deadlocks: list[BriefDeadlockInfo] = DeadlockAnalyzer.analyze(
            engine, no_progress_ticks=no_progress_ticks
        )

        # 2. Robots inspection
        robots = list(dynamic.robots.values()) if isinstance(dynamic.robots, dict) else list(dynamic.robots)
        avg_wait = (
            round(sum(float(getattr(r, "blocked_ticks", 0)) for r in robots) / len(robots), 2)
            if robots
            else 0.0
        )

        if isinstance(kpi_obj, dict):
            moving = int(kpi_obj.get("robots_moving", 0))
            idle = int(kpi_obj.get("robots_idle", 0))
            charging = int(kpi_obj.get("robots_charging", 0))
            q_depth = int(kpi_obj.get("queue_depth", 0))
            thru = float(
                kpi_obj.get("throughput_orders_per_hr") or kpi_obj.get("throughput_per_hr") or 0.0
            )
            at_risk = int(kpi_obj.get("at_risk_orders", 0))
            alerts_count = int(kpi_obj.get("active_alerts_count", 0))
            total_active = moving + idle + charging
            util_pct = round((moving / total_active * 100.0) if total_active > 0 else 0.0, 1)
        else:
            moving = int(getattr(kpi_obj, "robots_moving", 0))
            idle = int(getattr(kpi_obj, "robots_idle", 0))
            charging = int(getattr(kpi_obj, "robots_charging", 0))
            q_depth = int(getattr(kpi_obj, "queue_depth", 0))
            thru = float(getattr(kpi_obj, "throughput_orders_per_hr", getattr(kpi_obj, "throughput_per_hr", 0.0)))
            at_risk = int(getattr(kpi_obj, "at_risk_orders", 0))
            alerts_count = int(getattr(kpi_obj, "active_alerts_count", 0))
            total_active = moving + idle + charging
            util_pct = round((moving / total_active * 100.0) if total_active > 0 else 0.0, 1)

        brief_kpis = BriefKPIs(
            queue_depth=q_depth,
            throughput_per_hr=thru,
            at_risk_count=at_risk,
            active_alerts_count=alerts_count,
            robots_moving=moving,
            robots_idle=idle,
            robots_charging=charging,
            fleet_utilization_pct=util_pct,
            avg_waiting_ticks=avg_wait,
            active_deadlocks_count=len(deadlocks),
        )

        # 3. At-risk orders (plus urgent active queued orders)
        orders = list(dynamic.orders.values()) if isinstance(dynamic.orders, dict) else list(dynamic.orders)
        at_risk_list: list[BriefOrderSummary] = []
        sorted_orders = sorted(
            orders,
            key=lambda x: (
                0 if getattr(x, "at_risk", False) else 1,
                max(0, getattr(x, "deadline_tick", 999999) - tick),
                -int(getattr(x, "priority", 1)),
            ),
        )
        for o in sorted_orders:
            deadline_rem = max(0, getattr(o, "deadline_tick", 999999) - tick)
            st = getattr(o, "status", "RECEIVED")
            st_val = st.value if hasattr(st, "value") else str(st)
            if st_val in ("HANDED_OVER", "DELIVERED", "CANCELLED", "FAILED", "FAILED_PARTIAL"):
                continue
            is_at_risk = getattr(o, "at_risk", False) or deadline_rem < 200 or st_val in ("RECEIVED", "QUEUED")
            if is_at_risk:
                assigned_r = None
                assigned_list = getattr(o, "assigned_robot_ids", None)
                if assigned_list and len(assigned_list) > 0:
                    assigned_r = assigned_list[0]
                at_risk_list.append(
                    BriefOrderSummary(
                        order_id=getattr(o, "order_id", ""),
                        lines_count=len(getattr(o, "lines", [])),
                        sla_remaining_ticks=deadline_rem,
                        priority=getattr(o, "priority", 1),
                        assigned_robot_id=assigned_r,
                        state=st_val,
                    )
                )
            if len(at_risk_list) >= self.max_at_risk:
                break

        # 4. Station queues & chargers & zones
        station_queues: list[BriefStationQueue] = []
        layout = getattr(engine, "layout", None)
        stations = getattr(layout, "stations", []) if layout else []
        for st in stations:
            st_id = getattr(st, "station_id", "")
            q_len = 0
            if hasattr(engine, "station_mgr") and hasattr(engine.station_mgr, "robot_queues"):
                q_len = len(engine.station_mgr.robot_queues.get(st_id, []))
            elif hasattr(engine, "station_mgr") and hasattr(engine.station_mgr, "queues"):
                q_len = len(engine.station_mgr.queues.get(st_id, []))
            if q_len == 0:
                q_len = sum(1 for r in robots if getattr(r, "current_task_id", None) == st_id)
            station_queues.append(
                BriefStationQueue(
                    station_id=st_id,
                    queue_length=q_len,
                    active_robot_id=(
                        engine.station_mgr.dock_occupant.get(st_id)
                        if hasattr(engine, "station_mgr") and hasattr(engine.station_mgr, "dock_occupant")
                        else None
                    ),
                    avg_service_time_ticks=30.0,
                    is_active=bool(getattr(st, "is_active", True)),
                )
            )

        chargers = getattr(layout, "chargers", []) if layout else []
        charger_ids = [getattr(c, "charger_id", f"CHG-{idx}") for idx, c in enumerate(chargers)]
        available_zones = [getattr(z, "name", "") for z in (getattr(layout, "zones", []) if layout else []) if getattr(z, "name", "")]

        # 5. Robot summaries (critical + compact fleet overview)
        destinations = dict(getattr(engine, "last_destinations", {}))
        deadlocked_ids = {rid for dl in deadlocks for rid in dl.robots_involved}
        waiting_lookup: dict[str, str] = {}
        for dl in deadlocks:
            if len(dl.cycle_chain) >= 2:
                for i in range(len(dl.cycle_chain) - 1):
                    waiting_lookup[dl.cycle_chain[i]] = dl.cycle_chain[i + 1]

        critical_robots: list[BriefRobotSummary] = []
        robots_overview: list[BriefRobotSummary] = []

        for r in robots:
            rid = getattr(r, "robot_id", getattr(r, "id", ""))
            bat = float(getattr(r, "battery_pct", getattr(r, "battery_percent", 100.0)))
            st = getattr(r, "state", "IDLE")
            st_val = st.value if hasattr(st, "value") else str(st)
            blocked_ticks = int(getattr(r, "blocked_ticks", 0))
            coord = getattr(r, "cell", getattr(r, "coord", getattr(r, "pos", Coordinate(x=0, y=0))))
            fault = getattr(r, "fault", None)
            nearest_chg = (
                min((coord.manhattan_distance(c.pos) for c in chargers), default=None)
                if chargers
                else None
            )
            summary = BriefRobotSummary(
                robot_id=rid,
                state=st_val,
                battery_percent=round(bat, 1),
                current_coord=coord,
                current_task_type=getattr(r, "current_task_id", None),
                carrying_tote=bool(getattr(r, "carrying", False)),
                destination=destinations.get(rid),
                blocked_ticks=blocked_ticks,
                waiting_for_robot_id=waiting_lookup.get(rid),
                nearest_charger_distance=nearest_chg,
                has_valid_route=not any(dl.no_route_available and rid in dl.robots_involved for dl in deadlocks),
                fault=fault,
            )
            robots_overview.append(summary)

            is_crit = (
                bat < max(25.0, low_bat_thresh + 5.0)
                or "FAULT" in st_val
                or "UNAVAILABLE" in st_val
                or blocked_ticks >= no_progress_ticks
                or rid in deadlocked_ids
                or fault is not None
            )
            if is_crit and len(critical_robots) < self.max_robots:
                critical_robots.append(summary)

        # 6. Congested cells
        congested: list[Coordinate] = []
        for dl in deadlocks:
            for c in dl.conflict_cells:
                if c not in congested:
                    congested.append(c)
        if hasattr(engine, "safety_guard") and hasattr(engine.safety_guard, "recent_conflicts"):
            for c in list(engine.safety_guard.recent_conflicts)[-5:]:
                if c not in congested:
                    congested.append(c)

        # 7. Active alert IDs
        alerts = list(dynamic.alerts.values()) if isinstance(dynamic.alerts, dict) else list(dynamic.alerts)
        active_alerts = [
            getattr(a, "alert_id", getattr(a, "id", ""))
            for a in alerts
            if not getattr(a, "cleared", False)
        ]

        brief = SituationBrief(
            tick=tick,
            trigger=trigger,
            kpis=brief_kpis,
            at_risk_orders=at_risk_list,
            station_queues=station_queues,
            critical_robots=critical_robots,
            robots_overview=robots_overview[:20],
            congested_cells=congested[:8],
            deadlocks_detected=deadlocks[:5],
            active_alert_ids=active_alerts[:10],
            held_zone_ids=held_zone_ids or [],
            available_zones=available_zones,
            available_chargers=charger_ids,
            recent_decision_ids=recent_decision_ids or [],
            recent_outcomes=recent_outcomes or [],
            failed_command_hints=failed_command_hints or [],
            battery_thresholds={
                "low_battery_threshold": low_bat_thresh,
                "critical_battery_threshold": crit_bat_thresh,
            },
        )
        brief.brief_hash = brief.compute_hash()
        return brief
