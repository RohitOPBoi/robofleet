"""RoboFleet Phase 7 Flagship Acceptance Tests (P7-A1 to P7-A9).
Validates health checks, Prometheus metrics, diagnostics, security middleware,
recording replay, customer calibration, and webhook integration.
"""

from __future__ import annotations

import os
from pathlib import Path
import pytest
from starlette.testclient import TestClient

from robofleet.catalogue.generator import generate_catalogue
from robofleet.catalogue.slotting import slot_inventory
from robofleet.cli.calibrate import calibrate_profile, parse_customer_csv
from robofleet.config.loader import load_config
from robofleet.layout.generator import generate_parametric_layout
from robofleet.sim.engine import SimEngine
from robofleet.sim.pacer import SimulationPacer
from robofleet.sim.recording import RunRecorder, RunReplayer
from robofleet.api.app import create_app


@pytest.fixture
def test_stack():
    cfg, _ = load_config(scenario_name="standard", cli_overrides=["robot_count=10", "seed=42"])
    layout = generate_parametric_layout(cfg.layout, name=cfg.scenario_name)
    skus = generate_catalogue(sku_count=cfg.catalogue.sku_count, seed=cfg.seed)
    bins, _ = slot_inventory(layout=layout, skus=skus, seed=cfg.seed)
    engine = SimEngine(config=cfg, layout=layout, skus=skus, bins=bins)
    pacer = SimulationPacer(engine=engine, start_paused=True)
    app = create_app(engine=engine, pacer=pacer)
    token = os.environ.get("ROBOFLEET_TOKEN", cfg.server.auth_token)
    return TestClient(app), engine, token


def test_health_and_liveness_endpoints(test_stack):
    client, engine, _ = test_stack

    # /healthz
    res = client.get("/healthz")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"
    assert res.json()["healthy"] is True

    # /livez
    res = client.get("/livez")
    assert res.status_code == 200
    assert res.json()["status"] == "alive"

    # /readyz
    res = client.get("/readyz")
    assert res.status_code == 200
    assert res.json()["ready"] is True
    assert res.json()["active_robots"] == 10


def test_prometheus_metrics_exposition(test_stack):
    client, engine, _ = test_stack
    res = client.get("/metrics")
    assert res.status_code == 200
    assert "text/plain" in res.headers["content-type"]
    body = res.text
    assert "robofleet_active_robots 10" in body
    assert "robofleet_collisions_total 0" in body
    assert "robofleet_throughput_orders_per_hr" in body
    assert "robofleet_sim_ticks_total" in body


def test_diagnostics_endpoint(test_stack):
    client, engine, _ = test_stack
    res = client.get("/api/diagnostics")
    assert res.status_code == 200
    data = res.json()
    assert data["version"] == "1.0.0"
    assert data["memory_rss_mb"] > 0
    assert data["frame_budget_target_ms"] == 16.67
    assert data["active_robots"] == 10
    assert data["replay_active"] is False


def test_security_headers_and_payload_limits(test_stack):
    client, engine, token = test_stack

    # Check security headers on response
    res = client.get("/health")
    assert res.headers.get("X-Content-Type-Options") == "nosniff"
    assert res.headers.get("X-Frame-Options") == "DENY"
    assert "Strict-Transport-Security" in res.headers

    # Check payload size limit > 1MB
    large_payload = {"dummy": "x" * (1_048_576 + 50)}
    headers = {"Authorization": f"Bearer {token}", "Content-Length": str(len(str(large_payload)))}
    res_large = client.post("/api/control/speed", json={"multiplier": 2.0}, headers=headers)
    assert res_large.status_code == 413


