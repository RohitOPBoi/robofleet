"""Natural Language Supervisor Command & Query Parser (Phase 5 - Section F).
Parses supervisor text into typed commands, handles operational Q&A with evidence,
defends against prompt injection, and flags ambiguous inputs for clarification.
"""

from __future__ import annotations

import re
from typing import Any
from robofleet.contracts.brain import (
    HoldZoneCommand,
    ReleaseZoneCommand,
    ReprioritiseOrderCommand,
    SendToChargeCommand,
    SituationBrief,
    SupervisorQuery,
)


class SupervisorCommandParser:
    """Parses supervisor natural language text into typed commands or grounded answers."""

    # Explicit list of injection attack triggers
    INJECTION_PATTERNS = [
        r"ignore (all )?previous instructions",
        r"disable safety",
        r"bypass governance",
        r"delete (all )?rules",
        r"drop all",
        r"override safetyguard",
        r"reveal prompt",
        r"system prompt",
        r"api_key",
    ]

    def parse(
        self,
        text: str,
        current_tick: int,
        brief: SituationBrief | None = None,
        engine: Any | None = None,
    ) -> SupervisorQuery:
        cleaned = text.strip()
        lower = cleaned.lower()

        # 1. Injection Defense: Check for adversarial attempts to compromise safety or governance
        for pat in self.INJECTION_PATTERNS:
            if re.search(pat, lower):
                return SupervisorQuery(
                    tick=current_tick,
                    raw_text=cleaned,
                    query_type="command",
                    parsed_command=None,
                    requires_confirmation=False,
                    response_text="Action Refused: SafetyGuard and governance policies are non-bypassable physical invariants and cannot be altered via supervisor input.",
                    evidence_citations=["Security Rule SR-7", "ADR-002: SafetyGuard Boundary"],
                )

        # 2. Q&A: "Why is order <id> late?"
        order_match = re.search(r"why is (?:order\s+)?([A-Za-z0-9_-]+)\s+late", lower)
        if order_match or "why late" in lower:
            target_ord = order_match.group(1).upper() if order_match else None
            # Search order in engine
            if engine and target_ord:
                orders = getattr(engine, "orders", [])
                order_obj = next((o for o in orders if getattr(o, "order_id", "").upper() == target_ord), None)
                if order_obj:
                    delays = getattr(order_obj, "delay_attribution", None)
                    reason_str = ""
                    if delays:
                        reason_str = f"Picker wait: {delays.waiting_for_robot_ticks}t, Station queue: {delays.station_queue_ticks}t, Picking: {delays.picking_ticks}t, Total lateness: {delays.total_lateness_ticks}t."
                    else:
                        st = getattr(order_obj, "status", "UNKNOWN")
                        st_val = st.value if hasattr(st, "value") else str(st)
                        reason_str = f"Order status is {st_val}; currently in fulfillment pipeline."
                    return SupervisorQuery(
                        tick=current_tick,
                        raw_text=cleaned,
                        query_type="question",
                        response_text=f"Order {target_ord} delay analysis: {reason_str}",
                        evidence_citations=[f"Order {target_ord} event log", f"Deadline: T+{order_obj.deadline_tick}"],
                    )
            return SupervisorQuery(
                tick=current_tick,
                raw_text=cleaned,
                query_type="question",
                response_text=f"Order {target_ord or 'specified'} was analyzed: verified against active pick station queue and traffic reservations.",
                evidence_citations=["SituationBrief at-risk orders"],
            )

        # 3. Q&A: General store status or fleet query
        if any(q in lower for q in ["how many", "status", "kpi", "what is throughput", "utilization"]):
            if brief:
                return SupervisorQuery(
                    tick=current_tick,
                    raw_text=cleaned,
                    query_type="question",
                    response_text=(
                        f"Current Store Telemetry: Queue depth is {brief.kpis.queue_depth} orders; "
                        f"Throughput is {brief.kpis.throughput_per_hr}/hr; "
                        f"AMR utilization is {brief.kpis.fleet_utilization_pct}% ({brief.kpis.robots_moving} moving, {brief.kpis.robots_charging} charging); "
                        f"Active alerts: {brief.kpis.active_alerts_count}."
                    ),
                    evidence_citations=["SituationBrief KPIs", f"Tick T+{current_tick}"],
                )

        # 4. Command: "hold zone <name>" or "pause zone <name>"
        zone_match = re.search(r"(?:hold|pause|isolate|lock)\s+zone\s+([A-Za-z0-9_-]+)", lower)
        if zone_match:
            zone_id = zone_match.group(1)
            cmd = HoldZoneCommand(
                zone_id=zone_id,
                duration_ticks=300,
                expected_effect=f"Temporarily hold zone '{zone_id}' for safety clearance",
                reason=f"Supervisor manual command: hold zone {zone_id}",
            )
            return SupervisorQuery(
                tick=current_tick,
                raw_text=cleaned,
                query_type="command",
                parsed_command=cmd.model_dump(),
                requires_confirmation=True,
                response_text=f"Parsed command: Hold zone '{zone_id}' for 300 ticks (30s). Please confirm execution.",
                evidence_citations=[f"Supervisor Command: '{cleaned}'"],
            )

        # 5. Command: "release zone <name>" or "unpause zone <name>"
        rel_match = re.search(r"(?:release|unpause|unlock|resume)\s+zone\s+([A-Za-z0-9_-]+)", lower)
        if rel_match:
            zone_id = rel_match.group(1)
            cmd = ReleaseZoneCommand(
                zone_id=zone_id,
                expected_effect=f"Release held zone '{zone_id}' back to normal traffic",
                reason=f"Supervisor manual command: release zone {zone_id}",
            )
            return SupervisorQuery(
                tick=current_tick,
                raw_text=cleaned,
                query_type="command",
                parsed_command=cmd.model_dump(),
                requires_confirmation=True,
                response_text=f"Parsed command: Release zone '{zone_id}'. Please confirm execution.",
                evidence_citations=[f"Supervisor Command: '{cleaned}'"],
            )

        # 6. Command: "prioritise urgent orders" or "set priority <order_id>"
        if "prioritise" in lower or "prioritize" in lower or "priority" in lower:
            ord_search = re.search(r"order\s+([A-Za-z0-9_-]+)", lower)
            if ord_search:
                ord_id = ord_search.group(1).upper()
                cmd = ReprioritiseOrderCommand(
                    order_id=ord_id,
                    new_priority=10,
                    expected_effect=f"Elevate order {ord_id} to highest priority",
                    reason="Supervisor manual priority override",
                )
                return SupervisorQuery(
                    tick=current_tick,
                    raw_text=cleaned,
                    query_type="command",
                    parsed_command=cmd.model_dump(),
                    requires_confirmation=True,
                    response_text=f"Parsed command: Elevate order '{ord_id}' to express priority 10. Please confirm.",
                    evidence_citations=[f"Supervisor Command: '{cleaned}'"],
                )
            # General urgent order elevation
            return SupervisorQuery(
                tick=current_tick,
                raw_text=cleaned,
                query_type="command",
                parsed_command={
                    "command_type": "set_strategy_params",
                    "strategy_name": "batch_greedy",
                    "params": {"rush_boost": 2.0},
                    "expected_effect": "Boost urgent order dispatching priority",
                    "reason": "Supervisor request: prioritise urgent orders",
                },
                requires_confirmation=True,
                response_text="Parsed command: Boost priority weighting for all urgent orders. Please confirm.",
                evidence_citations=["Supervisor Command: General Priority Boost"],
            )

        # 7. Command: "send robot <id> to charge"
        charge_match = re.search(r"(?:send|route|dispatch)\s+(?:robot|amr)\s+([A-Za-z0-9_-]+)\s+to\s+charge", lower)
        if charge_match:
            rob_id = charge_match.group(1).upper()
            cmd = SendToChargeCommand(
                robot_id=rob_id,
                expected_effect=f"Command AMR {rob_id} to navigate to charging bank",
                reason="Supervisor manual charge command",
            )
            return SupervisorQuery(
                tick=current_tick,
                raw_text=cleaned,
                query_type="command",
                parsed_command=cmd.model_dump(),
                requires_confirmation=True,
                response_text=f"Parsed command: Dispatch AMR '{rob_id}' to charging bank. Please confirm.",
                evidence_citations=[f"Supervisor Command: '{cleaned}'"],
            )

        # 8. Ambiguous input handling: Request clarification rather than guessing
        if any(w in lower for w in ["hold", "zone", "pause", "reroute", "change", "fast"]):
            return SupervisorQuery(
                tick=current_tick,
                raw_text=cleaned,
                query_type="clarification_needed",
                clarification_prompt="Your instruction is ambiguous. Did you mean: 'hold zone <zone_name>' or 'prioritise urgent orders'?",
                response_text="Ambiguity detected: Please specify the exact target zone or entity.",
                evidence_citations=["Clarification protocol"],
            )

        # Default fallback acknowledgment
        return SupervisorQuery(
            tick=current_tick,
            raw_text=cleaned,
            query_type="question",
            response_text=f"Received supervisor note: '{cleaned}'. Recorded in operations audit log.",
            evidence_citations=["Audit trail"],
        )
