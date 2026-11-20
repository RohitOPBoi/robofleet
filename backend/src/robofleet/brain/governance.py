"""Governance Layer (Phase 5 - CA-3).
Enforces policy rules, rate limits, battery protection, zone hold caps,
and manages the Human Approvals Queue before any command reaches the engine.
"""

from __future__ import annotations

import logging
from typing import Any, Literal
from robofleet.contracts.brain import ApprovalRequest, BrainBaseCommand
from robofleet.rules.engine import RuleEngine

logger = logging.getLogger(__name__)


class GovernanceVerdict:
    def __init__(
        self,
        status: Literal["approved", "require_human", "denied"],
        reason: str = "",
        policy_id: str | None = None,
        approval_request: ApprovalRequest | None = None,
    ) -> None:
        self.status = status
        self.reason = reason
        self.policy_id = policy_id
        self.approval_request = approval_request

    @property
    def is_approved(self) -> bool:
        return self.status == "approved"


class ApprovalsQueue:
    """Manages commands awaiting human supervisor approval with automatic timeout handling."""

    def __init__(self) -> None:
        self.pending: dict[str, ApprovalRequest] = {}
        self.history: list[ApprovalRequest] = []

    def enqueue(
        self,
        decision_id: str,
        command: dict[str, Any],
        current_tick: int,
        timeout_ticks: int = 50,
        default_action: Literal["deny", "approve_safe_alternative"] = "deny",
        reason: str = "",
    ) -> ApprovalRequest:
        req = ApprovalRequest(
            decision_id=decision_id,
            command=command,
            timeout_tick=current_tick + timeout_ticks,
            default_action=default_action,
            created_tick=current_tick,
            status="pending",
            reason=reason,
        )
        self.pending[req.request_id] = req
        return req

    def approve(self, request_id: str) -> ApprovalRequest | None:
        req = self.pending.pop(request_id, None)
        if req:
            req.status = "approved"
            self.history.append(req)
            return req
        return None

    def reject(self, request_id: str) -> ApprovalRequest | None:
        req = self.pending.pop(request_id, None)
        if req:
            req.status = "rejected"
            self.history.append(req)
            return req
        return None

    def resolve(self, request_id: str, approve: bool) -> dict[str, Any] | None:
        if approve:
            req = self.approve(request_id)
            return req.command if req else None
        else:
            self.reject(request_id)
            return None

    def tick(self, current_tick: int) -> list[ApprovalRequest]:
        """Expire timed-out approval requests applying their default action."""
        expired: list[ApprovalRequest] = []
        for req_id, req in list(self.pending.items()):
            if current_tick >= req.timeout_tick:
                del self.pending[req_id]
                req.status = "timed_out"
                self.history.append(req)
                expired.append(req)
                logger.info(
                    "[Governance] Approval request %s timed out at tick %d (default: %s)",
                    req_id,
                    current_tick,
                    req.default_action,
                )
        return expired


class GovernanceLayer:
    """Evaluates commands against declarative policy rules before execution."""

    def __init__(self, rules_dir: str = "rules") -> None:
        self.rule_engine = RuleEngine(rules_dir=rules_dir)
        self.approvals_queue = ApprovalsQueue()

    def reload_policies(self) -> tuple[int, list[str]]:
        return self.rule_engine.load_rules()

    def evaluate_command(
        self,
        command: BrainBaseCommand | dict[str, Any],
        decision_id: str,
        current_tick: int,
        context_state: dict[str, Any] | None = None,
    ) -> GovernanceVerdict:
        cmd_dict = command.model_dump() if isinstance(command, BrainBaseCommand) else dict(command)
        cmd_type = cmd_dict.get("command_type", "")

        # 1. Base invariant: No-Action is always approved
        if cmd_type == "no_action":
            return GovernanceVerdict(status="approved", reason="No action nominal")

        # 2. Build governance context
        ctx: dict[str, Any] = {
            "command": cmd_dict,
            "tick": current_tick,
            "state": context_state or {},
        }

        # Context helpers for battery, zones, etc.
        if context_state:
            robots = context_state.get("robots", {})
            robot_id = cmd_dict.get("robot_id")
            if robot_id and robot_id in robots:
                r_dict = dict(robots[robot_id])
                if "battery_pct" in r_dict and "battery_percent" not in r_dict:
                    r_dict["battery_percent"] = r_dict["battery_pct"]
                ctx["robot"] = r_dict

            ctx["held_zones_count"] = len(context_state.get("held_zones", []))
            ctx["total_zones_count"] = len(context_state.get("zones", []))

        # 3. Evaluate matching 'command' scope rules
        matched_rules = self.rule_engine.evaluate(scope="command", context=ctx)

        for rule in matched_rules:
            if rule.effect == "deny":
                return GovernanceVerdict(
                    status="denied",
                    reason=f"Policy violation: {rule.description}",
                    policy_id=rule.id,
                )
            if rule.effect == "require_human":
                req = self.approvals_queue.enqueue(
                    decision_id=decision_id,
                    command=cmd_dict,
                    current_tick=current_tick,
                    timeout_ticks=rule.params.get("timeout_ticks", 50),
                    default_action=rule.params.get("default_action", "deny"),
                    reason=rule.description,
                )
                return GovernanceVerdict(
                    status="require_human",
                    reason=f"Requires human sign-off: {rule.description}",
                    policy_id=rule.id,
                    approval_request=req,
                )

        # 4. Explicit EscalateToHuman command
        if cmd_type == "escalate_to_human":
            req = self.approvals_queue.enqueue(
                decision_id=decision_id,
                command=cmd_dict.get("action_command", {}),
                current_tick=current_tick,
                timeout_ticks=cmd_dict.get("timeout_ticks", 50),
                default_action=cmd_dict.get("default_action", "deny"),
                reason=cmd_dict.get("reason", "Escalated to human"),
            )
            return GovernanceVerdict(
                status="require_human",
                reason=cmd_dict.get("reason", "Escalated to human"),
                approval_request=req,
            )

        # 5. Default: Approved
        return GovernanceVerdict(status="approved", reason="Policy verified")
