"""LLM Provider Port Interface & Shared Resilience Helpers.

Defines the provider protocol, unified result contract, specialist collection/conflict
arbitration helper, and shared circuit-breaker + explicit fallback behavior.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, Field

from robofleet.contracts.brain import (
    DecisionProposal,
    NoActionCommand,
    SituationBrief,
)


class LLMProviderResult(BaseModel):
    """Unified provider response with explicit attribution and telemetry."""

    proposals: list[DecisionProposal] = Field(default_factory=list)
    commands: list[dict[str, Any]] = Field(default_factory=list)
    rejected_commands: list[dict[str, Any]] = Field(default_factory=list)
    rationale: str = ""
    situation_summary: str = ""
    traffic_plan: dict[str, Any] = Field(default_factory=dict)
    unresolved_risks: list[str] = Field(default_factory=list)
    confidence: float = 1.0
    requires_human_approval: bool = False
    token_usage: dict[str, int] = Field(default_factory=dict)
    cost_usd: float = 0.0
    latency_ms: float = 0.0
    operating_mode: Literal["heuristic", "ai", "local_llm", "replay"] = "heuristic"
    provider_name: str = "heuristic"
    model_name: str = ""
    fallback_used: bool = False
    fallback_reason: str = ""
    provider_status: Literal[
        "connected", "generating", "unavailable", "fallback", "offline"
    ] = "connected"
    attribution: str = ""


@dataclass
class ProviderHealthStatus:
    """Diagnostic status returned by provider health & credential checks."""

    ok: bool
    operating_mode: str
    provider_name: str
    model_name: str
    status: Literal["connected", "unavailable", "unconfigured", "error"]
    message: str
    available_models: list[str] = field(default_factory=list)
    latency_ms: float = 0.0


@runtime_checkable
class LLMProvider(Protocol):
    """Protocol for AI decision engines."""

    name: str

    async def decide(
        self,
        brief: SituationBrief,
        specialists: list[Any],
    ) -> LLMProviderResult:
        ...


def collect_and_arbitrate_specialists(
    brief: SituationBrief,
    specialists: list[Any] | None = None,
) -> list[DecisionProposal]:
    """Invoke active specialist modules and deterministically arbitrate conflicts.

    Priority rules when specialists conflict on the same robot_id:
    1. Battery protection (`send_to_charge`) & hardware fault (`reassign_task`, `escalate_to_human`)
    2. Deadlock / collision recovery (`yield_robot`, `reroute_robot`)
    3. Planning / task allocation (`assign_task`, `reprioritise_order`, `set_station_policy`)
    """
    raw_proposals: list[DecisionProposal] = list(brief.specialist_summary)

    if specialists:
        seen_signatures = {
            (p.specialist, p.action, json.dumps(p.command, sort_keys=True))
            for p in raw_proposals
        }
        for spec in specialists:
            propose_fn = getattr(spec, "propose", None)
            if callable(propose_fn):
                try:
                    spec_props = propose_fn(brief)
                except Exception:
                    spec_props = []
                for p in spec_props:
                    sig = (p.specialist, p.action, json.dumps(p.command, sort_keys=True))
                    if sig not in seen_signatures:
                        raw_proposals.append(p)
                        seen_signatures.add(sig)

    # Deterministic priority ranking per entity to prevent contradictory commands
    action_priority: dict[str, int] = {
        "send_to_charge": 1,
        "reassign_task": 1,
        "escalate_to_human": 1,
        "yield_robot": 2,
        "reroute_robot": 2,
        "hold_zone": 3,
        "release_zone": 3,
        "reprioritise_order": 4,
        "set_station_policy": 4,
        "batch_orders": 5,
        "assign_task": 6,
        "set_strategy_params": 7,
        "no_action": 9,
    }

    sorted_props = sorted(
        raw_proposals,
        key=lambda p: (
            action_priority.get(str(p.command.get("command_type", p.action)), 8),
            -p.confidence,
        ),
    )

    # Keep highest-priority non-conflicting command per robot_id (except escalate_to_human + reassign_task pair)
    robot_actions_taken: dict[str, str] = {}
    arbitrated: list[DecisionProposal] = []
    seen_commands: set[str] = set()

    for p in sorted_props:
        cmd = p.command or {}
        ctype = str(cmd.get("command_type", p.action))
        if not cmd:
            continue

        cmd_fp = json.dumps(
            {k: v for k, v in cmd.items() if k not in ("command_id", "issued_tick")},
            sort_keys=True,
        )
        if cmd_fp in seen_commands:
            continue

        rid = cmd.get("robot_id")
        if rid and ctype != "escalate_to_human":
            prev_act = robot_actions_taken.get(str(rid))
            if prev_act is not None:
                # Avoid assigning a low-battery or yielding robot another task in the same tick
                continue
            robot_actions_taken[str(rid)] = ctype

        seen_commands.add(cmd_fp)
        arbitrated.append(p)

    return arbitrated


class CircuitBreakerMixin:
    """Shared circuit-breaker & attribution helpers for network/local LLM providers."""

    def _init_circuit(
        self,
        circuit_threshold: int,
        circuit_cooldown_s: float,
    ) -> None:
        self.circuit_threshold = max(1, circuit_threshold)
        self.circuit_cooldown_s = max(1.0, circuit_cooldown_s)
        self.consecutive_failures: int = 0
        self.circuit_open_until: float = 0.0
        self.total_prompt_tokens: int = 0
        self.total_completion_tokens: int = 0
        self.total_cost_usd: float = 0.0
        self.latencies_ms: list[float] = []
        self.last_error: str = ""

    @property
    def is_circuit_open(self) -> bool:
        return time.time() < self.circuit_open_until

    @property
    def circuit_tripped(self) -> bool:
        return self.is_circuit_open

    def reset_circuit(self) -> None:
        self.consecutive_failures = 0
        self.circuit_open_until = 0.0
        self.last_error = ""

    def _record_failure(self, err: str) -> None:
        self.last_error = err
        self.consecutive_failures += 1
        if self.consecutive_failures >= self.circuit_threshold:
            self.circuit_open_until = time.time() + self.circuit_cooldown_s

    def _record_success(self, latency_ms: float, p_tokens: int, c_tokens: int, cost: float = 0.0) -> None:
        self.consecutive_failures = 0
        self.circuit_open_until = 0.0
        self.last_error = ""
        self.latencies_ms.append(latency_ms)
        self.total_prompt_tokens += p_tokens
        self.total_completion_tokens += c_tokens
        self.total_cost_usd += cost


async def build_explicit_fallback_result(
    heuristic_fallback: Any,
    brief: SituationBrief,
    specialists: list[Any] | None,
    operating_mode: Literal["heuristic", "ai", "local_llm", "replay"],
    fallback_policy: Literal["heuristic", "safe_wait"],
    reason: str,
    model_name: str = "",
    token_usage: dict[str, int] | None = None,
    cost_usd: float = 0.0,
) -> LLMProviderResult:
    """Produce a transparent fallback decision without ever misattributing it to an LLM."""
    if fallback_policy == "safe_wait":
        cmd = NoActionCommand(
            issued_tick=brief.tick,
            reason=f"Safe wait fallback ({reason})",
            expected_effect="Hold fleet trajectories safely until provider recovers",
        )
        return LLMProviderResult(
            proposals=[
                DecisionProposal(
                    specialist="exceptions",
                    action="no_action",
                    command=cmd.model_dump(),
                    confidence=1.0,
                    rationale=f"Provider unavailable ({reason}); enforcing safe wait.",
                )
            ],
            commands=[cmd.model_dump()],
            rationale=f"Safe wait fallback active: {reason}",
            situation_summary="Provider unavailable; robots remain under SafetyGuard safe-wait protection.",
            unresolved_risks=[reason],
            token_usage=token_usage or {},
            cost_usd=cost_usd,
            latency_ms=0.0,
            operating_mode=operating_mode,
            provider_name="Safe wait fallback",
            model_name=model_name,
            fallback_used=True,
            fallback_reason=reason,
            provider_status="unavailable",
            attribution="Safe wait fallback — deterministic safety hold",
        )

    res: LLMProviderResult = await heuristic_fallback.decide(brief, specialists)
    res.operating_mode = operating_mode
    res.provider_name = "Heuristic fallback"
    res.model_name = model_name
    res.fallback_used = True
    res.fallback_reason = reason
    res.provider_status = "fallback"
    res.attribution = "Heuristic fallback — deterministic provider"
    if token_usage:
        res.token_usage = token_usage
    if cost_usd > 0.0:
        res.cost_usd = cost_usd
    return res
