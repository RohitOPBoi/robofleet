"""SQLite Append-Only Audit Log Database (Phase 6).
Maintains an immutable, append-only ledger of every human supervisor and AI brain state-changing action.
Enforces permissions based on roles (viewer, supervisor, admin) and records all rejected attempts.
Provides CSV export and query filtering.
"""

from __future__ import annotations

import csv
import io
import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal
import uuid

from robofleet.contracts.chaos import AuditEntry

logger = logging.getLogger(__name__)

ROLE_PERMISSIONS: dict[str, set[str]] = {
    "viewer": {"read"},
    "supervisor": {
        "read",
        "resolve_exception",
        "reassign_task",
        "substitute_item",
        "hold_zone",
        "release_zone",
        "approve_reslot",
        "clear_fault",
    },
    "admin": {
        "read",
        "resolve_exception",
        "reassign_task",
        "substitute_item",
        "hold_zone",
        "release_zone",
        "approve_reslot",
        "clear_fault",
        "emergency_stop",
        "scale_fleet",
        "inject_fault",
        "override_policy",
    },
}


class AuditDatabase:
    """Immutable SQLite audit log manager."""

    def __init__(self, db_path: str | Path = "runs/audit.db") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            # Enable WAL mode for high concurrency
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    audit_id TEXT UNIQUE NOT NULL,
                    timestamp_iso TEXT NOT NULL,
                    tick INTEGER NOT NULL,
                    actor TEXT NOT NULL,
                    role TEXT NOT NULL,
                    action TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    before_state TEXT NOT NULL,
                    after_state TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    result TEXT NOT NULL,
                    rejection_reason TEXT
                );
            """)

            # Append-only enforcement via SQLite triggers (prevent UPDATE and DELETE)
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS audit_log_no_update
                BEFORE UPDATE ON audit_log
                BEGIN
                    SELECT RAISE(FAIL, 'Audit log is strictly append-only: updates are prohibited.');
                END;
            """)
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS audit_log_no_delete
                BEFORE DELETE ON audit_log
                BEGIN
                    SELECT RAISE(FAIL, 'Audit log is strictly append-only: deletions are prohibited.');
                END;
            """)
            conn.commit()

    def check_permission(self, role: str, action: str) -> bool:
        allowed_actions = ROLE_PERMISSIONS.get(role.lower(), set())
        return action in allowed_actions

    def record_entry(
        self,
        tick: int,
        actor: str,
        role: Literal["viewer", "supervisor", "admin"],
        action: str,
        entity_type: str,
        entity_id: str,
        before_state: dict[str, Any] | None = None,
        after_state: dict[str, Any] | None = None,
        reason: str = "",
        result: Literal["SUCCESS", "REJECTED", "FAILED"] = "SUCCESS",
        rejection_reason: str | None = None,
    ) -> AuditEntry:
        """Appends an immutable audit entry to SQLite."""
        audit_id = f"AUD-{uuid.uuid4().hex[:10]}"
        now_iso = datetime.now(timezone.utc).isoformat()

        before_json = json.dumps(before_state or {})
        after_json = json.dumps(after_state or {})

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO audit_log (
                    audit_id, timestamp_iso, tick, actor, role, action,
                    entity_type, entity_id, before_state, after_state,
                    reason, result, rejection_reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    audit_id,
                    now_iso,
                    tick,
                    actor,
                    role,
                    action,
                    entity_type,
                    entity_id,
                    before_json,
                    after_json,
                    reason,
                    result,
                    rejection_reason,
                ),
            )
            conn.commit()

        return AuditEntry(
            audit_id=audit_id,
            timestamp_iso=now_iso,
            tick=tick,
            actor=actor,
            role=role,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            before_state=before_state or {},
            after_state=after_state or {},
            reason=reason,
            result=result,
            rejection_reason=rejection_reason,
        )

    def query_logs(
        self,
        role: str | None = None,
        actor: str | None = None,
        action: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Queries audit entries with optional filters."""
        query = "SELECT * FROM audit_log WHERE 1=1"
        params: list[Any] = []

        if role:
            query += " AND role = ?"
            params.append(role)
        if actor:
            query += " AND actor = ?"
            params.append(actor)
        if action:
            query += " AND action = ?"
            params.append(action)

        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)

        with self._get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            results = []
            for r in rows:
                results.append({
                    "id": r["id"],
                    "audit_id": r["audit_id"],
                    "timestamp_iso": r["timestamp_iso"],
                    "tick": r["tick"],
                    "actor": r["actor"],
                    "role": r["role"],
                    "action": r["action"],
                    "entity_type": r["entity_type"],
                    "entity_id": r["entity_id"],
                    "before_state": json.loads(r["before_state"]),
                    "after_state": json.loads(r["after_state"]),
                    "reason": r["reason"],
                    "result": r["result"],
                    "rejection_reason": r["rejection_reason"],
                })
            return results

    def export_csv(self) -> str:
        """Exports the full audit ledger to CSV format."""
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM audit_log ORDER BY id ASC").fetchall()

            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow([
                "id",
                "audit_id",
                "timestamp_iso",
                "tick",
                "actor",
                "role",
                "action",
                "entity_type",
                "entity_id",
                "before_state",
                "after_state",
                "reason",
                "result",
                "rejection_reason",
            ])
            for r in rows:
                writer.writerow([
                    r["id"],
                    r["audit_id"],
                    r["timestamp_iso"],
                    r["tick"],
                    r["actor"],
                    r["role"],
                    r["action"],
                    r["entity_type"],
                    r["entity_id"],
                    r["before_state"],
                    r["after_state"],
                    r["reason"],
                    r["result"],
                    r["rejection_reason"] or "",
                ])
            return output.getvalue()
