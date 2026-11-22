"""Exceptions Queue and Human Intervention Workflow (Phase 6, P6-A5).
Manages human-in-the-loop exception items: damaged goods, physical tote recovery,
unresolvable shortages, robot breakdown towing, and manual policy overrides.
Applies safe default actions on SLA timeouts and tracks interventions per 100 orders KPI.
"""

from __future__ import annotations

import logging
from typing import Any, Literal

from robofleet.audit.database import AuditDatabase
from robofleet.contracts.chaos import ExceptionItem

logger = logging.getLogger(__name__)


class ExceptionsQueue:
    """Manages queue of operational exceptions requiring human supervisor resolution."""

    def __init__(self, audit_db: AuditDatabase | None = None) -> None:
        self.audit_db = audit_db or AuditDatabase()
        self.pending_exceptions: dict[str, ExceptionItem] = {}
        self.history_exceptions: list[ExceptionItem] = []
        self.total_human_interventions: int = 0
        self.total_timed_out_exceptions: int = 0

    def add_exception(self, item: ExceptionItem) -> None:
        self.pending_exceptions[item.exception_id] = item
        logger.info("[ExceptionsQueue] Added exception %s (%s) for %s", item.exception_id, item.exception_type, item.entity_id)

    def resolve_exception(
        self,
        exception_id: str,
        action: str,
        actor: str,
        role: Literal["viewer", "supervisor", "admin"],
        reason: str,
        current_tick: int,
    ) -> tuple[bool, str]:
        """Resolves an exception with human supervisor action, verifying permissions and auditing result."""
        item = self.pending_exceptions.get(exception_id)
        if not item:
            return False, f"Exception '{exception_id}' not found in active queue."

        # Permission check
        if not self.audit_db.check_permission(role, "resolve_exception"):
            self.audit_db.record_entry(
                tick=current_tick,
                actor=actor,
                role=role,
                action="resolve_exception",
                entity_type="exception",
                entity_id=exception_id,
                before_state=item.model_dump(),
                after_state=item.model_dump(),
                reason=reason,
                result="REJECTED",
                rejection_reason=f"Role '{role}' lacks permission 'resolve_exception'.",
            )
            return False, f"Permission denied for role '{role}'."

        # Validate action is among available choices
        if item.available_actions and action not in item.available_actions:
            self.audit_db.record_entry(
                tick=current_tick,
                actor=actor,
                role=role,
                action="resolve_exception",
                entity_type="exception",
                entity_id=exception_id,
                before_state=item.model_dump(),
                after_state=item.model_dump(),
                reason=reason,
                result="REJECTED",
                rejection_reason=f"Action '{action}' is not valid for exception type '{item.exception_type}'.",
            )
            return False, f"Invalid action '{action}'. Valid: {item.available_actions}"

        # Resolve successfully
        before_state = item.model_dump()
        item.status = "RESOLVED"
        item.resolved_by = actor
        item.resolved_action = action
        item.resolved_tick = current_tick

        self.pending_exceptions.pop(exception_id)
        self.history_exceptions.append(item)
        self.total_human_interventions += 1

        self.audit_db.record_entry(
            tick=current_tick,
            actor=actor,
            role=role,
            action="resolve_exception",
            entity_type="exception",
            entity_id=exception_id,
            before_state=before_state,
            after_state=item.model_dump(),
            reason=reason,
            result="SUCCESS",
        )
        return True, f"Exception '{exception_id}' resolved with action '{action}'."

    def step(self, current_tick: int) -> list[ExceptionItem]:
        """Advances timeout clock for pending exceptions. Applies default action on SLA breach."""
        timed_out_items: list[ExceptionItem] = []

        for exc_id, item in list(self.pending_exceptions.items()):
            if current_tick >= item.deadline_tick:
                item.status = "TIMED_OUT"
                item.resolved_by = "SYSTEM_TIMEOUT"
                item.resolved_action = item.default_action
                item.resolved_tick = current_tick

                self.pending_exceptions.pop(exc_id)
                self.history_exceptions.append(item)
                self.total_timed_out_exceptions += 1
                timed_out_items.append(item)

                self.audit_db.record_entry(
                    tick=current_tick,
                    actor="SYSTEM_TIMEOUT",
                    role="admin",
                    action="auto_resolve_timeout",
                    entity_type="exception",
                    entity_id=exc_id,
                    before_state={"status": "PENDING"},
                    after_state=item.model_dump(),
                    reason=f"SLA deadline breached ({item.deadline_tick} ticks). Applied default action: {item.default_action}",
                    result="SUCCESS",
                )
                logger.warning("[ExceptionsQueue] Exception %s timed out; applied default action %s", exc_id, item.default_action)

        return timed_out_items

    def compute_human_interventions_per_100_orders(self, total_orders: int) -> float:
        """Computes the human interventions per 100 orders KPI."""
        if total_orders <= 0:
            return 0.0
        return round((self.total_human_interventions / total_orders) * 100.0, 2)

    def get_queue_average_age_ticks(self, current_tick: int) -> float:
        """Returns average age of active pending exceptions in ticks."""
        if not self.pending_exceptions:
            return 0.0
        ages = [max(0, current_tick - e.raised_tick) for e in self.pending_exceptions.values()]
        return round(sum(ages) / len(ages), 1)
