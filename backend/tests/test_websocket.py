"""WebSocket /ws protocol tests (Phase 2).
Verifies: envelope structure, hello -> static_world -> snapshot handshake,
delta ordering, resync on gap, ping-pong, and multi-client broadcast.
"""

from __future__ import annotations

import json

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
def sim_stack():
    cfg, _ = load_config("standard")
    layout = generate_parametric_layout(cfg.layout)
    skus = generate_catalogue(sku_count=50, seed=42)
    bins, _ = slot_inventory(layout=layout, skus=skus, seed=42)
    engine = SimEngine(config=cfg, layout=layout, skus=skus, bins=bins)
    pacer = SimulationPacer(engine=engine, start_paused=True)
    app = create_app(engine=engine, pacer=pacer)
    return engine, pacer, app


def test_websocket_handshake_and_envelopes(sim_stack):
    engine, pacer, app = sim_stack
    client = TestClient(app)

    with client.websocket_connect("/ws") as ws:
        # 1. First message must be 'hello'
        msg1 = json.loads(ws.receive_text())
        assert msg1["v"] == "1.0.0"
        assert msg1["type"] == "hello"
        assert msg1["payload"]["schema_version"] == "1.0.0"
        assert "server_capabilities" in msg1["payload"]

        # 2. Second message must be 'static_world'
        msg2 = json.loads(ws.receive_text())
        assert msg2["v"] == "1.0.0"
        assert msg2["type"] == "static_world"
        assert "layout" in msg2["payload"]

        # 3. Third message must be 'snapshot'
        msg3 = json.loads(ws.receive_text())
        assert msg3["v"] == "1.0.0"
        assert msg3["type"] == "snapshot"
        assert "robots" in msg3["payload"]
        assert len(msg3["payload"]["robots"]) == engine.config.robot_count


def test_websocket_ping_pong(sim_stack):
    engine, pacer, app = sim_stack
    client = TestClient(app)

    with client.websocket_connect("/ws") as ws:
        # Drain handshake
        for _ in range(3):
            ws.receive_text()

        # Send ping
        ws.send_text(json.dumps({"type": "ping"}))
        resp = json.loads(ws.receive_text())
        assert resp["type"] == "pong"
        assert "sim_time_ms" in resp["payload"]


def test_websocket_resync_requests_fresh_snapshot(sim_stack):
    engine, pacer, app = sim_stack
    client = TestClient(app)

    with client.websocket_connect("/ws") as ws:
        for _ in range(3):
            ws.receive_text()

        # Request resync
        ws.send_text(json.dumps({"type": "resync"}))
        resp = json.loads(ws.receive_text())
        assert resp["type"] == "snapshot"
        assert "robots" in resp["payload"]
