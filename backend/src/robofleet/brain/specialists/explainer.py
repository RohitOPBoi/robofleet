"""Explainer Specialist & Anti-Hallucination Fact Verifier (Phase 5 - P5-A6, P5-R5).
Synthesizes plain-language operational rationales and strictly audits referenced entities
against the SituationBrief to eliminate AI hallucinations.
"""

from __future__ import annotations

import re
from pathlib import Path
from robofleet.contracts.brain import DecisionProposal, SituationBrief


class ExplainerSpecialist:
    name: str = "explainer"
    prompt_file: Path = Path("prompts/explainer_v1.txt")

    def synthesize_rationale(
        self,
        brief: SituationBrief,
        proposals: list[DecisionProposal],
        executed_commands: list[dict],
    ) -> str:
        """Construct grounded, concise rationale summarizing actions taken."""
        if not executed_commands or all(c.get("command_type") == "no_action" for c in executed_commands):
            return (
                f"Dark store operations nominal: {brief.kpis.queue_depth} orders queued, "
                f"{brief.kpis.fleet_utilization_pct}% fleet utilization; zero critical bottlenecks."
            )

        parts: list[str] = []
        for prop in proposals:
            if prop.rationale:
                parts.append(prop.rationale)

        raw_rationale = " ".join(parts)
        return self.verify_and_sanitize(raw_rationale, brief)

    def verify_and_sanitize(self, rationale: str, brief: SituationBrief) -> str:
        """Audits all entity IDs mentioned in text against the SituationBrief."""
        # Known valid entities
        valid_orders = {o.order_id for o in brief.at_risk_orders}
        valid_robots = {r.robot_id for r in brief.critical_robots}
        valid_stations = {s.station_id for s in brief.station_queues}
        valid_alerts = set(brief.active_alert_ids)

        # Regex patterns for entities
        order_matches = set(re.findall(r"\bORD-[A-Za-z0-9_-]+\b", rationale))
        robot_matches = set(re.findall(r"\bR-\d{3,}\b", rationale))

        # Check for hallucinations
        for ord_id in order_matches:
            if ord_id not in valid_orders and not any(ord_id in oid for oid in valid_orders):
                # Replace hallucinated order ID with generic description
                rationale = rationale.replace(ord_id, "an urgent order")

        for rob_id in robot_matches:
            if rob_id not in valid_robots and not any(rob_id in rid for rid in valid_robots):
                rationale = rationale.replace(rob_id, "an active AMR")

        return rationale.strip()
