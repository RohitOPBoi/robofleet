"""End-to-end integration tests for streaming API and static UI serving (P2-A1, P2-A2, P2-A6)."""

from __future__ import annotations

import json

from robofleet.api.app import create_app
from robofleet.catalogue.generator import generate_catalogue
from robofleet.catalogue.slotting import slot_inventory
from robofleet.config.loader import load_config
from robofleet.layout.generator import generate_parametric_layout
from robofleet.sim.engine import SimEngine
from robofleet.sim.pacer import SimulationPacer
from starlette.testclient import TestClient


def test_e2e_frontend_html_served_and_api_connected():
    config, _ = load_config(scenario_name="standard")
    layout = generate_parametric_layout(config.layout)
    skus = generate_catalogue(sku_count=config.catalogue.sku_count, seed=config.seed)
    bins, _ = slot_inventory(skus=skus, layout=layout, seed=config.seed)

    engine = SimEngine(config=config, layout=layout, skus=skus, bins=bins)
    pacer = SimulationPacer(engine=engine, start_paused=True)
    app = create_app(engine=engine, pacer=pacer)

    with TestClient(app) as client:
        # 1. UI root is served with real title
        res_index = client.get("/")
        assert res_index.status_code == 200
        assert "RoboFleet Command Centre" in res_index.text

        # 2. Environment disclosure endpoint is valid
        res_env = client.get("/api/environment")
        assert res_env.status_code == 200
        env_data = res_env.json()
        assert env_data["mode"] == "digital_twin"
        assert env_data["robot_layer"] == "simulated"
        assert env_data["data_source"] == "demand_engine"

        # 3. WebSocket stream delivers hello, static_world, snapshot, and deltas
        with client.websocket_connect("/ws") as ws:
            m1 = json.loads(ws.receive_text())
            assert m1["type"] == "hello"

            m2 = json.loads(ws.receive_text())
            assert m2["type"] == "static_world"
            assert m2["payload"]["layout"]["width"] > 0

            m3 = json.loads(ws.receive_text())
            assert m3["type"] == "snapshot"
            assert len(m3["payload"]["robots"]) == 20
