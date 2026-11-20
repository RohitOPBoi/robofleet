"""Tests for Phase 5 Governance Layer and Human-in-the-Loop Approvals Queue."""

from __future__ import annotations

import pytest
from robofleet.brain.governance import GovernanceLayer
from robofleet.contracts.brain import ApprovalRequest


@pytest.fixture
def governance() -> GovernanceLayer:
    return GovernanceLayer(rules_dir="rules")


def test_command_battery_protection_policy(governance: GovernanceLayer) -> None:
    # AMR with 10% battery should be denied task assignment
    cmd = {
        "command_type": "assign_task",
        "robot_id": "R-001",
        "task_id": "T-100",
        "task_type": "PICK",
    }
    context_state = {
        "robots": {
            "R-001": {
                "robot_id": "R-001",
                "battery_pct": 10.0,
                "state": "IDLE",
            }
        },
        "held_zones": [],
        "zones": [],
    }

    verdict = governance.evaluate_command(
        command=cmd,
        decision_id="dec-1",
        current_tick=100,
        context_state=context_state,
    )

    assert not verdict.is_approved
    assert verdict.status == "denied"
    assert "battery below 15%" in verdict.reason.lower()


def test_command_hold_zone_limit_policy(governance: GovernanceLayer) -> None:
    # Trying to hold a 3rd zone when 2 are already held should be denied
    cmd = {
        "command_type": "hold_zone",
        "zone_id": "zone_c",
    }
    context_state = {
        "robots": {},
        "held_zones": ["zone_a", "zone_b"],
        "zones": ["zone_a", "zone_b", "zone_c"],
    }

    verdict = governance.evaluate_command(
        command=cmd,
        decision_id="dec-2",
        current_tick=200,
        context_state=context_state,
    )

    assert not verdict.is_approved
    assert verdict.status == "denied"
    assert "simultaneous" in verdict.reason.lower() or "hold" in verdict.reason.lower()


def test_command_bulk_reroute_requires_human_approval(governance: GovernanceLayer) -> None:
    # Rerouting with avoid cells requires supervisor sign-off
    cmd = {
        "command_type": "reroute_robot",
        "robot_id": "R-005",
        "avoid_cells": [{"x": 10, "y": 12}],
    }
    context_state = {
        "robots": {"R-005": {"robot_id": "R-005", "battery_pct": 80.0, "state": "MOVING"}},
        "held_zones": [],
        "zones": [],
    }

    verdict = governance.evaluate_command(
        command=cmd,
        decision_id="dec-3",
        current_tick=300,
        context_state=context_state,
    )

    assert not verdict.is_approved
    assert verdict.status == "require_human"
    assert len(governance.approvals_queue.pending) == 1

    req_id = list(governance.approvals_queue.pending.keys())[0]
    req = governance.approvals_queue.pending[req_id]
    assert req.command["command_type"] == "reroute_robot"
    assert req.timeout_tick == 340  # 300 + 40


def test_approvals_queue_approve_and_reject(governance: GovernanceLayer) -> None:
    queue = governance.approvals_queue
    req = ApprovalRequest(
        decision_id="dec-test",
        command={"command_type": "hold_zone", "zone_id": "zone_c"},
        timeout_tick=150,
        default_action="deny",
        created_tick=100,
    )
    queue.pending[req.request_id] = req

    # Resolve with approval
    approved_cmd = queue.resolve(req.request_id, approve=True)
    assert approved_cmd is not None
    assert approved_cmd["zone_id"] == "zone_c"
    assert req.request_id not in queue.pending

    # Add second request and resolve with reject
    req2 = ApprovalRequest(
        decision_id="dec-test-2",
        command={"command_type": "release_zone", "zone_id": "zone_c"},
        timeout_tick=200,
        default_action="deny",
        created_tick=150,
    )
    queue.pending[req2.request_id] = req2
    rejected_cmd = queue.resolve(req2.request_id, approve=False)
    assert rejected_cmd is None
    assert req2.request_id not in queue.pending


def test_approvals_queue_timeout_expiry(governance: GovernanceLayer) -> None:
    queue = governance.approvals_queue
    req = ApprovalRequest(
        decision_id="dec-timeout",
        command={"command_type": "hold_zone", "zone_id": "zone_d"},
        timeout_tick=120,
        default_action="deny",
        created_tick=100,
    )
    queue.pending[req.request_id] = req

    # Advance to tick 110 (not expired yet)
    expired = queue.tick(110)
    assert len(expired) == 0
    assert req.request_id in queue.pending

    # Advance to tick 125 (expired)
    expired = queue.tick(125)
    assert len(expired) == 1
    assert req.request_id not in queue.pending
    assert expired[0].status == "timed_out"
