"""Security regression tests verifying perimeter defense and audit findings."""

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
from starlette.websockets import WebSocketDisconnect


@pytest.fixture
def sec_client():
    cfg, _ = load_config("standard")
    cfg.server.auth_token = "secure-test-token-xyz"
    layout = generate_parametric_layout(cfg.layout)
    skus = generate_catalogue(sku_count=20, seed=42)
    bins, _ = slot_inventory(layout=layout, skus=skus, seed=42)
    engine = SimEngine(config=cfg, layout=layout, skus=skus, bins=bins)
    pacer = SimulationPacer(engine=engine, start_paused=True)
    app = create_app(engine=engine, pacer=pacer)
    return TestClient(app), "secure-test-token-xyz"


def test_config_effective_redacts_auth_token(sec_client):
    client, _ = sec_client
    res = client.get("/api/config/effective")
    assert res.status_code == 200
    data = res.json()
    assert "server" in data
    assert data["server"]["auth_token"] == "[REDACTED]"


def test_cors_disallows_credentials_on_wildcard(sec_client):
    client, _ = sec_client
    res = client.get("/api/config/effective", headers={"Origin": "https://attacker.example.com"})
    # When allow_origins=["*"], allow_credentials must not be "true"
    assert res.headers.get("access-control-allow-credentials") != "true"


def test_chaos_load_scenario_rejects_path_traversal(sec_client):
    client, token = sec_client
    headers = {"Authorization": f"Bearer {token}"}
    res = client.post(
        "/api/chaos/load_scenario",
        json={"scenario_name": "../../scenarios/defaults.yaml"},
        headers=headers,
    )
    assert res.status_code == 404


def test_replay_load_rejects_path_traversal(sec_client):
    client, token = sec_client
    headers = {"Authorization": f"Bearer {token}"}
    res = client.post(
        "/api/replay/load",
        json={"recording_id": "../../scenarios/defaults.yaml"},
        headers=headers,
    )
    assert res.status_code == 404


def test_websocket_rejects_invalid_token(sec_client):
    client, _ = sec_client
    with pytest.raises(WebSocketDisconnect), client.websocket_connect("/ws?token=bad-token"):
        pass
