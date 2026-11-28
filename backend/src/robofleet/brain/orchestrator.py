"""Central AI Fleet Operations Orchestrator.

Coordinates heuristic decision logic, Cloud AI Mode (OpenAI-compatible &
Anthropic adapters), Local LLM Mode (Ollama), deterministic replay, four
domain specialists, deadlock detection/recovery, YAML-policy governance,
non-blocking asynchronous inference, staleness rejection, and post-execution
outcome measurement.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from pydantic import ValidationError

from robofleet.brain.brief import SituationBriefBuilder
from robofleet.brain.credentials import SecretCredentialStore
from robofleet.brain.deadlock import DeadlockAnalyzer, _find_safe_yield_cell
from robofleet.brain.governance import GovernanceLayer
from robofleet.brain.providers.ai_mode import UnifiedAIProvider
from robofleet.brain.providers.base import LLMProvider, LLMProviderResult
from robofleet.brain.providers.heuristic import HeuristicProvider
from robofleet.brain.providers.ollama import OllamaProvider
from robofleet.brain.providers.replay import ReplayProvider
from robofleet.brain.specialists.exceptions import ExceptionsRecoverySpecialist
from robofleet.brain.specialists.explainer import ExplainerSpecialist
from robofleet.brain.specialists.planner import PlannerSpecialist
from robofleet.brain.specialists.traffic import TrafficFleetSpecialist
from robofleet.config.models import AICloudConfig, BrainConfig, LocalLLMConfig
from robofleet.contracts.brain import (
    BriefDeadlockInfo,
    BriefOutcomeSummary,
    Decision,
    SituationBrief,
    validate_brain_command,
)
from robofleet.contracts.common import Coordinate
from robofleet.contracts.order import OrderStatus
from robofleet.contracts.robot import RobotState

logger = logging.getLogger(__name__)

OperatingMode = Literal["heuristic", "ai", "local_llm", "replay"]

MAX_DECISION_HISTORY = 250
MAX_OUTCOME_HISTORY = 8
MAX_FAILED_HINTS = 6
DEFAULT_AVOID_TTL_TICKS = 20
DEFAULT_MOVE_TTL_TICKS = 30
MAX_AVOID_CELLS_PER_CMD = 25
MIN_TRIGGER_COOLDOWN_TICKS = 3
DEADLOCK_TRIGGER_COOLDOWN_TICKS = 6
HIGH_PRIORITY_THRESHOLD = 8
IMMINENT_SLA_TICKS = 120
QUEUE_IMBALANCE_DELTA = 2
MAX_STATION_QUEUE_LIMIT = 20
DEFAULT_CHARGE_PRIORITY_HOLD = 10


@dataclass
class _PendingInference:
    """Tracks an asynchronous in-flight LLM decision task."""

    task: asyncio.Task[LLMProviderResult]
    brief: SituationBrief
    snapshot_tick: int
    snapshot_epoch: int
    operating_mode: OperatingMode


@dataclass
class _PendingOutcomeWindow:
    """Stores pre-execution KPIs to evaluate post-execution impact."""

    decision: Decision
    created_tick: int
    eval_tick: int
    world_epoch: int
    deadlocks_before: int
    blocked_before: int
    max_blocked_before: int
    completed_before: int
    at_risk_before: int
    target_robots: list[str] = field(default_factory=list)
    target_robot_batteries: dict[str, float] = field(default_factory=dict)
    command_types: list[str] = field(default_factory=list)


class MissionOrchestrator:
    """Central AI decision engine coordinating specialists, providers, and governance."""

    def __init__(
        self,
        engine: Any,
        provider_name: str | None = None,
        rules_dir: str = "rules",
        decisions_log_path: Path | str = "runs/decisions.ndjson",
        credential_store: SecretCredentialStore | None = None,
        brain_config: BrainConfig | None = None,
    ) -> None:
        self.engine = engine
        cfg_brain = brain_config or getattr(getattr(engine, "config", None), "brain", None)
        self.brain_config: BrainConfig = (
            cfg_brain.model_copy(deep=True) if isinstance(cfg_brain, BrainConfig) else BrainConfig()
        )
        self.credential_store = credential_store or SecretCredentialStore()

        self.enabled: bool = True
        self.mode: OperatingMode = self.brain_config.operating_mode
        self.provider_name: str = self.mode

        self.decisions_log_path = Path(decisions_log_path)
        self.decisions_log_path.parent.mkdir(parents=True, exist_ok=True)

        # Core Components
        self.brief_builder = SituationBriefBuilder()
        self.deadlock_analyzer = DeadlockAnalyzer()
        self.governance = GovernanceLayer(rules_dir=rules_dir)

        # 4 Domain Specialists
        self.planner = PlannerSpecialist()
        self.traffic = TrafficFleetSpecialist()
        self.exceptions = ExceptionsRecoverySpecialist()
        self.explainer = ExplainerSpecialist()
        self.specialists = [self.planner, self.traffic, self.exceptions, self.explainer]

        # Operating-mode providers
        self.heuristic_provider = HeuristicProvider()
        self.replay_provider = ReplayProvider()
        self.ai_provider = UnifiedAIProvider(
            cloud_config=self.brain_config.cloud,
            credential_store=self.credential_store,
        )
        self.local_provider = OllamaProvider()
        self.local_provider.apply_config(self.brain_config.local)
        # Backward-compatible attribute reference to internal Anthropic adapter
        self.anthropic_provider = self.ai_provider.anthropic_adapter

        # Operational state
        self.decisions: list[Decision] = []
        self._recent_outcomes: list[BriefOutcomeSummary] = []
        self._failed_command_hints: list[str] = []
        self._pending_outcomes: list[_PendingOutcomeWindow] = []
        self._updated_decisions: list[Decision] = []
        self._pending_inference: _PendingInference | None = None
        self._latest_deadlocks: list[BriefDeadlockInfo] = []
        self._latest_deadlocks_tick: int = -1

        self.last_decision_tick: int = -1
        self._last_trigger_attempt_tick: int = -100
        self._last_deadlock_trigger_tick: int = -100
        self._last_brief_hash: str = ""
        self._last_hash_tick: int = -100
        self._last_world_epoch: int = getattr(engine, "world_epoch", 1)

        # Operational telemetry counters
        self.stale_decisions_discarded: int = 0
        self.invalid_command_rejections: int = 0
        self.deadlocks_resolved: int = 0

        if provider_name is not None:
            self.set_provider(provider_name)

    @property
    def held_zones(self) -> set[str]:
        """Synchronized view of currently held zone IDs on the engine."""
        held = getattr(self.engine, "held_zones_until", None)
        if isinstance(held, dict):
            return set(held.keys())
        return set()

    def get_active_provider(self) -> LLMProvider:
        if self.mode == "ai":
            return self.ai_provider
        if self.mode == "local_llm":
            return self.local_provider
        if self.mode == "replay":
            return self.replay_provider
        return self.heuristic_provider

    def set_mode(self, enabled: bool) -> None:
        self.enabled = bool(enabled)
        if not self.enabled:
            self.cancel_pending_inference()

    def set_provider(self, name: str) -> None:
        """Select active operating mode (`heuristic`, `ai`, `local_llm`, `replay`, or `baseline`)."""
        norm = (name or "").strip().lower()
        if norm == "baseline":
            self.enabled = False
            return
        if norm == "anthropic":
            # Legacy CLI/API alias: route into AI Mode using Anthropic adapter
            self.enabled = True
            self.mode = "ai"
            self.provider_name = "ai"
            cloud_update = self.brain_config.cloud.model_copy(
                update={
                    "provider_type": "anthropic",
                    "provider_label": "Anthropic",
                    "api_compatibility": "anthropic_messages",
                    "base_url": self.brain_config.cloud.base_url
                    if "anthropic" in self.brain_config.cloud.base_url
                    else "https://api.anthropic.com",
                    "model": self.brain_config.cloud.model
                    if self.brain_config.cloud.provider_type == "anthropic"
                    else "claude-3-5-sonnet-20241022",
                }
            )
            self.update_ai_cloud_config(cloud_update)
        elif norm in ("ai", "cloud", "cloud_ai"):
            self.enabled = True
            self.mode = "ai"
            self.provider_name = "ai"
        elif norm in ("local_llm", "local", "ollama"):
            self.enabled = True
            self.mode = "local_llm"
            self.provider_name = "local_llm"
        elif norm == "replay":
            self.enabled = True
            self.mode = "replay"
            self.provider_name = "replay"
        elif norm == "heuristic":
            self.enabled = True
            self.mode = "heuristic"
            self.provider_name = "heuristic"
        else:
            raise ValueError(
                f"Unsupported operating mode '{name}'. Choose from: heuristic, ai, local_llm, replay, baseline."
            )

        self.brain_config.operating_mode = self.mode
        self.cancel_pending_inference()
        # Reset deduplication cooldown so the newly chosen provider can act promptly
        self._last_brief_hash = ""
        self._last_hash_tick = -100

    def update_ai_cloud_config(
        self,
        cfg: AICloudConfig | dict[str, Any],
        api_key: str | None = None,
        clear_api_key: bool = False,
    ) -> None:
        """Apply updated Cloud AI configuration and/or in-memory secret credentials."""
        if isinstance(cfg, dict):
            merged = self.brain_config.cloud.model_dump()
            merged.update(cfg)
            cfg_obj = AICloudConfig.model_validate(merged)
        else:
            cfg_obj = cfg

        self.brain_config.cloud = cfg_obj
        self.ai_provider.apply_config(cfg_obj)
        profile = self.ai_provider.current_profile_key

        if clear_api_key:
            self.credential_store.clear_key(profile)
        if api_key is not None and api_key.strip():
            self.credential_store.set_key(profile, api_key.strip())
            # Also store under generic 'custom'/'ai' or provider_type for adapter consistency
            if cfg_obj.provider_type != profile:
                self.credential_store.set_key(cfg_obj.provider_type, api_key.strip())
            adapter = self.ai_provider.get_active_adapter()
            if hasattr(adapter, "reset_circuit"):
                adapter.reset_circuit()

    def update_local_llm_config(self, cfg: LocalLLMConfig | dict[str, Any]) -> None:
        """Apply updated Local Ollama configuration."""
        if isinstance(cfg, dict):
            merged = self.brain_config.local.model_dump()
            merged.update(cfg)
            cfg_obj = LocalLLMConfig.model_validate(merged)
        else:
            cfg_obj = cfg
        self.brain_config.local = cfg_obj
        self.local_provider.apply_config(cfg_obj)
        self.local_provider.reset_circuit()

    def cancel_pending_inference(self) -> None:
        if self._pending_inference and not self._pending_inference.task.done():
            self._pending_inference.task.cancel()
        self._pending_inference = None

    def _sync_world_epoch(self) -> None:
        """Reset transient orchestrator buffers if simulation engine was restarted."""
        epoch = getattr(self.engine, "world_epoch", 1)
        if epoch != self._last_world_epoch:
            self.cancel_pending_inference()
            self._pending_outcomes.clear()
            self._updated_decisions.clear()
            self._recent_outcomes.clear()
            self._failed_command_hints.clear()
            self._latest_deadlocks = []
            self._latest_deadlocks_tick = -1
            self.last_decision_tick = -1
            self._last_trigger_attempt_tick = -100
            self._last_deadlock_trigger_tick = -100
            self._last_brief_hash = ""
            self._last_hash_tick = -100
            self._last_world_epoch = epoch

    def _get_deadlocks(self, tick: int) -> list[BriefDeadlockInfo]:
        if self._latest_deadlocks_tick != tick:
            self._latest_deadlocks = self.deadlock_analyzer.analyze(
                self.engine,
                no_progress_ticks=self.brain_config.deadlock_no_progress_ticks,
            )
            self._latest_deadlocks_tick = tick
        return self._latest_deadlocks

    def should_trigger(self, tick: int) -> tuple[bool, str]:
        """Event-driven trigger evaluation prioritizing deadlocks, faults, battery, and SLA."""
        if not self.enabled:
            return False, ""

        deadlocks = self._get_deadlocks(tick)
        if deadlocks and (tick - self._last_deadlock_trigger_tick) >= DEADLOCK_TRIGGER_COOLDOWN_TICKS:
            self._last_deadlock_trigger_tick = tick
            return True, "deadlock_detected"

        # Enforce brief cooldown for non-deadlock triggers so remote LLMs are not spammed
        if self.last_decision_tick >= 0 and (tick - self._last_trigger_attempt_tick) < MIN_TRIGGER_COOLDOWN_TICKS:
            return False, ""

        # 1. Active faulted/unavailable robot or chaos faults
        robots = getattr(self.engine, "robots", [])
        if any(r.fault is not None or r.state == RobotState.UNAVAILABLE for r in robots):
            return True, "robot_faulted"

        # 2. Critical battery threshold without active charging or AI charge route
        charge_overrides = getattr(self.engine, "ai_charge_overrides", {})
        crit_pct = self.brain_config.critical_battery_trigger_pct
        if any(
            r.battery_pct <= crit_pct
            and r.state != RobotState.CHARGING
            and r.robot_id not in charge_overrides
            for r in robots
        ):
            return True, "critical_battery"

        # 3. Stalled robot above deadlock threshold
        blocked_count = sum(1 for r in robots if r.blocked_ticks > 0)
        stalled_robots = [
            r for r in robots if r.blocked_ticks >= self.brain_config.deadlock_no_progress_ticks
        ]
        if stalled_robots:
            return True, "blocked_robot_stalled"

        # 4. At-risk orders
        for order in getattr(self.engine, "orders", []):
            if order.status in (OrderStatus.HANDED_OVER, OrderStatus.CANCELLED, OrderStatus.FAILED):
                continue
            sla_rem = getattr(order, "deadline_tick", tick + 500) - tick
            if getattr(order, "at_risk", False) or sla_rem < IMMINENT_SLA_TICKS:
                return True, "order_at_risk"

        # 5. Station queue imbalance
        station_mgr = getattr(self.engine, "station_mgr", None)
        if station_mgr and getattr(station_mgr, "robot_queues", None):
            q_lens = [len(q) for q in station_mgr.robot_queues.values()]
            if len(q_lens) >= 2 and (max(q_lens) - min(q_lens)) >= QUEUE_IMBALANCE_DELTA:
                return True, "station_queue_imbalance"

        # 6. Multi-robot congestion threshold
        if blocked_count >= self.brain_config.congestion_alert_threshold:
            return True, "congestion_threshold"

        # 7. Periodic heartbeat when active work or fleet state exists
        if tick - self.last_decision_tick >= self.brain_config.heartbeat_ticks and (
            tick > 0 or getattr(self.engine, "orders", [])
        ):
            return True, "periodic_heartbeat"

        return False, ""

    def _build_brief(self, tick: int, trigger: str) -> SituationBrief:
        recent_ids = [d.decision_id for d in self.decisions[-5:]]
        return self.brief_builder.build(
            tick=tick,
            trigger=trigger,
            engine=self.engine,
            recent_decision_ids=recent_ids,
            held_zone_ids=sorted(self.held_zones),
            recent_outcomes=list(self._recent_outcomes[-MAX_OUTCOME_HISTORY:]),
            failed_command_hints=list(self._failed_command_hints[-MAX_FAILED_HINTS:]),
        )

    def _governance_context(self) -> dict[str, Any]:
        station_mgr = getattr(self.engine, "station_mgr", None)
        station_count = len(getattr(station_mgr, "station_defs", {})) if station_mgr else 1
        return {
            "active_robot_count": len(self.engine.robots),
            "held_zones": sorted(self.held_zones),
            "station_count": max(1, station_count),
        }

    def _validate_command_against_live_state(
        self,
        cmd: dict[str, Any],
    ) -> tuple[bool, str, dict[str, Any]]:
        """Re-validates a proposed command against live engine state before governance/execution."""
        try:
            validated = validate_brain_command(cmd)
        except ValidationError as exc:
            self.invalid_command_rejections += 1
            return False, f"Invalid schema: {exc.errors()[0].get('msg', str(exc))}", cmd

        normalized = validated.model_dump()
        ctype = normalized.get("command_type", "")
        robots_by_id = {r.robot_id: r for r in self.engine.robots}
        orders_by_id = {o.order_id: o for o in self.engine.orders}
        station_defs = getattr(getattr(self.engine, "station_mgr", None), "station_defs", {})

        if ctype in ("yield_robot", "reroute_robot", "send_to_charge", "assign_task", "reassign_task"):
            r_id = normalized.get("robot_id")
            robot = robots_by_id.get(str(r_id))
            if robot is None:
                self.invalid_command_rejections += 1
                return False, f"Unknown robot '{r_id}'", normalized
            if ctype == "send_to_charge" and robot.state == RobotState.UNAVAILABLE:
                return False, f"Robot '{r_id}' is unavailable/faulted", normalized
            if ctype == "send_to_charge" and not getattr(self.engine.layout, "chargers", []):
                return False, "Layout has no charger stations", normalized

        if ctype in ("reprioritise_order", "substitute_item"):
            o_id = normalized.get("order_id")
            if o_id not in orders_by_id:
                self.invalid_command_rejections += 1
                return False, f"Unknown order '{o_id}'", normalized

        if ctype == "batch_orders":
            st_id = normalized.get("target_station_id")
            if st_id not in station_defs:
                self.invalid_command_rejections += 1
                return False, f"Unknown station '{st_id}'", normalized
            if not any(oid in orders_by_id for oid in normalized.get("order_ids", [])):
                self.invalid_command_rejections += 1
                return False, "No valid order_ids matched in batch_orders", normalized

        if ctype in ("reroute_station", "set_station_policy"):
            st_id = normalized.get("station_id")
            if st_id not in station_defs:
                self.invalid_command_rejections += 1
                return False, f"Unknown station '{st_id}'", normalized

        if ctype == "hold_zone":
            z_id = normalized.get("zone_id")
            if not any(z.name == z_id for z in self.engine.layout.zones):
                self.invalid_command_rejections += 1
                return False, f"Unknown zone '{z_id}'", normalized

        return True, "", normalized

    def _capture_outcome_window(
        self,
        decision: Decision,
        tick: int,
        executed_cmds: list[dict[str, Any]],
    ) -> None:
        robots = getattr(self.engine, "robots", [])
        orders = getattr(self.engine, "orders", [])
        deadlocks = self._get_deadlocks(tick)
        blocked_before = sum(1 for r in robots if r.blocked_ticks > 0)
        max_blocked_before = max((r.blocked_ticks for r in robots), default=0)
        completed_before = sum(1 for o in orders if o.status == OrderStatus.HANDED_OVER)
        at_risk_before = sum(
            1
            for o in orders
            if o.status not in (OrderStatus.HANDED_OVER, OrderStatus.CANCELLED, OrderStatus.FAILED)
            and getattr(o, "at_risk", False)
        )

        target_robots: list[str] = []
        target_batteries: dict[str, float] = {}
        cmd_types: list[str] = []
        robots_by_id = {r.robot_id: r for r in robots}
        for c in executed_cmds:
            ct = str(c.get("command_type", ""))
            if ct and ct != "no_action":
                cmd_types.append(ct)
            r_id = c.get("robot_id") or c.get("target_id")
            if isinstance(r_id, str) and r_id in robots_by_id and r_id not in target_robots:
                target_robots.append(r_id)
                target_batteries[r_id] = float(robots_by_id[r_id].battery_pct)

        if not cmd_types:
            return

        self._pending_outcomes.append(
            _PendingOutcomeWindow(
                decision=decision,
                created_tick=tick,
                eval_tick=tick + self.brain_config.outcome_eval_window_ticks,
                world_epoch=getattr(self.engine, "world_epoch", 1),
                deadlocks_before=len(deadlocks),
                blocked_before=blocked_before,
                max_blocked_before=max_blocked_before,
                completed_before=completed_before,
                at_risk_before=at_risk_before,
                target_robots=target_robots,
                target_robot_batteries=target_batteries,
                command_types=cmd_types,
            )
        )

    def _evaluate_pending_outcomes(self, tick: int, force: bool = False) -> None:
        """Measures real simulation delta after executed commands and records outcome feedback."""
        current_epoch = getattr(self.engine, "world_epoch", 1)
        remaining: list[_PendingOutcomeWindow] = []

        for item in self._pending_outcomes:
            if item.world_epoch != current_epoch:
                continue
            if not force and tick < item.eval_tick:
                remaining.append(item)
                continue

            robots = getattr(self.engine, "robots", [])
            orders = getattr(self.engine, "orders", [])
            robots_by_id = {r.robot_id: r for r in robots}

            deadlocks_after = len(
                self.deadlock_analyzer.analyze(
                    self.engine, no_progress_ticks=self.brain_config.deadlock_no_progress_ticks
                )
            )
            blocked_after = sum(1 for r in robots if r.blocked_ticks > 0)
            max_blocked_after = max((r.blocked_ticks for r in robots), default=0)
            completed_after = sum(1 for o in orders if o.status == OrderStatus.HANDED_OVER)
            at_risk_after = sum(
                1
                for o in orders
                if o.status not in (OrderStatus.HANDED_OVER, OrderStatus.CANCELLED, OrderStatus.FAILED)
                and getattr(o, "at_risk", False)
            )

            delta_deadlocks = deadlocks_after - item.deadlocks_before
            delta_blocked = blocked_after - item.blocked_before
            delta_completed = completed_after - item.completed_before
            delta_at_risk = at_risk_after - item.at_risk_before

            charging_progress = any(
                (r := robots_by_id.get(r_id)) is not None
                and (
                    r.state == RobotState.CHARGING
                    or r.battery_pct > item.target_robot_batteries.get(r_id, 100.0)
                )
                for r_id in item.target_robots
                if "send_to_charge" in item.command_types
            )
            fault_recovered = any(
                (r := robots_by_id.get(r_id)) is not None
                and r.fault is None
                and r.state != RobotState.UNAVAILABLE
                for r_id in item.target_robots
                if "clear_fault" in item.command_types
            )

            if item.deadlocks_before > 0 and deadlocks_after < item.deadlocks_before:
                self.deadlocks_resolved += item.deadlocks_before - deadlocks_after

            outcome: Literal["improved", "neutral", "worsened", "unknown"]
            if item.decision.execution_result == "failed":
                outcome = "worsened"
            elif (
                delta_deadlocks < 0
                or (item.blocked_before > 0 and delta_blocked < 0 and delta_deadlocks <= 0)
                or delta_completed > 0
                or delta_at_risk < 0
                or charging_progress
                or fault_recovered
            ):
                outcome = "improved"
            elif delta_deadlocks > 0 or delta_blocked >= 2:
                outcome = "worsened"
            else:
                outcome = "neutral"

            item.decision.observed_outcome = outcome
            item.decision.outcome_metrics = {
                "eval_tick": tick,
                "delta_deadlocks": delta_deadlocks,
                "delta_blocked": delta_blocked,
                "max_blocked_before": item.max_blocked_before,
                "max_blocked_after": max_blocked_after,
                "delta_completed": delta_completed,
                "delta_at_risk": delta_at_risk,
            }
            item.decision.decision_version += 1
            self._updated_decisions.append(item.decision)

            self._recent_outcomes.append(
                BriefOutcomeSummary(
                    decision_id=item.decision.decision_id,
                    tick=item.created_tick,
                    provider=item.decision.attribution or item.decision.provider_name,
                    commands=item.command_types,
                    observed_outcome=outcome,
                    summary=f"dDeadlock={delta_deadlocks}, dBlocked={delta_blocked}, dDone={delta_completed}",
                )
            )
            if len(self._recent_outcomes) > MAX_OUTCOME_HISTORY:
                self._recent_outcomes = self._recent_outcomes[-MAX_OUTCOME_HISTORY:]

        self._pending_outcomes = remaining

    def flush_pending_outcomes(self, tick: int) -> None:
        """Forces immediate evaluation of any open post-execution outcome windows."""
        self._evaluate_pending_outcomes(tick, force=True)

    def pop_updated_decisions(self) -> list[Decision]:
        """Returns and clears decisions whose observed_outcome updated since last drain."""
        updates = list(self._updated_decisions)
        self._updated_decisions.clear()
        return updates

    def _finalize_decision(
        self,
        res: LLMProviderResult,
        brief: SituationBrief,
        tick: int,
        trigger: str,
        stale_rejected: bool = False,
        stale_reason: str = "",
    ) -> Decision:
        proposals = res.proposals
        raw_commands: list[dict[str, Any]] = list(res.commands or [])
        rejected_cmds: list[dict[str, Any]] = list(res.rejected_commands or [])
        approved_cmds: list[dict[str, Any]] = []
        gov_outcome: Literal["approved", "require_human", "denied"] = "approved"
        gov_reasons: list[str] = []
        exec_result: Literal["success", "partial", "failed", "rejected_by_safety"] = "success"

        if stale_rejected:
            self.stale_decisions_discarded += 1
            gov_outcome = "denied"
            exec_result = "failed"
            gov_reasons.append(stale_reason or "Stale LLM response discarded because simulation advanced")
            for c in raw_commands:
                rejected_cmds.append({"command": c, "reason": stale_reason})
            raw_commands = []

        context_state = self._governance_context()
        temp_id = f"dec-{tick}-{brief.brief_hash[:6]}"

        if not stale_rejected:
            if not raw_commands and not proposals:
                approved_cmds.append({"command_type": "no_action", "reason": res.rationale})
            elif not raw_commands and proposals:
                # Never fabricate execution from raw proposal text if provider intentionally returned no commands
                approved_cmds.append({"command_type": "no_action", "reason": res.rationale})

            for cmd in raw_commands:
                ctype = cmd.get("command_type", "")
                if ctype == "no_action":
                    approved_cmds.append(cmd)
                    continue

                live_ok, live_err, normalized_cmd = self._validate_command_against_live_state(cmd)
                if not live_ok:
                    rejected_cmds.append({"command": cmd, "reason": live_err})
                    self._record_failed_hint(f"{ctype}: {live_err}")
                    continue

                verdict = self.governance.evaluate_command(
                    normalized_cmd,
                    decision_id=temp_id,
                    current_tick=tick,
                    context_state=context_state,
                )
                if verdict.status == "approved":
                    approved_cmds.append(normalized_cmd)
                elif verdict.status == "require_human":
                    gov_outcome = "require_human"
                    gov_reasons.append(verdict.reason)
                else:
                    if gov_outcome == "approved":
                        gov_outcome = "denied"
                    gov_reasons.append(verdict.reason)
                    rejected_cmds.append({"command": normalized_cmd, "reason": verdict.reason})

        # Execute approved commands cleanly and track real failures
        executed_ok = 0
        executed_failed = 0
        exec_notes: list[str] = []
        for cmd in approved_cmds:
            if cmd.get("command_type") == "no_action":
                continue
            ok, msg = self._execute_command(cmd, tick)
            if ok:
                executed_ok += 1
                exec_notes.append(msg)
            else:
                executed_failed += 1
                exec_notes.append(f"FAILED({cmd.get('command_type')}): {msg}")
                self._record_failed_hint(f"{cmd.get('command_type')}: {msg}")

        if not stale_rejected:
            if executed_failed > 0 and executed_ok == 0:
                exec_result = "failed"
            elif executed_failed > 0 and executed_ok > 0:
                exec_result = "partial"
            elif rejected_cmds and not executed_ok and not any(
                c.get("command_type") == "no_action" for c in approved_cmds
            ):
                exec_result = "rejected_by_safety" if gov_outcome == "denied" else "failed"

        rationale_parts = [res.rationale] if res.rationale else []
        if gov_reasons:
            rationale_parts.append("Governance: " + "; ".join(gov_reasons))
        if stale_rejected and stale_reason:
            rationale_parts.append(stale_reason)

        decision_provider_mode: Literal[
            "heuristic", "ai", "local_llm", "replay", "anthropic", "heuristic_fallback"
        ]
        raw_prov = (res.provider_name or "").strip().lower()
        if res.fallback_used or raw_prov in (
            "heuristic_fallback",
            "heuristic fallback",
            "safe_wait",
            "safe wait fallback",
        ):
            decision_provider_mode = "heuristic_fallback"
        elif res.operating_mode == "local_llm" or raw_prov == "ollama":
            decision_provider_mode = "local_llm"
        elif res.operating_mode == "ai":
            decision_provider_mode = "ai"
        elif res.operating_mode == "replay":
            decision_provider_mode = "replay"
        else:
            decision_provider_mode = "heuristic"

        decision = Decision(
            decision_id=temp_id,
            tick=tick,
            trigger=trigger,
            brief_hash=brief.brief_hash,
            proposals=proposals,
            final_commands=approved_cmds if approved_cmds else rejected_cmds,
            rejected_commands=rejected_cmds,
            governance_outcome=gov_outcome,
            execution_result=exec_result,
            observed_outcome="unknown",
            latency_ms=res.latency_ms,
            token_usage=res.token_usage,
            cost_usd=res.cost_usd,
            operating_mode=res.operating_mode,
            provider_mode=decision_provider_mode,
            provider_name=res.provider_name,
            model_name=res.model_name,
            fallback_used=res.fallback_used,
            fallback_reason=res.fallback_reason,
            attribution=res.attribution,
            situation_summary=res.situation_summary,
            traffic_plan=res.traffic_plan,
            unresolved_risks=res.unresolved_risks,
            confidence=res.confidence,
            rationale=" | ".join(rationale_parts),
        )

        self.decisions.append(decision)
        if len(self.decisions) > MAX_DECISION_HISTORY:
            self.decisions = self.decisions[-MAX_DECISION_HISTORY:]
        self.last_decision_tick = tick
        self._append_decision_to_log(decision)

        if not stale_rejected:
            self._capture_outcome_window(decision, tick, approved_cmds)

        self.engine.emit_event(
            "brain.decision",
            {
                "decision_id": decision.decision_id,
                "operating_mode": decision.operating_mode,
                "provider_mode": decision.provider_mode,
                "provider_name": decision.provider_name,
                "model_name": decision.model_name,
                "fallback_used": decision.fallback_used,
                "attribution": decision.attribution,
                "trigger": trigger,
                "outcome": gov_outcome,
                "execution_result": exec_result,
                "commands_count": len(approved_cmds),
            },
        )
        return decision

    def _record_failed_hint(self, hint: str) -> None:
        cleaned = hint.strip()[:140]
        if cleaned and cleaned not in self._failed_command_hints:
            self._failed_command_hints.append(cleaned)
            if len(self._failed_command_hints) > MAX_FAILED_HINTS:
                self._failed_command_hints = self._failed_command_hints[-MAX_FAILED_HINTS:]

    async def step(self, tick: int, force_trigger: bool = False) -> Decision | None:
        """Synchronous-await decision step used by CLI evals, chaos runs, and tests."""
        self._sync_world_epoch()
        self.governance.approvals_queue.tick(tick)
        self._evaluate_pending_outcomes(tick)

        if not self.enabled and not force_trigger:
            return None

        if force_trigger:
            trigger_reason = "manual_eval"
        else:
            should, trigger_reason = self.should_trigger(tick)
            if not should:
                return None

        self._last_trigger_attempt_tick = tick
        brief = self._build_brief(tick, trigger_reason)

        if (
            not force_trigger
            and not brief.deadlocks_detected
            and brief.brief_hash == self._last_brief_hash
            and (tick - self._last_hash_tick) < self.brain_config.dedup_cooldown_ticks
        ):
            return None

        self._last_brief_hash = brief.brief_hash
        self._last_hash_tick = tick

        snapshot_epoch = getattr(self.engine, "world_epoch", 1)
        provider = self.get_active_provider()
        res = await provider.decide(brief, self.specialists)

        current_epoch = getattr(self.engine, "world_epoch", 1)
        if current_epoch != snapshot_epoch:
            return self._finalize_decision(
                res=res,
                brief=brief,
                tick=tick,
                trigger=trigger_reason,
                stale_rejected=True,
                stale_reason="World restarted during inference (epoch mismatch)",
            )

        return self._finalize_decision(
            res=res,
            brief=brief,
            tick=tick,
            trigger=trigger_reason,
        )

    async def step_nonblocking(self, tick: int) -> Decision | None:
        """Non-blocking simulation-loop step: spawns background LLM calls so ticks never freeze."""
        self._sync_world_epoch()
        self.governance.approvals_queue.tick(tick)
        self._evaluate_pending_outcomes(tick)

        completed_decision: Decision | None = None

        # 1. Harvest finished background inference task if present
        if self._pending_inference is not None and self._pending_inference.task.done():
            pending = self._pending_inference
            self._pending_inference = None
            try:
                res = pending.task.result()
            except asyncio.CancelledError:
                res = None
            except Exception as exc:
                logger.warning("Background brain inference raised unexpected error: %s", exc)
                res = await self.heuristic_provider.decide(pending.brief, self.specialists)
                res.operating_mode = pending.operating_mode
                res.provider_name = "heuristic_fallback"
                res.provider_status = "fallback"
                res.fallback_used = True
                res.fallback_reason = str(exc)[:120]
                res.attribution = f"Heuristic fallback — deterministic provider ({res.fallback_reason})"

            if res is not None:
                current_epoch = getattr(self.engine, "world_epoch", 1)
                tick_age = tick - pending.snapshot_tick
                stale_reason = ""
                is_stale = False
                if current_epoch != pending.snapshot_epoch:
                    is_stale = True
                    stale_reason = "World restarted while LLM inference was running"
                elif tick_age > self.brain_config.max_decision_staleness_ticks:
                    is_stale = True
                    stale_reason = (
                        f"Stale LLM response dropped after {tick_age} ticks "
                        f"(limit {self.brain_config.max_decision_staleness_ticks})"
                    )

                completed_decision = self._finalize_decision(
                    res=res,
                    brief=pending.brief,
                    tick=tick,
                    trigger=pending.brief.trigger,
                    stale_rejected=is_stale,
                    stale_reason=stale_reason,
                )

        # 2. If enabled and no LLM task currently running, check trigger
        if not self.enabled or self._pending_inference is not None:
            return completed_decision

        should, trigger_reason = self.should_trigger(tick)
        if not should:
            return completed_decision

        self._last_trigger_attempt_tick = tick
        brief = self._build_brief(tick, trigger_reason)

        if (
            not brief.deadlocks_detected
            and brief.brief_hash == self._last_brief_hash
            and (tick - self._last_hash_tick) < self.brain_config.dedup_cooldown_ticks
        ):
            return completed_decision

        self._last_brief_hash = brief.brief_hash
        self._last_hash_tick = tick

        provider = self.get_active_provider()
        if self.mode in ("heuristic", "replay"):
            # Local deterministic providers complete in <1ms without blocking network I/O
            res = await provider.decide(brief, self.specialists)
            return self._finalize_decision(
                res=res,
                brief=brief,
                tick=tick,
                trigger=trigger_reason,
            )

        # Launch Cloud AI / Ollama HTTP inference asynchronously on the event loop
        snapshot_epoch = getattr(self.engine, "world_epoch", 1)
        task = asyncio.create_task(provider.decide(brief, self.specialists))
        self._pending_inference = _PendingInference(
            task=task,
            brief=brief,
            snapshot_tick=tick,
            snapshot_epoch=snapshot_epoch,
            operating_mode=self.mode,
        )
        return completed_decision

    def _assign_charge_route(
        self,
        robot_id: str,
        charger_id: str | None = None,
    ) -> tuple[bool, str]:
        robot = next((r for r in self.engine.robots if r.robot_id == robot_id), None)
        if not robot:
            return False, f"Robot '{robot_id}' not found"
        if robot.state == RobotState.UNAVAILABLE:
            return False, f"Robot '{robot_id}' is unavailable"
        chargers = list(getattr(self.engine.layout, "chargers", []))
        if not chargers:
            return False, "No charger cells defined in warehouse layout"

        chosen = None
        if charger_id:
            chosen = next((c for c in chargers if c.charger_id == charger_id), None)
        if chosen is None:
            occupied_chargers = {
                r.cell.as_tuple()
                for r in self.engine.robots
                if r.robot_id != robot_id and r.state == RobotState.CHARGING
            }
            chosen = min(
                chargers,
                key=lambda c: (
                    1 if c.pos.as_tuple() in occupied_chargers else 0,
                    robot.cell.manhattan_distance(c.pos),
                ),
            )

        self.engine.ai_charge_overrides[robot_id] = chosen.pos
        self.engine.ai_yield_directives.pop(robot_id, None)
        if robot.cell == chosen.pos:
            robot.state = RobotState.CHARGING
        return True, f"Routed {robot_id} to charger {chosen.charger_id} at ({chosen.pos.x},{chosen.pos.y})"

    def _execute_command(self, cmd: dict[str, Any], tick: int) -> tuple[bool, str]:
        """Executes a governed brain command directly against SimEngine state."""
        ctype = cmd.get("command_type", "")
        robots_by_id = {r.robot_id: r for r in self.engine.robots}
        orders_by_id = {o.order_id: o for o in self.engine.orders}

        if ctype == "no_action":
            return True, "No action nominal"

        if ctype == "yield_robot":
            r_id = str(cmd.get("robot_id", ""))
            robot = robots_by_id.get(r_id)
            if not robot:
                return False, f"Robot '{r_id}' not found"
            if robot.state in (RobotState.UNAVAILABLE, RobotState.CHARGING) or robot.fault is not None:
                return False, f"Robot '{r_id}' cannot yield in state {robot.state.value}"

            hold_ticks = int(cmd.get("hold_ticks") or 15)
            prio_id = cmd.get("priority_robot_id")
            raw_cell = cmd.get("yield_cell")
            grid = getattr(self.engine.planner, "_grid", None) or {
                c.pos.as_tuple(): c for c in self.engine.layout.cells
            }
            occupied = {r.cell.as_tuple() for r in self.engine.robots}
            hard_blocked = self.engine.safety_guard.blocked_cells | getattr(
                self.engine, "held_zone_cells", set()
            )

            target_cell: Coordinate | None = None
            if isinstance(raw_cell, dict) and "x" in raw_cell and "y" in raw_cell:
                cand = Coordinate(x=int(raw_cell["x"]), y=int(raw_cell["y"]))
                g_cell = grid.get((cand.x, cand.y))
                if (
                    g_cell is not None
                    and g_cell.is_walkable
                    and (cand.x, cand.y) not in hard_blocked
                    and ((cand.x, cand.y) not in occupied or cand == robot.cell)
                ):
                    target_cell = cand
            elif isinstance(raw_cell, Coordinate):
                g_cell = grid.get((raw_cell.x, raw_cell.y))
                if g_cell is not None and g_cell.is_walkable and (raw_cell.x, raw_cell.y) not in hard_blocked:
                    target_cell = raw_cell

            if target_cell is None:
                prio_cell = robots_by_id[prio_id].cell if prio_id in robots_by_id else None
                target_cell = _find_safe_yield_cell(robot, grid, occupied, hard_blocked, prio_cell)

            if target_cell is None:
                return False, f"No safe adjacent yield cell found for {r_id}"

            self.engine.ai_yield_directives[r_id] = (
                target_cell,
                tick + hold_ticks,
                prio_id if isinstance(prio_id, str) else None,
            )
            if isinstance(prio_id, str) and prio_id in robots_by_id:
                self.engine.ai_priority_boost[prio_id] = tick + max(hold_ticks, DEFAULT_CHARGE_PRIORITY_HOLD)

            self.engine.emit_event(
                "brain.command_executed",
                {
                    "command_type": "yield_robot",
                    "robot_id": r_id,
                    "yield_cell": target_cell.model_dump(),
                    "priority_robot_id": prio_id,
                },
            )
            return True, f"Yielded {r_id} to ({target_cell.x},{target_cell.y})"

        if ctype == "reroute_robot":
            r_id = str(cmd.get("robot_id", ""))
            robot = robots_by_id.get(r_id)
            if not robot:
                return False, f"Robot '{r_id}' not found"
            raw_avoid = cmd.get("avoid_cells") or []
            avoid_set: set[tuple[int, int]] = set()
            for entry in raw_avoid[:MAX_AVOID_CELLS_PER_CMD]:
                if isinstance(entry, dict) and "x" in entry and "y" in entry:
                    tup = (int(entry["x"]), int(entry["y"]))
                elif isinstance(entry, Coordinate):
                    tup = entry.as_tuple()
                else:
                    continue
                if tup != robot.cell.as_tuple():
                    avoid_set.add(tup)
            self.engine.ai_avoid_cells[r_id] = (avoid_set, tick + DEFAULT_AVOID_TTL_TICKS)
            self.engine.ai_priority_boost[r_id] = tick + DEFAULT_CHARGE_PRIORITY_HOLD
            self.engine.emit_event(
                "brain.command_executed",
                {"command_type": "reroute_robot", "robot_id": r_id, "avoid_count": len(avoid_set)},
            )
            return True, f"Applied temporary detour around {len(avoid_set)} cell(s) for {r_id}"

        if ctype == "send_to_charge":
            r_id = str(cmd.get("robot_id", ""))
            charger_id = cmd.get("charger_id")
            ok, msg = self._assign_charge_route(
                r_id, charger_id=str(charger_id) if charger_id else None
            )
            if ok:
                self.engine.emit_event(
                    "brain.command_executed",
                    {"command_type": "send_to_charge", "robot_id": r_id, "detail": msg},
                )
            return ok, msg

        if ctype == "assign_task":
            r_id = str(cmd.get("robot_id", ""))
            robot = robots_by_id.get(r_id)
            if not robot:
                return False, f"Robot '{r_id}' not found"
            task_type = str(cmd.get("task_type") or "PICK").upper()

            if task_type == "CHARGE":
                return self._assign_charge_route(r_id)

            if task_type == "MOVE":
                dest = cmd.get("destination")
                if isinstance(dest, dict) and "x" in dest and "y" in dest:
                    dest_coord = Coordinate(x=int(dest["x"]), y=int(dest["y"]))
                elif isinstance(dest, Coordinate):
                    dest_coord = dest
                else:
                    return False, "assign_task MOVE requires valid destination coordinate"

                grid = getattr(self.engine.planner, "_grid", None) or {
                    c.pos.as_tuple(): c for c in self.engine.layout.cells
                }
                cell_obj = grid.get(dest_coord.as_tuple())
                if not cell_obj or not cell_obj.is_walkable:
                    return False, f"Destination ({dest_coord.x},{dest_coord.y}) is non-walkable"
                self.engine.ai_move_overrides[r_id] = (dest_coord, tick + DEFAULT_MOVE_TTL_TICKS)
                self.engine.emit_event(
                    "brain.command_executed",
                    {
                        "command_type": "assign_task",
                        "robot_id": r_id,
                        "task_type": "MOVE",
                        "destination": dest_coord.model_dump(),
                    },
                )
                return True, f"Assigned MOVE to ({dest_coord.x},{dest_coord.y}) for {r_id}"

            if robot.state != RobotState.IDLE or robot.current_task_id is not None:
                return False, f"Robot '{r_id}' is busy ({robot.state.value}) and cannot accept a PICK task"

            order_id = cmd.get("order_id")
            target_order = orders_by_id.get(str(order_id)) if order_id else None
            if target_order is None:
                # Pick highest-priority pending order if order_id not supplied
                pending_orders = [
                    o
                    for o in self.engine.orders
                    if o.status in (OrderStatus.RECEIVED, OrderStatus.QUEUED, OrderStatus.PLANNED)
                    and self.engine.task_mgr.get_pending_line_for_order(o) is not None
                ]
                pending_orders.sort(key=lambda o: (-o.priority, o.deadline_tick))
                target_order = pending_orders[0] if pending_orders else None

            if target_order is None:
                return False, "No pending order available for PICK assignment"

            pending_line = self.engine.task_mgr.get_pending_line_for_order(target_order)
            if pending_line is None:
                return False, f"Order '{target_order.order_id}' has no pending pick lines"

            matching_bin = next(
                (
                    b
                    for b in self.engine.bins
                    if b.sku_id == pending_line.sku_id
                    and b.quantity > 0
                    and self.engine.task_mgr.get_bin_access_cell(b.bin_id) is not None
                ),
                None,
            )
            if matching_bin is None:
                return False, f"No stocked accessible bin for SKU '{pending_line.sku_id}'"

            stations = list(self.engine.station_mgr.station_defs.keys())
            st_id = target_order.assigned_station_id
            if not st_id or st_id not in self.engine.station_mgr.station_defs:
                st_id = (
                    min(
                        stations,
                        key=lambda sid: len(self.engine.station_mgr.robot_queues.get(sid, [])),
                    )
                    if stations
                    else "STATION-1"
                )
            target_order.assigned_station_id = st_id
            if target_order.status in (OrderStatus.RECEIVED, OrderStatus.QUEUED):
                target_order.status = OrderStatus.PLANNED
                self.engine.task_mgr.record_stage_time(target_order.order_id, "PLANNED", tick)

            task = self.engine.task_mgr.create_fetch_task(
                order=target_order,
                line=pending_line,
                bin_id=matching_bin.bin_id,
                station_id=st_id,
                current_tick=tick,
            )
            if task is None:
                return False, f"Could not create fetch task for order '{target_order.order_id}'"
            self.engine.task_mgr.assign_task_to_robot(
                task=task, robot=robot, current_tick=tick, order=target_order
            )
            self.engine.emit_event(
                "brain.command_executed",
                {
                    "command_type": "assign_task",
                    "robot_id": r_id,
                    "order_id": target_order.order_id,
                    "task_id": task.task_id,
                },
            )
            return True, f"Assigned {target_order.order_id} (bin {matching_bin.bin_id}) to {r_id}"

        if ctype == "reprioritise_order":
            o_id = str(cmd.get("order_id", ""))
            new_p = max(1, min(10, int(cmd.get("new_priority") or 10)))
            order = orders_by_id.get(o_id)
            if order is None:
                return False, f"Order '{o_id}' not found"
            order.priority = new_p
            if new_p >= HIGH_PRIORITY_THRESHOLD:
                order.sla_tier = "express"
            self.engine.emit_event(
                "brain.command_executed",
                {"command_type": "reprioritise_order", "order_id": o_id, "new_priority": new_p},
            )
            return True, f"Reprioritised {o_id} to priority {new_p}"

        if ctype == "batch_orders":
            order_ids = list(cmd.get("order_ids") or [])
            target_st = str(cmd.get("target_station_id") or "")
            if target_st not in self.engine.station_mgr.station_defs:
                return False, f"Target station '{target_st}' not found"
            updated = 0
            for oid in order_ids:
                order = orders_by_id.get(str(oid))
                if order and order.status not in (
                    OrderStatus.HANDED_OVER,
                    OrderStatus.CANCELLED,
                    OrderStatus.FAILED,
                ):
                    order.assigned_station_id = target_st
                    updated += 1
            if updated == 0:
                return False, f"No active orders updated for batch_orders to {target_st}"
            self.engine.emit_event(
                "brain.command_executed",
                {
                    "command_type": "batch_orders",
                    "target_station_id": target_st,
                    "orders_updated": updated,
                },
            )
            return True, f"Batched {updated} order(s) to station {target_st}"

        if ctype == "hold_zone":
            zone_id = str(cmd.get("zone_id") or "")
            dur = int(cmd.get("duration_ticks") or 300)
            ok = self.engine.hold_zone(zone_id, duration_ticks=dur)
            return (ok, f"Held zone {zone_id} for {dur} ticks") if ok else (False, f"Unknown zone '{zone_id}'")

        if ctype == "release_zone":
            rel_zone_id = cmd.get("zone_id")
            released = self.engine.release_zone(str(rel_zone_id) if rel_zone_id else None)
            if released:
                return True, f"Released zone(s): {', '.join(released)}"
            return False, f"Zone '{rel_zone_id}' is not currently held"

        if ctype == "set_station_policy":
            st_id = str(cmd.get("station_id") or "")
            if st_id not in self.engine.station_mgr.station_defs:
                return False, f"Station '{st_id}' not found"
            depth = max(1, min(MAX_STATION_QUEUE_LIMIT, int(cmd.get("max_queue_depth") or 6)))
            self.engine.station_mgr.max_queue_capacity = depth
            policies = getattr(self.engine.station_mgr, "station_policies", None)
            if not isinstance(policies, dict):
                policies = {}
                self.engine.station_mgr.station_policies = policies
            policies[st_id] = {
                "max_queue_depth": depth,
                "batch_window_sec": float(cmd.get("batch_window_sec") or 30.0),
            }
            self.engine.emit_event(
                "brain.command_executed",
                {"command_type": "set_station_policy", "station_id": st_id, "max_queue_depth": depth},
            )
            return True, f"Updated queue depth of {st_id} to {depth}"

        if ctype == "set_strategy_params":
            params = dict(cmd.get("params") or {})
            dispatcher = self.engine.dispatcher
            applied: dict[str, Any] = {}
            for key, val in params.items():
                if key.startswith("_"):
                    continue
                if hasattr(dispatcher, key) and isinstance(val, (int, float, bool, str)):
                    setattr(dispatcher, key, val)
                    applied[key] = val
            store = getattr(dispatcher, "ai_strategy_params", None)
            if not isinstance(store, dict):
                store = {}
                dispatcher.ai_strategy_params = store
            store.update(params)
            self.engine.emit_event(
                "brain.strategy_updated",
                {"strategy_name": cmd.get("strategy_name", ""), "applied": applied or params},
            )
            return True, f"Updated strategy parameters ({len(params)} keys)"

        if ctype == "reassign_task":
            r_id = str(cmd.get("robot_id") or "")
            if r_id not in robots_by_id:
                return False, f"Robot '{r_id}' not found"
            reassigned = self.engine.chaos_engine.recovery_mgr.reassign_robot_tasks(r_id, tick)
            self.engine.ai_yield_directives.pop(r_id, None)
            self.engine.emit_event(
                "brain.command_executed",
                {"command_type": "reassign_task", "robot_id": r_id, "reassigned_count": reassigned},
            )
            return True, f"Reassigned {reassigned} task(s) from {r_id}"

        if ctype == "substitute_item":
            o_id = str(cmd.get("order_id") or "")
            sku_id = str(cmd.get("sku_id") or "")
            ok = self.engine.chaos_engine.recovery_mgr.substitute_missing_or_damaged_item(
                o_id, sku_id, tick
            )
            return (
                (True, f"Substituted SKU {sku_id} for order {o_id}")
                if ok
                else (False, f"No substitute bin found for SKU {sku_id} on {o_id}")
            )

        if ctype == "reroute_station":
            st_id = str(cmd.get("station_id") or "")
            if st_id not in self.engine.station_mgr.station_defs:
                return False, f"Station '{st_id}' not found"
            rebalanced = self.engine.chaos_engine.recovery_mgr.rebalance_station_queues(st_id, tick)
            return True, f"Rerouted {rebalanced} robot(s) away from congested station {st_id}"

        if ctype == "clear_fault":
            target_id = str(cmd.get("target_id") or "")
            resolved = False
            for f in list(self.engine.chaos_engine.active_faults):
                if (
                    f.target_id == target_id or f.fault_id == target_id
                ) and self.engine.chaos_engine.resolve_fault(f.fault_id, tick):
                    resolved = True

            robot = robots_by_id.get(target_id)
            if robot and (robot.fault is not None or robot.state == RobotState.UNAVAILABLE):
                robot.fault = None
                if robot.state == RobotState.UNAVAILABLE:
                    robot.state = RobotState.IDLE
                resolved = True

            if resolved:
                self.engine.emit_event(
                    "brain.command_executed",
                    {"command_type": "clear_fault", "target_id": target_id},
                )
                return True, f"Cleared fault for {target_id}"
            return False, f"No active fault matched '{target_id}'"

        return False, f"Unsupported command_type '{ctype}'"

    def get_operational_metrics(self) -> dict[str, Any]:
        """Aggregates verified provider attribution, fallback rate, latency, cost, and outcomes."""
        total = len(self.decisions)
        fallback_count = sum(1 for d in self.decisions if d.fallback_used)
        ai_count = sum(1 for d in self.decisions if d.provider_mode == "ai" and not d.fallback_used)
        local_count = sum(
            1 for d in self.decisions if d.provider_mode == "local_llm" and not d.fallback_used
        )
        heuristic_count = sum(1 for d in self.decisions if d.provider_mode == "heuristic")
        improved = sum(1 for d in self.decisions if d.observed_outcome == "improved")
        neutral = sum(1 for d in self.decisions if d.observed_outcome == "neutral")
        worsened = sum(1 for d in self.decisions if d.observed_outcome == "worsened")
        avg_latency = (
            sum(d.latency_ms for d in self.decisions) / total if total > 0 else 0.0
        )
        total_cost = sum(d.cost_usd for d in self.decisions)
        return {
            "total_decisions": total,
            "ai_decisions": ai_count,
            "local_llm_decisions": local_count,
            "heuristic_decisions": heuristic_count,
            "fallback_count": fallback_count,
            "fallback_rate": (fallback_count / total) if total > 0 else 0.0,
            "stale_decisions_discarded": self.stale_decisions_discarded,
            "invalid_command_rejections": self.invalid_command_rejections,
            "deadlocks_resolved": self.deadlocks_resolved,
            "outcomes": {
                "improved": improved,
                "neutral": neutral,
                "worsened": worsened,
                "unknown": max(0, total - improved - neutral - worsened),
            },
            "avg_latency_ms": round(avg_latency, 2),
            "total_cost_usd": round(total_cost, 6),
        }

    def get_status_summary(self) -> dict[str, Any]:
        """Builds structured non-secret Brain status payload for API and WebSocket telemetry."""
        provider = self.get_active_provider()
        last_dec = self.decisions[-1] if self.decisions else None
        approvals_pending = len(self.governance.approvals_queue.pending)
        cloud_cfg = self.brain_config.cloud
        local_cfg = self.brain_config.local
        inference_running = (
            self._pending_inference is not None and not self._pending_inference.task.done()
        )
        current_tick = getattr(getattr(self.engine, "clock", None), "tick", 0)
        deadlocks = self._get_deadlocks(current_tick)

        connection_state = "Baseline Mode"
        model_name = ""
        provider_label = "Heuristic"

        if not self.enabled:
            connection_state = "Baseline Mode — Deterministic Dispatcher"
            provider_label = "Baseline"
        elif self.mode == "heuristic":
            connection_state = "Heuristic Mode — Active"
            provider_label = "Heuristic"
            model_name = "deterministic"
        elif self.mode == "replay":
            connection_state = "Replay Mode — Active"
            provider_label = "Replay"
            model_name = "ndjson-replay"
        elif self.mode == "ai":
            adapter = self.ai_provider.get_active_adapter()
            provider_label = cloud_cfg.provider_label or cloud_cfg.provider_type
            model_name = cloud_cfg.model
            has_key = self.ai_provider.has_configured_key()
            if inference_running:
                connection_state = f"AI Mode ({provider_label}) — Generating decision"
            elif not has_key:
                connection_state = "AI Mode — API key missing"
            elif getattr(adapter, "circuit_tripped", False):
                connection_state = f"AI Mode ({provider_label}) — Circuit cooldown / Fallback"
            elif getattr(adapter, "last_error", ""):
                connection_state = f"AI Mode ({provider_label}) — Error / Fallback active"
            else:
                connection_state = f"AI Mode ({provider_label}) — Connected"
        elif self.mode == "local_llm":
            provider_label = "Ollama (Local LLM)"
            model_name = local_cfg.model
            health = self.local_provider.last_health_status
            if inference_running:
                connection_state = f"Local LLM ({model_name}) — Generating decision"
            elif getattr(self.local_provider, "circuit_tripped", False):
                connection_state = "Local LLM — Unavailable / Fallback active"
            elif health is not None and not health.ok:
                connection_state = f"Local LLM — Unavailable ({health.message[:48]})"
            else:
                connection_state = f"Local LLM ({model_name}) — Ready"

        return {
            "enabled": self.enabled,
            "mode": self.mode if self.enabled else "baseline",
            "operating_mode": self.mode,
            "provider": self.provider_name if self.enabled else "baseline",
            "provider_label": provider_label,
            "model_name": model_name,
            "connection_state": connection_state,
            "inference_in_flight": inference_running,
            "inference_started_tick": (
                self._pending_inference.snapshot_tick if inference_running and self._pending_inference else None
            ),
            "last_decision_tick": self.last_decision_tick,
            "last_latency_ms": last_dec.latency_ms if last_dec else 0.0,
            "last_fallback_used": last_dec.fallback_used if last_dec else False,
            "last_fallback_reason": last_dec.fallback_reason if last_dec else "",
            "last_attribution": last_dec.attribution if last_dec else "",
            "decisions_count": len(self.decisions),
            "approvals_pending": approvals_pending,
            "held_zones": sorted(self.held_zones),
            "deadlocks_active_count": len(deadlocks),
            "circuit_tripped": bool(getattr(provider, "circuit_tripped", False)),
            "total_cost_usd": float(getattr(provider, "total_cost_usd", 0.0)),
            "metrics": self.get_operational_metrics(),
            "ai_cloud": {
                "provider_type": cloud_cfg.provider_type,
                "provider_label": cloud_cfg.provider_label,
                "api_compatibility": cloud_cfg.api_compatibility,
                "base_url": cloud_cfg.base_url,
                "model": cloud_cfg.model,
                "timeout_s": cloud_cfg.timeout_s,
                "max_tokens": cloud_cfg.max_tokens,
                "temperature": cloud_cfg.temperature,
                "fallback_policy": cloud_cfg.fallback_policy,
                "has_api_key": self.ai_provider.has_configured_key(),
                "masked_api_key": self.ai_provider.get_masked_key(),
                "key_source": self.ai_provider.key_source(),
            },
            "local_llm": {
                "provider": local_cfg.provider,
                "base_url": local_cfg.base_url,
                "model": local_cfg.model,
                "recommended_model": "qwen3.5:4b",
                "timeout_s": local_cfg.timeout_s,
                "context_length": local_cfg.context_length,
                "temperature": local_cfg.temperature,
                "max_tokens": local_cfg.max_tokens,
                "max_concurrency": local_cfg.max_concurrency,
                "fallback_policy": local_cfg.fallback_policy,
                "health": (
                    asdict(self.local_provider.last_health_status)
                    if self.local_provider.last_health_status
                    else None
                ),
            },
        }

    def _append_decision_to_log(self, decision: Decision) -> None:
        with open(self.decisions_log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(decision.model_dump()) + "\n")
