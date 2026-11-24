"""Mission Orchestrator (Phase 5).
Central event-driven decision maker uniting Specialists, Governance Layer,
LLM Provider Port, and the Simulation Engine.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Literal

from robofleet.brain.brief import SituationBriefBuilder
from robofleet.brain.governance import GovernanceLayer
from robofleet.brain.providers.anthropic import AnthropicProvider
from robofleet.brain.providers.base import LLMProvider, LLMProviderResult
from robofleet.brain.providers.heuristic import HeuristicProvider
from robofleet.brain.providers.replay import ReplayProvider
from robofleet.brain.specialists.exceptions import ExceptionsRecoverySpecialist
from robofleet.brain.specialists.explainer import ExplainerSpecialist
from robofleet.brain.specialists.planner import PlannerSpecialist
from robofleet.brain.specialists.traffic import TrafficFleetSpecialist
from robofleet.contracts.brain import Decision, DecisionProposal, SituationBrief
from robofleet.contracts.robot import RobotState

logger = logging.getLogger(__name__)


class MissionOrchestrator:
    """Central AI decision engine coordinating specialists and governance."""

    def __init__(
        self,
        engine: Any,
        provider_name: Literal["heuristic", "anthropic", "replay"] = "heuristic",
        rules_dir: str = "rules",
        decisions_log_path: Path | str = "runs/decisions.ndjson",
    ) -> None:
        self.engine = engine
        self.enabled: bool = True  # Mode: True = AI Mode, False = Baseline Mode
        self.provider_name = provider_name
        self.decisions_log_path = Path(decisions_log_path)
        self.decisions_log_path.parent.mkdir(parents=True, exist_ok=True)

        # Core Components
        self.brief_builder = SituationBriefBuilder()
        self.governance = GovernanceLayer(rules_dir=rules_dir)

        # 4 Specialists
        self.planner = PlannerSpecialist()
        self.traffic = TrafficFleetSpecialist()
        self.exceptions = ExceptionsRecoverySpecialist()
        self.explainer = ExplainerSpecialist()
        self.specialists = [self.planner, self.traffic, self.exceptions, self.explainer]

        # Providers
        self.heuristic_provider = HeuristicProvider()
        self.anthropic_provider = AnthropicProvider()
        self.replay_provider = ReplayProvider()

        # Telemetry & State
        self.decisions: list[Decision] = []
        self.last_decision_tick: int = -999
        self.held_zones: set[str] = set()
        self.trigger_cooldowns: dict[str, int] = {}

    def get_active_provider(self) -> LLMProvider:
        if self.provider_name == "anthropic":
            return self.anthropic_provider
        if self.provider_name == "replay":
            return self.replay_provider
        return self.heuristic_provider

    def set_mode(self, enabled: bool) -> None:
        self.enabled = enabled
        logger.info("[Orchestrator] AI Mode set to %s", "ENABLED" if enabled else "BASELINE")

    def set_provider(self, name: Literal["heuristic", "anthropic", "replay"]) -> None:
        self.provider_name = name
        logger.info("[Orchestrator] Provider set to %s", name)

    def should_trigger(self, tick: int) -> tuple[bool, str]:
        """Debounced check for decision triggers."""
        if not self.enabled:
            return False, ""

        dynamic = self.engine.dynamic_state if hasattr(self.engine, "dynamic_state") else self.engine.get_dynamic_state()
        kpi = dynamic.kpis

        # 1. At-risk orders trigger (cooldown 10 ticks = 1s)
        at_risk_orders = int(kpi.get("at_risk_orders", 0) if isinstance(kpi, dict) else getattr(kpi, "at_risk_orders", 0))
        if at_risk_orders > 0:
            if tick - self.trigger_cooldowns.get("at_risk", -999) > 10:
                self.trigger_cooldowns["at_risk"] = tick
                return True, "order_at_risk"

        # 2. Critical battery trigger (< 25%)
        robots = list(dynamic.robots.values()) if isinstance(dynamic.robots, dict) else list(dynamic.robots)
        for r in robots:
            bat = float(getattr(r, "battery_pct", getattr(r, "battery_percent", 100.0)))
            st = getattr(r, "state", "")
            st_val = st.value if hasattr(st, "value") else str(st)
            if bat < 25.0 and st_val != "CHARGING":
                if tick - self.trigger_cooldowns.get("battery", -999) > 15:
                    self.trigger_cooldowns["battery"] = tick
                    return True, "critical_battery"

        # 3. Station queue imbalance (queue >= 4)
        stations = getattr(self.engine.layout, "stations", [])
        for st in stations:
            st_id = getattr(st, "station_id", "")
            q_len = 0
            if hasattr(self.engine, "station_mgr") and hasattr(self.engine.station_mgr, "queues"):
                q_len = len(self.engine.station_mgr.queues.get(st_id, []))
            if q_len == 0:
                q_len = sum(
                    1
                    for r in robots
                    if getattr(r, "current_task_id", None) == st_id
                )
            if q_len >= 4 and tick - self.trigger_cooldowns.get("station_queue", -999) > 20:
                self.trigger_cooldowns["station_queue"] = tick
                return True, "station_queue_imbalance"

        # 4. Periodic heartbeat (every 50 ticks = 5s)
        if tick - self.last_decision_tick >= 50:
            return True, "periodic_heartbeat"

        return False, ""

    async def step(self, tick: int) -> Decision | None:
        """Main orchestrator step executed each simulation tick."""
        # Expire any timed-out approval requests
        self.governance.approvals_queue.tick(tick)

        should_act, trigger = self.should_trigger(tick)
        if not should_act:
            return None

        self.last_decision_tick = tick
        t0 = time.perf_counter()

        # 1. Build Situation Brief
        recent_ids = [d.decision_id for d in self.decisions[-5:]]
        brief = self.brief_builder.build(
            tick=tick,
            trigger=trigger,
            engine=self.engine,
            recent_decision_ids=recent_ids,
            held_zone_ids=list(self.held_zones),
        )

        # 2. Query Active Provider
        provider = self.get_active_provider()
        res: LLMProviderResult = await provider.decide(brief, self.specialists)

        # 3. Governance Evaluation
        approved_commands: list[dict[str, Any]] = []
        governance_statuses: list[str] = []

        robots_list = list(self.engine.robots) if hasattr(self.engine, "robots") else list(self.engine.get_dynamic_state().robots)
        context_state = {
            "robots": {getattr(r, "robot_id", getattr(r, "id", "")): r.model_dump() for r in robots_list},
            "held_zones": list(self.held_zones),
            "zones": [z.name for z in getattr(self.engine.layout, "zones", [])],
        }

        for cmd in res.commands:
            verdict = self.governance.evaluate_command(
                command=cmd,
                decision_id=brief.brief_hash[:8],
                current_tick=tick,
                context_state=context_state,
            )
            governance_statuses.append(verdict.status)
            if verdict.is_approved:
                approved_commands.append(cmd)

        overall_governance: Literal["approved", "require_human", "denied"] = "approved"
        if "denied" in governance_statuses:
            overall_governance = "denied" if not approved_commands else "approved"
        elif "require_human" in governance_statuses:
            overall_governance = "require_human"

        # 4. Execute Approved Commands on SimEngine
        execution_status: Literal["success", "partial", "failed", "rejected_by_safety"] = "success"
        for cmd in approved_commands:
            try:
                self._execute_command(cmd, tick)
            except Exception as e:
                logger.error("[Orchestrator] Execution error for command %s: %s", cmd, e)
                execution_status = "partial"

        # 5. Synthesize Grounded Rationale
        rationale = self.explainer.synthesize_rationale(brief, res.proposals, approved_commands)

        latency = (time.perf_counter() - t0) * 1000.0

        decision = Decision(
            tick=tick,
            trigger=trigger,
            brief_hash=brief.brief_hash,
            proposals=res.proposals,
            final_commands=approved_commands,
            governance_outcome=overall_governance,
            execution_result=execution_status,
            observed_outcome="improved" if approved_commands else "neutral",
            latency_ms=round(latency, 2),
            token_usage=res.token_usage,
            cost_usd=res.cost_usd,
            provider_mode=provider.name,  # type: ignore
            rationale=rationale,
        )

        self.decisions.append(decision)
        self._append_decision_to_log(decision)
        return decision

    def _execute_command(self, cmd: dict[str, Any], tick: int) -> None:
        ctype = cmd.get("command_type")

        if ctype == "reprioritise_order":
            ord_id = cmd.get("order_id")
            new_p = cmd.get("new_priority", 10)
            orders = getattr(self.engine, "orders", [])
            for order in orders:
                if order.order_id == ord_id:
                    order.priority = new_p
                    break

        elif ctype == "send_to_charge":
            rob_id = cmd.get("robot_id")
            robots = getattr(self.engine, "robots", [])
            for robot in robots:
                if robot.robot_id == rob_id:
                    robot.state = RobotState.CHARGING
                    break

        elif ctype == "hold_zone":
            zone_id = cmd.get("zone_id")
            if zone_id:
                self.held_zones.add(zone_id)

        elif ctype == "release_zone":
            zone_id = cmd.get("zone_id")
            if zone_id and zone_id in self.held_zones:
                self.held_zones.remove(zone_id)

        elif ctype == "set_station_policy":
            st_id = cmd.get("station_id")
            for s in getattr(self.engine.layout, "stations", []):
                if getattr(s, "station_id", "") == st_id:
                    if not hasattr(s, "metadata") or s.metadata is None:
                        s.metadata = {}
                    s.metadata["max_queue_depth"] = cmd.get("max_queue_depth", 6)

        elif ctype == "reassign_task":
            rob_id = cmd.get("robot_id")
            if rob_id and hasattr(self.engine, "chaos_engine"):
                self.engine.chaos_engine.recovery_mgr.reassign_robot_tasks(rob_id, tick)

        elif ctype == "substitute_item":
            ord_id = cmd.get("order_id")
            sku_id = cmd.get("sku_id")
            qty = cmd.get("quantity", 1)
            reason = cmd.get("reason", "ai_arbitrated_substitution")
            if ord_id and sku_id and hasattr(self.engine, "chaos_engine"):
                self.engine.chaos_engine.recovery_mgr.substitute_missing_or_damaged_item(
                    order_id=ord_id, sku_id=sku_id, quantity=qty, reason=reason, tick=tick
                )

        elif ctype == "reroute_station":
            st_id = cmd.get("station_id")
            if st_id and hasattr(self.engine, "chaos_engine"):
                self.engine.chaos_engine.recovery_mgr.rebalance_station_queues(st_id, tick)

        elif ctype == "clear_fault":
            t_id = cmd.get("target_id")
            if t_id and hasattr(self.engine, "chaos_engine"):
                self.engine.chaos_engine.resolve_fault(t_id, tick)

    def _append_decision_to_log(self, decision: Decision) -> None:
        try:
            with open(self.decisions_log_path, "a", encoding="utf-8") as f:
                f.write(decision.model_dump_json() + "\n")
        except Exception as e:
            logger.warning("[Orchestrator] Failed writing to decisions log: %s", e)
