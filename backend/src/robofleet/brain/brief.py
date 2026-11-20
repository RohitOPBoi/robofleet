"""Situation Brief Builder (Phase 5).
Constructs bounded, deterministic world briefs for the AI Operations Brain.
Never exposes raw full state; extracts operational signals within a token budget.
"""

from __future__ import annotations

from typing import Any

from robofleet.contracts.brain import (
    BriefKPIs,
    BriefOrderSummary,
    BriefRobotSummary,
    BriefStationQueue,
    SituationBrief,
)
from robofleet.contracts.common import Coordinate


class SituationBriefBuilder:
    """Builds a compact, deterministic SituationBrief from live simulation state."""

    def __init__(self, max_at_risk: int = 10, max_robots: int = 10) -> None:
        self.max_at_risk = max_at_risk
        self.max_robots = max_robots

    def build(
        self,
        tick: int,
        trigger: str,
        engine: Any,
        recent_decision_ids: list[str] | None = None,
        held_zone_ids: list[str] | None = None,
    ) -> SituationBrief:
        dynamic = engine.dynamic_state if hasattr(engine, "dynamic_state") else engine.get_dynamic_state()
        kpi_obj = dynamic.kpis

        # 1. KPIs
        if isinstance(kpi_obj, dict):
            moving = int(kpi_obj.get("robots_moving", 0))
            idle = int(kpi_obj.get("robots_idle", 0))
            charging = int(kpi_obj.get("robots_charging", 0))
            q_depth = int(kpi_obj.get("queue_depth", 0))
            thru = float(kpi_obj.get("throughput_orders_per_hr", kpi_obj.get("throughput_per_hr", 0.0)))
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
        )

        # 2. At-risk orders (sorted by deadline urgency)
        orders = list(dynamic.orders.values()) if isinstance(dynamic.orders, dict) else list(dynamic.orders)
        at_risk_list: list[BriefOrderSummary] = []
        sorted_orders = sorted(orders, key=lambda x: max(0, getattr(x, "deadline_tick", 999999) - tick))
        for o in sorted_orders:
            deadline_rem = max(0, getattr(o, "deadline_tick", 999999) - tick)
            is_at_risk = getattr(o, "at_risk", False) or deadline_rem < 200
            st = getattr(o, "status", "RECEIVED")
            st_val = st.value if hasattr(st, "value") else str(st)
            if is_at_risk and st_val not in ("HANDED_OVER", "DELIVERED", "CANCELLED", "FAILED"):
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

        # 3. Station queues
        station_queues: list[BriefStationQueue] = []
        stations = getattr(engine.layout, "stations", [])
        robots = list(dynamic.robots.values()) if isinstance(dynamic.robots, dict) else list(dynamic.robots)
        for st in stations:
            st_id = getattr(st, "station_id", "")
            q_len = 0
            if hasattr(engine, "station_mgr") and hasattr(engine.station_mgr, "queues"):
                q_len = len(engine.station_mgr.queues.get(st_id, []))
            if q_len == 0:
                q_len = sum(
                    1
                    for r in robots
                    if getattr(r, "current_task_id", None) == st_id
                )
            station_queues.append(
                BriefStationQueue(
                    station_id=st_id,
                    queue_length=q_len,
                    avg_service_time_ticks=30.0,
                )
            )

        # 4. Critical robots (low battery, faulted, or long-blocked)
        critical_robots: list[BriefRobotSummary] = []
        for r in robots:
            bat = getattr(r, "battery_pct", getattr(r, "battery_percent", 100.0))
            st = getattr(r, "state", "IDLE")
            st_val = st.value if hasattr(st, "value") else str(st)
            blocked_ticks = getattr(r, "blocked_ticks", 0)
            if float(bat) < 30.0 or "FAULT" in st_val or "UNAVAILABLE" in st_val or blocked_ticks > 15:
                coord = getattr(r, "cell", getattr(r, "coord", getattr(r, "pos", Coordinate(x=0, y=0))))
                critical_robots.append(
                    BriefRobotSummary(
                        robot_id=getattr(r, "robot_id", getattr(r, "id", "")),
                        state=st_val,
                        battery_percent=round(float(bat), 1),
                        current_coord=coord,
                        current_task_type=getattr(r, "current_task_id", None),
                        carrying_tote=bool(getattr(r, "carrying", False)),
                    )
                )
            if len(critical_robots) >= self.max_robots:
                break

        # 5. Congested cells
        congested: list[Coordinate] = []
        if hasattr(engine, "safety_guard") and hasattr(engine.safety_guard, "recent_conflicts"):
            congested = list(engine.safety_guard.recent_conflicts)[-5:]

        # 6. Active alert IDs
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
            congested_cells=congested,
            active_alert_ids=active_alerts[:10],
            held_zone_ids=held_zone_ids or [],
            recent_decision_ids=recent_decision_ids or [],
        )
        brief.brief_hash = brief.compute_hash()
        return brief
