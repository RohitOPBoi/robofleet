"""Tests for Append-Only Audit Ledger and Manual Override Hard Constraint Validation (P6-A6, P6-A7, P6-R7)."""

from __future__ import annotations

import sqlite3
from pathlib import Path
import pytest

from robofleet.audit.database import AuditDatabase
from robofleet.audit.exceptions_queue import ExceptionsQueue
from robofleet.audit.validation import ManualOverrideValidator
from robofleet.contracts.catalogue import Bin, HazardClass, Sku, TemperatureClass
from robofleet.contracts.chaos import ExceptionItem
from robofleet.contracts.common import Coordinate


@pytest.fixture
def temp_audit_db(tmp_path: Path) -> AuditDatabase:
    db_file = tmp_path / "test_audit.db"
    return AuditDatabase(db_path=db_file)


def test_audit_log_is_strictly_append_only(temp_audit_db: AuditDatabase) -> None:
    """Verifies that SQLite triggers prohibit UPDATE and DELETE operations on audit_log."""
    entry = temp_audit_db.record_entry(
        tick=10,
        actor="supervisor_alice",
        role="supervisor",
        action="reassign_task",
        entity_type="robot",
        entity_id="R-001",
        reason="AMR battery low",
        result="SUCCESS",
    )

    with sqlite3.connect(str(temp_audit_db.db_path)) as conn:
        # Try UPDATE -> Must fail with trigger error
        with pytest.raises(sqlite3.DatabaseError, match="strictly append-only"):
            conn.execute("UPDATE audit_log SET actor = 'forged_actor' WHERE id = 1;")

        # Try DELETE -> Must fail with trigger error
        with pytest.raises(sqlite3.DatabaseError, match="strictly append-only"):
            conn.execute("DELETE FROM audit_log WHERE id = 1;")


def test_audit_role_permissions_and_rejection_logging(temp_audit_db: AuditDatabase) -> None:
    """Viewer cannot resolve exceptions; supervisor can; rejected attempts are logged."""
    queue = ExceptionsQueue(audit_db=temp_audit_db)

    exc = ExceptionItem(
        exception_type="damaged_item",
        severity="HIGH",
        entity_id="SKU-99",
        raised_tick=10,
        deadline_tick=100,
        default_action="write_off_and_reslot",
        recommended_action="Write off",
        available_actions=["write_off_and_reslot", "return_to_vendor"],
    )
    queue.add_exception(exc)

    # 1. Viewer tries to resolve -> Rejected
    ok, msg = queue.resolve_exception(
        exception_id=exc.exception_id,
        action="write_off_and_reslot",
        actor="viewer_bob",
        role="viewer",
        reason="Trying to resolve as viewer",
        current_tick=15,
    )
    assert not ok
    assert "Permission denied" in msg

    # Verify rejection was logged
    logs = temp_audit_db.query_logs(role="viewer")
    assert len(logs) == 1
    assert logs[0]["result"] == "REJECTED"
    assert "Permission denied" in logs[0]["rejection_reason"] or "lacks permission" in logs[0]["rejection_reason"]

    # 2. Supervisor resolves with invalid action -> Rejected
    ok_inv, msg_inv = queue.resolve_exception(
        exception_id=exc.exception_id,
        action="unsupported_magical_fix",
        actor="supervisor_carol",
        role="supervisor",
        reason="Trying invalid action",
        current_tick=16,
    )
    assert not ok_inv
    assert "Invalid action" in msg_inv

    # 3. Supervisor resolves with valid action -> Success
    ok_valid, msg_valid = queue.resolve_exception(
        exception_id=exc.exception_id,
        action="write_off_and_reslot",
        actor="supervisor_carol",
        role="supervisor",
        reason="Approved write-off",
        current_tick=20,
    )
    assert ok_valid
    assert exc.exception_id not in queue.pending_exceptions

    logs_success = temp_audit_db.query_logs(actor="supervisor_carol")
    assert any(l["result"] == "SUCCESS" for l in logs_success)


def test_audit_csv_export(temp_audit_db: AuditDatabase) -> None:
    temp_audit_db.record_entry(
        tick=5,
        actor="admin",
        role="admin",
        action="clear_fault",
        entity_type="robot",
        entity_id="R-002",
        reason="Test clearing fault",
        result="SUCCESS",
    )
    csv_str = temp_audit_db.export_csv()
    assert "audit_id,timestamp_iso,tick,actor,role,action" in csv_str
    assert "R-002" in csv_str
    assert "clear_fault" in csv_str


def test_manual_override_hard_constraints_validation() -> None:
    """P6-A7: Hard-constraint validation blocks violations (temp, weight, chemical, level)."""
    # 1. Temperature constraint
    chilled_sku = Sku(
        sku_id="SKU-CHILLED",
        name="Greek Yogurt",
        category="dairy",
        pack_size="500g",
        mrp_inr=80.0,
        popularity_rank=10,
        unit_weight_g=500,
        temperature_class=TemperatureClass.CHILLED,
    )
    ambient_bin = Bin(bin_id="BIN-A1", cell=Coordinate(x=2, y=2), level=2, capacity=50, max_weight_g=25000)

    # Chilled SKU in ambient bin must FAIL
    valid, reason = ManualOverrideValidator.validate_placement(chilled_sku, ambient_bin, bin_zone_temp="ambient")
    assert not valid
    assert "Temperature violation" in reason

    # Chilled SKU in chilled bin must PASS
    valid_c, _ = ManualOverrideValidator.validate_placement(chilled_sku, ambient_bin, bin_zone_temp="chilled")
    assert valid_c

    # 2. Heavy shelf constraint (>5000g on level >= 4)
    heavy_sku = Sku(
        sku_id="SKU-HEAVY",
        name="Rice Sack 10kg",
        category="staples",
        pack_size="10kg",
        mrp_inr=600.0,
        popularity_rank=20,
        unit_weight_g=10000,
    )
    top_shelf_bin = Bin(bin_id="BIN-TOP", cell=Coordinate(x=2, y=2), level=4, capacity=10, max_weight_g=50000)
    bottom_shelf_bin = Bin(bin_id="BIN-BTM", cell=Coordinate(x=2, y=2), level=1, capacity=10, max_weight_g=50000)

    # Heavy SKU on top shelf must FAIL
    valid_h, reason_h = ManualOverrideValidator.validate_placement(heavy_sku, top_shelf_bin)
    assert not valid_h
    assert "Heavy shelf violation" in reason_h

    # Heavy SKU on bottom shelf must PASS
    valid_b, _ = ManualOverrideValidator.validate_placement(heavy_sku, bottom_shelf_bin)
    assert valid_b

    # 3. Chemical isolation constraint
    bleach_sku = Sku(
        sku_id="SKU-BLEACH",
        name="Floor Disinfectant Bleach",
        category="cleaning",
        pack_size="1L",
        mrp_inr=150.0,
        popularity_rank=30,
        unit_weight_g=1200,
        hazard_class=HazardClass.CHEMICAL,
    )
    # Bleach adjacent to dairy/food must FAIL
    valid_chem, reason_chem = ManualOverrideValidator.validate_placement(
        bleach_sku, bottom_shelf_bin, adjacent_category="dairy"
    )
    assert not valid_chem
    assert "Chemical isolation violation" in reason_chem

    # Bleach adjacent to cleaning aisle must PASS
    valid_chem_ok, _ = ManualOverrideValidator.validate_placement(
        bleach_sku, bottom_shelf_bin, adjacent_category="cleaning"
    )
    assert valid_chem_ok
