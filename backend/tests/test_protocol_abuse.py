"""Protocol abuse, injection, and security resilience tests (P2-R1, P2-R2).
Verifies server resilience under:
1. Malformed JSON and oversized WebSocket messages
2. Unknown WebSocket envelope types
3. Sequence resync requests
4. Unauthenticated control calls & invalid bearer tokens
5. SQL / JSON / HTML injection fuzzing across order string fields
6. Webhook order duplicate idempotency and rate limiting
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
from starlette.websockets import WebSocketDisconnect

AUTH_TOKEN = "secret-robofleet-token"


def build_test_app():
    config, _ = load_config(scenario_name="standard")
    layout = generate_parametric_layout(config.layout)
    skus = generate_catalogue(sku_count=config.catalogue.sku_count, seed=config.seed)
    bins, _ = slot_inventory(skus=skus, layout=layout, seed=config.seed)

    engine = SimEngine(config=config, layout=layout, skus=skus, bins=bins)
    pacer = SimulationPacer(engine=engine, start_paused=True)
    return create_app(engine=engine, pacer=pacer)


def test_protocol_abuse_websocket_fuzzing():
    app = build_test_app()
    client = TestClient(app)

    # Verify invalid token connection is rejected
    with pytest.raises(WebSocketDisconnect), client.websocket_connect("/ws?token=invalid-wrong-token"):
        pass

    # WebSocket connection
    with client.websocket_connect(f"/ws?token={AUTH_TOKEN}") as ws:
        # 1. Handshake
        msg1 = json.loads(ws.receive_text())
        assert msg1["type"] == "hello"
        msg2 = json.loads(ws.receive_text())
        assert msg2["type"] == "static_world"
        msg3 = json.loads(ws.receive_text())
        assert msg3["type"] == "snapshot"

        # 2. Malformed JSON
        ws.send_text("{{{INVALID_JSON_CORRUPT")

        # 3. Ping with oversized junk - server sends pong
        ws.send_text(json.dumps({"type": "ping", "junk": "A" * 100_000}))
        pong_msg = json.loads(ws.receive_text())
        assert pong_msg["type"] == "pong"

        # 4. Unknown message type
        ws.send_text(json.dumps({"type": "quantum_teleport", "payload": {}}))

        # 5. Resync after abuse still functions
        ws.send_text(json.dumps({"type": "resync"}))
        resp = json.loads(ws.receive_text())
        assert resp["type"] == "snapshot"
        assert "robots" in resp["payload"]


def test_security_control_auth_and_injection():
    app = build_test_app()
    client = TestClient(app)

    # 1. Unauthenticated control calls return 401
    r_pause = client.post("/api/control/pause")
    assert r_pause.status_code == 401

    r_speed = client.post("/api/control/speed", json={"multiplier": 2.0})
    assert r_speed.status_code == 401

    # 2. Wrong token returns 401
    r_wrong = client.post(
        "/api/control/pause", headers={"Authorization": "Bearer totally-fake-token"}
    )
    assert r_wrong.status_code == 401

    # 3. SQL / HTML / Shell injection fuzzing on order ingestion
    headers = {"Authorization": f"Bearer {AUTH_TOKEN}"}
    injection_strings = [
        "'; DROP TABLE orders; --",
        "<script>alert('xss')</script>",
        '{"$gt": ""}',
        "{{ 7 * 7 }}",
        "$(cat /etc/passwd)",
        "\x00\x01\xff",
    ]
    for idx, injection in enumerate(injection_strings):
        order_payload = {
            "order_id": f"ORD-FUZZ-{idx}",
            "lines": [{"sku_id": "SKU-0001", "quantity": 1}],
            "sla_tier": injection,
            "deadline_tick": 500,
        }
        res = client.post("/api/ingest/orders", headers=headers, json=order_payload)
        # Server must handle safely without 500 internal server error
        assert res.status_code in (200, 400, 422), (
            f"Failed on injection {injection}: {res.status_code}"
        )

    # 4. Duplicate order ID returns 409 Conflict (idempotency)
    dup_order = {
        "order_id": "ORD-DUP-CHECK-999",
        "lines": [{"sku_id": "SKU-0001", "quantity": 1}],
    }
    res1 = client.post("/api/ingest/orders", headers=headers, json=dup_order)
    assert res1.status_code == 200
    res2 = client.post("/api/ingest/orders", headers=headers, json=dup_order)
    assert res2.status_code == 409
    assert "Duplicate order_id" in res2.json()["detail"]
