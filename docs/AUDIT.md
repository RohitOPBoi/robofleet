# RoboFleet Immutable Audit Ledger Specification

## 1. Architectural Overview

The RoboFleet Audit Ledger provides a cryptographically protected, append-only record of all operational interventions, policy overrides, chaos injections, and governance decisions. It ensures full non-repudiation, regulatory compliance, and post-incident root-cause analysis.

---

## 2. Storage & Trigger Enforcement

The ledger is hosted in an embedded SQLite database (`runs/audit.db`) with active schema triggers prohibiting mutation or record removal:

```sql
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
    before_state TEXT,
    after_state TEXT,
    reason TEXT,
    result TEXT NOT NULL,
    rejection_reason TEXT
);

-- Immutable Append-Only Triggers
CREATE TRIGGER IF NOT EXISTS audit_log_no_update
BEFORE UPDATE ON audit_log
BEGIN
    SELECT RAISE(FAIL, 'Audit log is strictly append-only: updates are prohibited.');
END;

CREATE TRIGGER IF NOT EXISTS audit_log_no_delete
BEFORE DELETE ON audit_log
BEGIN
    SELECT RAISE(FAIL, 'Audit log is strictly append-only: deletions are prohibited.');
END;
```

Any attempt by an application thread, external actor, or supervisor to execute `UPDATE audit_log ...` or `DELETE FROM audit_log ...` is aborted by the SQLite database engine with an `OperationalError`.

---

## 3. Role-Based Access Control (RBAC)

RoboFleet enforces role permissions prior to executing supervisor commands:

| Action Type | Viewer | Supervisor | Admin |
| :--- | :---: | :---: | :---: |
| `view_audit_logs` | Yes | Yes | Yes |
| `export_audit_csv` | Yes | Yes | Yes |
| `resolve_exception` | No | Yes | Yes |
| `approve_reslot` | No | Yes | Yes |
| `override_physical_constraint`| No | No | No (Blocked by SafetyGuard) |
| `inject_chaos_fault` | No | No | Yes |
| `clear_chaos_faults` | No | Yes | Yes |

---

## 4. Audit Query & CSV Export API

1. `GET /api/audit/logs`: Filter audit entries by `role`, `actor`, `action`, and `limit`.
2. `GET /api/audit/export.csv`: Streams full immutable audit trail as RFC-4180 compliant CSV:
```csv
id,audit_id,timestamp_iso,tick,actor,role,action,entity_type,entity_id,reason,result,rejection_reason
1,AUD-8f3a1e9c2b,2026-11-23T02:54:12Z,120,supervisor,supervisor,approve_reslot,sku,SKU-0012,Move to prime bin,SUCCESS,
```
