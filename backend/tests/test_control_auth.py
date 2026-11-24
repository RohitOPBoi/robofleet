"""Control channel authentication and REST endpoints tests (P2-A3, P2-A9).
Ensures all state-changing control endpoints are strictly token-gated,
and public disclosure endpoints are accessible and accurate.
"""

from __future__ import annotations

import pytest
from robofleet.api.app import create_app
from robofleet.catalogue.generator import generate_catalogue
from robofleet.catalogue.slotting import slot_inventory
from robofleet.config.loader import load_config
from robofleet.layout.generator import generate_parametric_layout
from robofleet.sim.engine import SimEngine
from robofleet.sim.pacer import SimulationPacer
from starlette.testclient import TestClient


@pytest.fixture
def api_client():
    cfg, _ = load_config("standard")
    cfg.server.auth_token = "test-secret-token"
    layout = generate_parametric_layout(cfg.layout)
    skus = generate_catalogue(sku_count=50, seed=42)
    bins, _ = slot_inventory(layout=layout, skus=skus, seed=42)
    engine = SimEngine(config=cfg, layout=layout, skus=skus, bins=bins)
    pacer = SimulationPacer(engine=engine, start_paused=True)
    app = create_app(engine=engine, pacer=pacer)
    return TestClient(app), "test-secret-token"


def test_public_endpoints_accessible_without_token(api_client):
    client, _ = api_client

    # /health
    r_health = client.get("/health")
    assert r_health.status_code == 200
    assert r_health.json()["status"] == "ok"
    assert r_health.json()["mode"] == "digital_twin"

    # /api/environment (Single disclosure surface)
    r_env = client.get("/api/environment")
    assert r_env.status_code == 200
    env_data = r_env.json()
    assert env_data["mode"] == "digital_twin"
    assert env_data["robot_layer"] == "simulated"
    assert "demand_engine" in env_data["active_adapters"]

    # /api/scenarios
    r_scen = client.get("/api/scenarios")
    assert r_scen.status_code == 200
    assert "standard" in r_scen.json()

    # /api/rules
    r_rules = client.get("/api/rules")
    assert r_rules.status_code == 200
    assert len(r_rules.json()) >= 7


def test_control_endpoints_reject_unauthenticated_requests(api_client):
    client, _ = api_client

    control_endpoints = [
        ("POST", "/api/control/pause", {}),
        ("POST", "/api/control/resume", {}),
        ("POST", "/api/control/speed", {"multiplier": 2.0}),
        ("POST", "/api/control/step", {}),
        ("POST", "/api/control/rush", {"multiplier": 2.5}),
        ("POST", "/api/control/emergency_stop", {"scope": "all"}),
        ("POST", "/api/control/resume_emergency", {"scope": "all"}),
        ("POST", "/api/control/block_cells", {"cells": [{"x": 1, "y": 1}]}),
        ("POST", "/api/control/unblock_cells", {"cells": [{"x": 1, "y": 1}]}),
        (
            "POST",
            "/api/ingest/orders",
            {"order_id": "ORD-1", "lines": [{"sku_id": "SKU-1", "quantity": 1}]},
        ),
    ]

    for method, path, payload in control_endpoints:
        # 1. No token provided -> 401
        res_no_token = client.request(method, path, json=payload)
        assert res_no_token.status_code == 401, f"{path} did not reject unauthenticated request"

        # 2. Wrong token provided -> 401
        res_bad_token = client.request(
            method, path, json=payload, headers={"Authorization": "Bearer wrong-token"}
        )
        assert res_bad_token.status_code == 401, f"{path} did not reject invalid token"


def test_control_endpoints_accept_valid_token(api_client):
    client, valid_token = api_client
    headers = {"Authorization": f"Bearer {valid_token}"}

    # Speed control
    res_speed = client.post("/api/control/speed", json={"multiplier": 3.0}, headers=headers)
    assert res_speed.status_code == 200
    assert res_speed.json()["speed_multiplier"] == 3.0

    # Pause & resume
    assert client.post("/api/control/pause", headers=headers).status_code == 200
    assert client.post("/api/control/resume", headers=headers).status_code == 200

    # Rush
    res_rush = client.post(
        "/api/control/rush", json={"multiplier": 2.0, "duration_s": 60}, headers=headers
    )
    assert res_rush.status_code == 200

    # E-stop
    res_estop = client.post("/api/control/emergency_stop", json={"scope": "all"}, headers=headers)
    assert res_estop.status_code == 200
    assert res_estop.json()["status"] == "emergency_stop_queued"
