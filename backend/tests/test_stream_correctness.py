"""Stream correctness and state consistency test (P2-R3).
Verifies bit-for-bit equivalence between client-received dynamic snapshots
and server authoritative engine state across multiple ticks and after forced resyncs.
"""

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


def test_client_state_reconstruction_matches_server_snapshot_at_100_ticks():
    config, _ = load_config(scenario_name="standard")
    layout = generate_parametric_layout(config.layout)
    skus = generate_catalogue(sku_count=config.catalogue.sku_count, seed=config.seed)
    bins, _ = slot_inventory(skus=skus, layout=layout, seed=config.seed)

    engine = SimEngine(config=config, layout=layout, skus=skus, bins=bins)
    pacer = SimulationPacer(engine=engine, start_paused=True)
    app = create_app(engine=engine, pacer=pacer)

    with TestClient(app) as client, client.websocket_connect("/ws") as ws:
        # 1. Handshake
        json.loads(ws.receive_text())  # hello
        json.loads(ws.receive_text())  # static_world
        snap_msg = json.loads(ws.receive_text())  # snapshot
        initial_robots = {r["robot_id"]: r for r in snap_msg["payload"]["robots"]}
        assert len(initial_robots) == engine.config.robot_count

        # 2. Advance 100 simulation ticks on engine
        for _ in range(100):
            engine.step()

        # 3. Request resync snapshot and compare with authoritative engine state
        ws.send_text(json.dumps({"type": "resync"}))
        authoritative_snap = json.loads(ws.receive_text())
        assert authoritative_snap["type"] == "snapshot"
        snap_robots = {r["robot_id"]: r for r in authoritative_snap["payload"]["robots"]}

        authoritative_state = engine.get_dynamic_state()
        auth_robots = {r.robot_id: r for r in authoritative_state.robots}

        # 4. Compare all robots: cell, state, heading, battery
        assert len(snap_robots) == len(auth_robots)
        for r_id, a_robot in auth_robots.items():
            s_robot = snap_robots[r_id]
            assert s_robot["cell"]["x"] == a_robot.cell.x
            assert s_robot["cell"]["y"] == a_robot.cell.y
            assert s_robot["state"] == a_robot.state.value
            assert s_robot["heading"] == a_robot.heading.value
            assert abs(s_robot["battery_pct"] - a_robot.battery_pct) < 1e-6