def test_webhook_order_ingest_and_idempotency(test_stack):
    client, engine, token = test_stack
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "order_id": "ORD-FLAGSHIP-001",
        "lines": [{"sku_id": "SKU-BEV-001", "quantity": 2}],
        "priority": 2,
        "sla_tier": "express",
    }

    # 1. First ingest -> Accepted
    res1 = client.post("/api/orders/webhook", json=payload, headers=headers)
    assert res1.status_code == 200
    assert res1.json()["status"] == "accepted"
    assert res1.json()["order_id"] == "ORD-FLAGSHIP-001"

    # 2. Duplicate order_id -> 409 Conflict (Idempotency)
    res2 = client.post("/api/orders/webhook", json=payload, headers=headers)
    assert res2.status_code == 409
    assert "Duplicate order_id" in res2.json()["detail"]


def test_recording_and_deterministic_replay(test_stack, tmp_path):
    client, engine, token = test_stack
    headers = {"Authorization": f"Bearer {token}"}

    # Record 50 ticks
    recorder = RunRecorder(engine=engine, recording_id="test_run_replay", output_dir=str(tmp_path), snapshot_interval_ticks=10)
    for tick in range(1, 51):
        engine.step()
        recorder.record_step(tick)
    rec_path = recorder.finalize()
    assert rec_path.exists()

    # Test RunReplayer directly
    replayer = RunReplayer(rec_path)
    info = replayer.get_info()
    assert info["total_ticks"] == 50
    assert info["robot_count"] == 10

    # Seek to tick 0, 25, 50
    s0 = replayer.seek(0)
    assert s0["tick"] == 0
    s25 = replayer.seek(25)
    assert s25["tick"] == 25
    s50 = replayer.seek(50)
    assert s50["tick"] == 50

    # Test Replay API endpoints
    # Copy to runs/recordings so API can find it
    runs_rec_dir = Path("runs/recordings")
    runs_rec_dir.mkdir(parents=True, exist_ok=True)
    target_rec = runs_rec_dir / "test_api_replay.ndjson"
    target_rec.write_text(rec_path.read_text(encoding="utf-8"), encoding="utf-8")

    try:
        # 1. List recordings
        res_list = client.get("/api/replay/recordings")
        assert res_list.status_code == 200
        rec_ids = [r["id"] for r in res_list.json()]
        assert "test_api_replay" in rec_ids

        # 2. Load recording
        res_load = client.post("/api/replay/load", json={"recording_id": "test_api_replay"}, headers=headers)
        assert res_load.status_code == 200
        assert res_load.json()["status"] == "recording_loaded"

        # Check environment disclosure now says recorded_run
        env_res = client.get("/api/environment")
        assert env_res.json()["mode"] == "recorded_run"
        assert env_res.json()["is_replay"] is True

        # 3. Seek to tick 30
        res_seek = client.post("/api/replay/seek", json={"tick": 30}, headers=headers)
        assert res_seek.status_code == 200
        assert res_seek.json()["tick"] == 30

        # 4. Step
        res_step = client.post("/api/replay/step", headers=headers)
        assert res_step.status_code == 200
        assert res_step.json()["tick"] == 31

        # 5. Exit replay
        res_exit = client.post("/api/replay/exit", headers=headers)
        assert res_exit.status_code == 200
        assert res_exit.json()["mode"] == "digital_twin"

        env_after = client.get("/api/environment")
        assert env_after.json()["mode"] == "digital_twin"
        assert env_after.json()["is_replay"] is False
    finally:
        if target_rec.exists():
            target_rec.unlink()


def test_customer_calibration_tool():
    csv_file = Path("examples/customer_orders_sample.csv")
    assert csv_file.exists(), "Customer orders sample CSV must exist"

    records, stats = parse_customer_csv(csv_file)
    assert len(records) > 0
    assert stats["anomalies_detected"] == 0

    profile = calibrate_profile(records)
    assert profile["total_orders_analyzed"] > 0
    assert profile["demand_profile"]["arrival_rate_orders_per_hr"] > 0
    assert len(profile["demand_profile"]["diurnal_24h_weights"]) == 24
    assert profile["basket_distribution"]["mean_units"] > 0
    assert profile["catalogue_distribution"]["top_20_percent_sku_volume_share"] > 0
