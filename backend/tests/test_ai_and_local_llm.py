"""Comprehensive test suite for AI Mode (Cloud LLMs), Local LLM Mode (Ollama),
multi-robot deadlock detection & recovery, non-blocking orchestrator execution,
governance enforcement, API key confidentiality, real outcome measurement, and
API/evaluation parity.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from robofleet.api.app import create_app
from robofleet.brain.credentials import SecretCredentialStore, SecretRedactingFilter
from robofleet.brain.deadlock import DeadlockAnalyzer
from robofleet.brain.orchestrator import MissionOrchestrator
from robofleet.brain.prompt_builder import build_decision_messages
from robofleet.brain.providers.ai_mode import UnifiedAIProvider
from robofleet.brain.providers.base import LLMProviderResult, collect_and_arbitrate_specialists
from robofleet.brain.providers.ollama import OllamaProvider
from robofleet.brain.providers.openai_compatible import OpenAICompatibleProvider
from robofleet.brain.specialists.exceptions import ExceptionsRecoverySpecialist
from robofleet.brain.specialists.explainer import ExplainerSpecialist
from robofleet.brain.specialists.planner import PlannerSpecialist
from robofleet.brain.specialists.traffic import TrafficFleetSpecialist
from robofleet.catalogue.generator import generate_catalogue
from robofleet.catalogue.slotting import slot_inventory
from robofleet.cli.eval_ai import run_single_eval_mode
from robofleet.config.loader import load_config
from robofleet.config.models import AICloudConfig
from robofleet.contracts.brain import (
    BriefDeadlockInfo,
    BriefKPIs,
    BriefOrderSummary,
    BriefRobotSummary,
    BriefStationQueue,
    SituationBrief,
)
from robofleet.contracts.common import Coordinate
from robofleet.contracts.order import Order, OrderLine, OrderStatus
from robofleet.contracts.robot import RobotState
from robofleet.layout.generator import generate_parametric_layout
from robofleet.sim.engine import SimEngine
from robofleet.sim.pacer import SimulationPacer


def _make_engine(scenario: str = "small", seed: int = 42, robot_count: int | None = None) -> SimEngine:
    overrides = [f"seed={seed}"]
    if robot_count is not None:
        overrides.append(f"robot_count={robot_count}")
    cfg, _ = load_config(scenario_name=scenario, cli_overrides=overrides)
    layout = generate_parametric_layout(cfg.layout)
    skus = generate_catalogue(sku_count=cfg.catalogue.sku_count, seed=seed)
    bins, _ = slot_inventory(skus=skus, layout=layout, seed=seed)
    return SimEngine(config=cfg, layout=layout, skus=skus, bins=bins)


def _sample_brief() -> SituationBrief:
    return SituationBrief(
        tick=50,
        trigger="deadlock_detected",
        kpis=BriefKPIs(
            queue_depth=4,
            throughput_per_hr=110.0,
            at_risk_count=1,
            active_alerts_count=1,
            robots_moving=4,
            robots_idle=2,
            robots_blocked=2,
            robots_charging=0,
            deadlocks_count=1,
            fleet_utilization_pct=75.0,
        ),
        at_risk_orders=[
            BriefOrderSummary(
                order_id="ORD-001",
                lines_count=1,
                sla_remaining_ticks=70,
                priority=3,
                assigned_robot_id=None,
                state="QUEUED",
            )
        ],
        station_queues=[
            BriefStationQueue(station_id="ST-01", queue_length=4, max_capacity=6),
            BriefStationQueue(station_id="ST-02", queue_length=0, max_capacity=6),
        ],
        critical_robots=[
            BriefRobotSummary(
                robot_id="R-001",
                state="WAITING",
                battery_percent=19.0,
                current_coord=Coordinate(x=4, y=4),
                blocked_ticks=14,
            ),
            BriefRobotSummary(
                robot_id="R-002",
                state="MOVING",
                battery_percent=82.0,
                current_coord=Coordinate(x=5, y=4),
                blocked_ticks=14,
            ),
        ],
        robots_overview=[
            BriefRobotSummary(
                robot_id="R-001",
                state="WAITING",
                battery_percent=19.0,
                current_coord=Coordinate(x=4, y=4),
                blocked_ticks=14,
            ),
            BriefRobotSummary(
                robot_id="R-002",
                state="MOVING",
                battery_percent=82.0,
                current_coord=Coordinate(x=5, y=4),
                blocked_ticks=14,
            ),
        ],
        deadlocks_detected=[
            BriefDeadlockInfo(
                conflict_id="COR-R-001-R-002",
                conflict_type="facing_corridor",
                robots_involved=["R-001", "R-002"],
                conflict_cells=[Coordinate(x=4, y=4), Coordinate(x=5, y=4)],
                recommended_yield_robot="R-002",
                recommended_yield_cell=Coordinate(x=5, y=5),
                recommended_priority_robot="R-001",
                max_blocked_ticks=14,
                description="Head-on corridor lock between R-001 and R-002",
            )
        ],
        congested_cells=[Coordinate(x=4, y=4)],
        available_chargers=["CHG-01"],
        available_zones=["PICK_NORTH"],
        brief_hash="abc123def456",
    )


def _specialists():
    return [
        PlannerSpecialist(),
        TrafficFleetSpecialist(),
        ExceptionsRecoverySpecialist(),
        ExplainerSpecialist(),
    ]


def _patch_httpx_mock(monkeypatch: pytest.MonkeyPatch, handler: Any) -> None:
    transport = httpx.MockTransport(handler)
    real_async_client = httpx.AsyncClient

    def _client_factory(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        kwargs["transport"] = transport
        return real_async_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", _client_factory)


@pytest.mark.asyncio
async def test_openai_compatible_chat_and_responses_modes(monkeypatch: pytest.MonkeyPatch) -> None:
    seen_requests: list[tuple[str, str, dict[str, Any]]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8")) if request.content else {}
        seen_requests.append((request.method, str(request.url), body))
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": "gpt-4o-mini"}, {"id": "gpt-4.1-mini"}]})
        if request.url.path.endswith("/chat/completions"):
            assert request.headers.get("authorization") == "Bearer test-cloud-key-999"
            payload = {
                "situation_summary": "Corridor conflict R-001 vs R-002 resolved.",
                "commands": [
                    {
                        "command_type": "yield_robot",
                        "robot_id": "R-002",
                        "yield_cell": {"x": 5, "y": 5},
                        "priority_robot_id": "R-001",
                        "hold_ticks": 10,
                        "reason": "Clear facing corridor for low-battery R-001",
                    }
                ],
                "rationale": "R-002 yields at (5,5) while R-001 passes.",
                "confidence": 0.92,
            }
            return httpx.Response(
                200,
                json={
                    "choices": [{"message": {"content": json.dumps(payload)}}],
                    "usage": {"prompt_tokens": 180, "completion_tokens": 55},
                },
            )
        if request.url.path.endswith("/responses"):
            return httpx.Response(
                200,
                json={
                    "output_text": json.dumps(
                        {
                            "situation_summary": "Express escalation.",
                            "commands": [
                                {
                                    "command_type": "reprioritise_order",
                                    "order_id": "ORD-001",
                                    "new_priority": 10,
                                    "reason": "Prevent SLA breach",
                                }
                            ],
                            "rationale": "Promoted ORD-001 to priority 10.",
                            "confidence": 0.88,
                        }
                    ),
                    "usage": {"input_tokens": 120, "output_tokens": 40},
                },
            )
        return httpx.Response(404, json={"error": {"message": "Not found"}})

    _patch_httpx_mock(monkeypatch, handler)
    store = SecretCredentialStore()
    brief = _sample_brief()

    provider = OpenAICompatibleProvider(
        api_key="test-cloud-key-999",
        provider_label="OpenAI",
        api_compatibility="openai_chat",
        base_url="https://api.example.test/v1",
        model="gpt-4o-mini",
        credential_store=store,
    )

    health = await provider.test_connection()
    assert health.ok is True
    models = await provider.list_models()
    assert "gpt-4o-mini" in models

    res_chat = await provider.decide(brief, _specialists())
    assert res_chat.operating_mode == "ai"
    assert res_chat.provider_name == "OpenAI"
    assert res_chat.model_name == "gpt-4o-mini"
    assert res_chat.fallback_used is False
    assert res_chat.commands[0]["command_type"] == "yield_robot"
    assert "AI Mode" in res_chat.attribution

    # Switch compatibility to Responses API
    provider.api_compatibility = "openai_responses"
    res_resp = await provider.decide(brief, _specialists())
    assert res_resp.fallback_used is False
    assert res_resp.commands[0]["command_type"] == "reprioritise_order"
    assert any(url.endswith("/responses") for _, url, _ in seen_requests)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status_code", "err_msg"),
    [
        (401, "Invalid API key provided"),
        (404, "Model not found"),
        (429, "Rate limit exceeded"),
    ],
)
async def test_openai_compatible_failures_trigger_honest_fallback_not_misattributed(
    monkeypatch: pytest.MonkeyPatch, status_code: int, err_msg: str
) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json={"error": {"message": err_msg}})

    _patch_httpx_mock(monkeypatch, handler)
    store = SecretCredentialStore()
    provider = OpenAICompatibleProvider(
        api_key="sk-secret-value-xyz",
        provider_label="OpenAI",
        base_url="https://api.example.test/v1",
        model="gpt-4o-mini",
        retry_count=0,
        circuit_threshold=2,
        credential_store=store,
    )

    res1 = await provider.decide(_sample_brief(), _specialists())
    assert res1.fallback_used is True
    assert res1.provider_name == "Heuristic fallback"
    assert res1.provider_status == "fallback"
    assert "Heuristic fallback" in res1.attribution
    assert "sk-secret-value-xyz" not in res1.fallback_reason
    assert len(res1.commands) >= 1

    # Second failure trips circuit breaker; safe_wait policy should hold instead of heuristic
    provider.fallback_policy = "safe_wait"
    res2 = await provider.decide(_sample_brief(), _specialists())
    assert provider.circuit_tripped is True
    assert res2.fallback_used is True
    assert res2.provider_name == "Safe wait fallback"
    assert res2.commands[0]["command_type"] == "no_action"


@pytest.mark.asyncio
async def test_openai_compatible_rejects_invalid_json_and_hallucinated_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = {"n": 0}

    def handler(_request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            # First call sends one valid action alongside hallucinated robot ID R-999
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "commands": [
                                            {"command_type": "send_to_charge", "robot_id": "R-001", "reason": "Charge R-001"},
                                            {"command_type": "send_to_charge", "robot_id": "R-999", "reason": "Phantom"},
                                        ],
                                        "rationale": "Valid R-001 + bogus R-999",
                                    }
                                )
                            }
                        }
                    ]
                },
            )
        return httpx.Response(200, json={"choices": [{"message": {"content": "NOT JSON {{{{"}}]})

    _patch_httpx_mock(monkeypatch, handler)
    store = SecretCredentialStore()
    provider = OpenAICompatibleProvider(
        api_key="or-key-123456",
        provider_label="OpenRouter",
        base_url="https://openrouter.ai/api/v1",
        model="openai/gpt-4o-mini",
        retry_count=0,
        credential_store=store,
    )

    res_hallucinated = await provider.decide(_sample_brief(), _specialists())
    assert res_hallucinated.fallback_used is False
    assert len(res_hallucinated.commands) == 1
    assert res_hallucinated.commands[0]["robot_id"] == "R-001"
    assert len(res_hallucinated.rejected_commands) == 1
    assert "R-999" in str(res_hallucinated.rejected_commands[0])

    res_bad_json = await provider.decide(_sample_brief(), _specialists())
    assert res_bad_json.fallback_used is True
    assert res_bad_json.provider_name == "Heuristic fallback"


@pytest.mark.asyncio
async def test_anthropic_adapter_custom_endpoint_and_unified_ai_routing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("x-api-key") == "sk-ant-secret-555"
        return httpx.Response(
            200,
            json={
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(
                            {
                                "commands": [
                                    {"command_type": "send_to_charge", "robot_id": "R-001", "reason": "Low battery"}
                                ],
                                "rationale": "Route R-001 to charger.",
                            }
                        ),
                    }
                ],
                "usage": {"input_tokens": 100, "output_tokens": 30},
            },
        )

    _patch_httpx_mock(monkeypatch, handler)
    store = SecretCredentialStore()
    store.set_key("anthropic", "sk-ant-secret-555")
    ai_provider = UnifiedAIProvider(
        cloud_config=AICloudConfig(
            provider_type="anthropic",
            provider_label="Anthropic",
            api_compatibility="anthropic_messages",
            base_url="https://custom-anthropic.test",
            model="claude-3-5-sonnet-20241022",
        ),
        credential_store=store,
    )
    res = await ai_provider.decide(_sample_brief(), _specialists())
    assert res.operating_mode == "ai"
    assert res.fallback_used is False
    assert res.commands[0]["command_type"] == "send_to_charge"
    assert "Anthropic" in res.attribution


@pytest.mark.asyncio
async def test_ollama_provider_qwen35_health_think_stripping_and_offline_handling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = {"mode": "healthy_think", "seen_chat_payloads": []}

    def handler(request: httpx.Request) -> httpx.Response:
        if state["mode"] == "offline":
            raise httpx.ConnectError("Connection refused", request=request)
        if state["mode"] == "timeout":
            raise httpx.ReadTimeout("Timed out", request=request)

        if request.url.path.endswith("/api/tags"):
            if state["mode"] == "missing_model":
                return httpx.Response(200, json={"models": [{"name": "llama3:8b"}]})
            return httpx.Response(200, json={"models": [{"name": "qwen3.5:4b"}, {"name": "llama3.2:3b"}]})

        if request.url.path.endswith("/api/chat"):
            payload = json.loads(request.content.decode("utf-8"))
            state["seen_chat_payloads"].append(payload)
            if state["mode"] == "oom":
                return httpx.Response(500, text="model requires more system memory than available")
            if state["mode"] == "reject_think" and "think" in payload:
                return httpx.Response(400, text="unknown field 'think'")
            # Simulate Qwen model emitting <think> block around JSON even when stripped
            content = (
                "<think>Check R-001 vs R-002 corridor lock, pick R-002 to yield.</think>\n"
                + json.dumps(
                    {
                        "situation_summary": "Deadlock cleared locally via qwen3.5:4b.",
                        "commands": [
                            {
                                "command_type": "yield_robot",
                                "robot_id": "R-002",
                                "yield_cell": {"x": 5, "y": 5},
                                "priority_robot_id": "R-001",
                                "hold_ticks": 12,
                                "reason": "Step aside cleanly",
                            }
                        ],
                        "rationale": "Local LLM yielded R-002 to free corridor.",
                        "confidence": 0.9,
                    }
                )
            )
            return httpx.Response(
                200,
                json={"message": {"role": "assistant", "content": content}, "prompt_eval_count": 210, "eval_count": 65},
            )
        return httpx.Response(404)

    _patch_httpx_mock(monkeypatch, handler)
    ollama = OllamaProvider(model="qwen3.5:4b", retry_count=0, circuit_threshold=3)

    # 1. Healthy check detects qwen3.5:4b
    health = await ollama.check_health(force=True)
    assert health.ok is True
    assert "qwen3.5:4b" in health.available_models

    # 2. Missing model reported clearly
    state["mode"] = "missing_model"
    missing_health = await ollama.check_health(force=True)
    assert missing_health.ok is False
    assert missing_health.status == "unavailable"
    assert "ollama pull qwen3.5:4b" in missing_health.message

    # 3. Healthy inference parses JSON & strips <think> block + uses num_ctx=4096
    state["mode"] = "healthy_think"
    res = await ollama.decide(_sample_brief(), _specialists())
    assert res.operating_mode == "local_llm"
    assert res.provider_name == "Ollama"
    assert res.model_name == "qwen3.5:4b"
    assert res.fallback_used is False
    assert res.cost_usd == 0.0
    assert res.commands[0]["command_type"] == "yield_robot"
    assert state["seen_chat_payloads"][0]["options"]["num_ctx"] == 4096

    # 4. Retry cleanly when older Ollama rejects 'think' flag
    state["mode"] = "reject_think"
    res_compat = await ollama.decide(_sample_brief(), _specialists())
    assert res_compat.fallback_used is False

    # 5. OOM / Offline triggers explicit local fallback (never cloud AI!)
    state["mode"] = "oom"
    res_oom = await ollama.decide(_sample_brief(), _specialists())
    assert res_oom.fallback_used is True
    assert res_oom.operating_mode == "local_llm"
    assert "memory" in res_oom.fallback_reason.lower()

    state["mode"] = "offline"
    ollama.reset_circuit()
    res_off = await ollama.decide(_sample_brief(), _specialists())
    assert res_off.fallback_used is True
    assert "offline" in res_off.fallback_reason.lower() or "refused" in res_off.fallback_reason.lower()


def test_api_key_confidentiality_and_log_prompt_config_redaction(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    secret_val = "sk-topsecret-neverleak-987654321"
    monkeypatch.setenv("ROBOFLEET_AI_API_KEY", secret_val)
    monkeypatch.setenv("OPENAI_API_KEY", secret_val)

    # 1. Config loader must never store secret env vars into ScenarioConfig
    cfg, sources = load_config(scenario_name="small")
    dumped = json.dumps(cfg.model_dump())
    assert secret_val not in dumped
    assert "ROBOFLEET_AI_API_KEY" not in repr(getattr(sources, "origins", sources))
    assert secret_val not in repr(getattr(sources, "origins", sources))

    # 2. Prompt builder must never contain API keys
    proposals = collect_and_arbitrate_specialists(_sample_brief(), _specialists())
    messages = build_decision_messages(_sample_brief(), proposals)
    assert secret_val not in json.dumps(messages)

    # 3. SecretRedactingFilter scrubs logs and messages
    store = SecretCredentialStore()
    store.set_key("openai", secret_val)
    redactor = SecretRedactingFilter(store)
    logger = logging.getLogger("robofleet.test.secret")
    logger.addFilter(redactor)
    try:
        with caplog.at_level(logging.WARNING, logger="robofleet.test.secret"):
            logger.warning("Upstream failed with bearer %s", secret_val)
        assert secret_val not in caplog.text
        assert "[REDACTED" in caplog.text
    finally:
        logger.removeFilter(redactor)


@pytest.mark.asyncio
async def test_deadlock_detection_all_patterns_and_end_to_end_yield_recovery() -> None:
    engine = _make_engine("small", seed=12, robot_count=4)
    # Find a horizontal walkable corridor triple: c_left, c_mid, c_right with at least one adjacent branch off c_left/c_mid
    grid = {c.pos.as_tuple(): c for c in engine.layout.cells}
    corridor: tuple[Coordinate, Coordinate, Coordinate] | None = None
    for (x, y), cell in sorted(grid.items()):
        if not cell.is_walkable:
            continue
        left = grid.get((x - 1, y))
        right = grid.get((x + 1, y))
        up = grid.get((x, y - 1))
        down = grid.get((x, y + 1))
        if (
            left
            and left.is_walkable
            and right
            and right.is_walkable
            and ((up and up.is_walkable) or (down and down.is_walkable))
        ):
            corridor = (left.pos, cell.pos, right.pos)
            break
    assert corridor is not None
    c_left, c_mid, c_right = corridor

    r1, r2, r3, r4 = engine.robots[:4]
    # Clear other destinations & simulate head-on corridor stall
    r1.cell = c_left
    r2.cell = c_mid
    r1.blocked_ticks = 15
    r2.blocked_ticks = 15
    r1.battery_pct = 20.0  # R-001 lower battery -> gets right of way
    r2.battery_pct = 85.0
    r3.cell = Coordinate(x=r3.cell.x, y=r3.cell.y)
    r4.cell = Coordinate(x=r4.cell.x, y=r4.cell.y)
    engine.last_destinations[r1.robot_id] = c_right
    engine.last_destinations[r2.robot_id] = c_left

    analyzer = DeadlockAnalyzer()
    conflicts = analyzer.analyze(engine, no_progress_ticks=12)
    assert any(c.conflict_type == "facing_corridor" for c in conflicts)
    cor = next(c for c in conflicts if c.conflict_type == "facing_corridor")
    assert cor.recommended_priority_robot == r1.robot_id
    assert cor.recommended_yield_robot == r2.robot_id
    assert cor.recommended_yield_cell is not None

    # Execute through MissionOrchestrator & advance simulation ticks
    orch = MissionOrchestrator(engine=engine, provider_name="heuristic", rules_dir="rules")
    dec = await orch.step(engine.clock.tick, force_trigger=True)
    assert dec is not None
    assert any(c.get("command_type") == "yield_robot" for c in dec.final_commands)

    start_r2_cell = r2.cell
    for _ in range(8):
        engine.step()
    assert r2.cell != start_r2_cell or len(engine.ai_yield_directives) == 0


def test_deadlock_analyzer_detects_circular_3robot_cycle() -> None:
    engine = _make_engine("small", seed=5, robot_count=4)
    grid = {c.pos.as_tuple(): c for c in engine.layout.cells}
    # Locate 3 mutually adjacent walkable cells forming an L corner (or cycle intent via next step)
    tri: tuple[Coordinate, Coordinate, Coordinate] | None = None
    for (x, y), cell in sorted(grid.items()):
        if not cell.is_walkable:
            continue
        c2 = grid.get((x + 1, y))
        c3 = grid.get((x + 1, y + 1))
        c4 = grid.get((x, y + 1))
        if c2 and c2.is_walkable and c3 and c3.is_walkable and c4 and c4.is_walkable:
            tri = (cell.pos, c2.pos, c3.pos)
            break
    assert tri is not None
    r1, r2, r3 = engine.robots[:3]
    r1.cell, r2.cell, r3.cell = tri
    r1.blocked_ticks = r2.blocked_ticks = r3.blocked_ticks = 14
    engine.last_destinations[r1.robot_id] = tri[1]
    engine.last_destinations[r2.robot_id] = tri[2]
    engine.last_destinations[r3.robot_id] = tri[0]

    conflicts = DeadlockAnalyzer().analyze(engine, no_progress_ticks=12)
    assert any(
        c.conflict_type in ("circular_deadlock", "facing_corridor", "intersection_conflict", "blocked_route")
        for c in conflicts
    )


def test_all_orchestrator_command_handlers_real_state_and_validation() -> None:
    engine = _make_engine("small", seed=9, robot_count=4)
    orch = MissionOrchestrator(engine=engine, provider_name="heuristic", rules_dir="rules")

    # Add a pending order backed by a real stocked SKU
    stocked_bin = next(b for b in engine.bins if b.sku_id and b.quantity > 0)
    ord_obj = Order(
        order_id="ORD-CUSTOM-1",
        priority=2,
        status=OrderStatus.QUEUED,
        created_tick=0,
        deadline_tick=500,
        lines=[OrderLine(sku_id=stocked_bin.sku_id, quantity=1)],
    )
    engine.orders.append(ord_obj)

    robot = engine.robots[0]
    robot.battery_pct = 20.0
    # 1. send_to_charge routes via ai_charge_overrides instead of faking CHARGING away from charger
    ok_charge, _ = orch._execute_command({"command_type": "send_to_charge", "robot_id": robot.robot_id}, 10)
    assert ok_charge is True
    assert robot.robot_id in engine.ai_charge_overrides
    if robot.cell != engine.ai_charge_overrides[robot.robot_id]:
        assert robot.state != RobotState.CHARGING

    # 2. reprioritise_order
    ok_prio, _ = orch._execute_command(
        {"command_type": "reprioritise_order", "order_id": "ORD-CUSTOM-1", "new_priority": 10}, 10
    )
    assert ok_prio is True
    assert ord_obj.priority == 10
    assert ord_obj.sla_tier == "express"

    # 3. batch_orders
    st_id = next(iter(engine.station_mgr.station_defs.keys()))
    ok_batch, _ = orch._execute_command(
        {"command_type": "batch_orders", "order_ids": ["ORD-CUSTOM-1"], "target_station_id": st_id}, 10
    )
    assert ok_batch is True
    assert ord_obj.assigned_station_id == st_id

    # 4. assign_task PICK
    idle_r = engine.robots[1]
    idle_r.state = RobotState.IDLE
    idle_r.current_task_id = None
    ok_pick, _ = orch._execute_command(
        {"command_type": "assign_task", "robot_id": idle_r.robot_id, "task_type": "PICK", "order_id": "ORD-CUSTOM-1"},
        11,
    )
    assert ok_pick is True
    assert idle_r.current_task_id is not None

    # 5. set_station_policy & set_strategy_params
    ok_st, _ = orch._execute_command(
        {"command_type": "set_station_policy", "station_id": st_id, "max_queue_depth": 4}, 12
    )
    assert ok_st is True
    assert engine.station_mgr.max_queue_capacity == 4

    ok_sp, _ = orch._execute_command(
        {"command_type": "set_strategy_params", "strategy_name": "robot_supervisor", "params": {"rush_boost": 1.5}}, 12
    )
    assert ok_sp is True

    # 6. hold_zone & release_zone
    if engine.layout.zones:
        z_name = engine.layout.zones[0].name
        ok_hz, _ = orch._execute_command({"command_type": "hold_zone", "zone_id": z_name, "duration_ticks": 5}, 12)
        assert ok_hz is True
        assert z_name in orch.held_zones
        assert len(engine.held_zone_cells) > 0
        ok_rz, _ = orch._execute_command({"command_type": "release_zone", "zone_id": z_name}, 13)
        assert ok_rz is True
        assert z_name not in orch.held_zones

    # 7. clear_fault
    faulted_r = engine.robots[2]
    faulted_r.fault = "motor_jam"
    faulted_r.state = RobotState.UNAVAILABLE
    ok_cf, _ = orch._execute_command({"command_type": "clear_fault", "target_id": faulted_r.robot_id}, 13)
    assert ok_cf is True
    assert faulted_r.fault is None
    assert faulted_r.state == RobotState.IDLE

    # 8. Invalid command rejected cleanly without silent success
    ok_live, _, _ = orch._validate_command_against_live_state(
        {"command_type": "send_to_charge", "robot_id": "R-NOPE"}
    )
    assert ok_live is False
    assert orch.invalid_command_rejections >= 1


@pytest.mark.asyncio
async def test_nonblocking_inference_epoch_staleness_and_outcome_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = _make_engine("small", seed=15, robot_count=4)
    orch = MissionOrchestrator(engine=engine, provider_name="ai", rules_dir="rules")
    orch.brain_config.max_decision_staleness_ticks = 3

    async def slow_ai_decide(_brief: SituationBrief, _specs: list[Any]) -> LLMProviderResult:
        await asyncio.sleep(0.05)
        return LLMProviderResult(
            commands=[{"command_type": "no_action", "reason": "ok"}],
            rationale="Delayed LLM output",
            operating_mode="ai",
            provider_name="OpenAI",
            model_name="gpt-4o-mini",
            attribution="AI Mode — OpenAI — gpt-4o-mini",
        )

    monkeypatch.setattr(orch.ai_provider, "decide", slow_ai_decide)

    # Start inference non-blocking on tick 0; sim advances immediately without awaiting slow LLM
    engine.robots[0].blocked_ticks = 20
    d0 = await orch.step_nonblocking(tick=0)
    assert d0 is None
    assert orch._pending_inference is not None

    # Advance 6 simulation ticks quickly while task finishes -> age 6 > limit 3 -> stale discarded!
    await asyncio.sleep(0.07)
    d_late = await orch.step_nonblocking(tick=6)
    assert d_late is not None
    assert orch.stale_decisions_discarded == 1
    assert d_late.governance_outcome == "denied"

    # Also test world_epoch reset invalidation
    d_start = await orch.step_nonblocking(tick=10)
    assert d_start is None
    engine.reset()  # Increments world_epoch
    d_after_reset = await orch.step_nonblocking(tick=1)
    assert d_after_reset is None
    assert orch._pending_inference is None

    # Outcome measurement loop checks actual post-execution delta
    orch.set_provider("heuristic")
    engine.robots[0].blocked_ticks = 16
    dec = await orch.step(tick=20, force_trigger=True)
    assert dec is not None
    # Clear obstacle / unblock robots then evaluate outcome window
    for r in engine.robots:
        r.blocked_ticks = 0
    engine.robots[0].cell = Coordinate(x=1, y=1)
    orch.flush_pending_outcomes(tick=45)
    assert dec.observed_outcome in ("improved", "neutral")
    assert dec.outcome_metrics.get("eval_tick") == 45


@pytest.mark.asyncio
async def test_governance_enforced_identically_for_ai_and_local_llm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = _make_engine("small", seed=21, robot_count=4)
    orch = MissionOrchestrator(engine=engine, provider_name="local_llm", rules_dir="rules")

    # Propose bulk corridor avoidance reroute_robot -> YAML rule command_bulk_reroute_human requires human!
    async def mock_local(_brief: SituationBrief, _specs: list[Any]) -> LLMProviderResult:
        return LLMProviderResult(
            commands=[
                {
                    "command_type": "reroute_robot",
                    "robot_id": engine.robots[0].robot_id,
                    "avoid_cells": [{"x": 5, "y": 5}, {"x": 5, "y": 6}],
                    "reason": "Avoid congested zone",
                }
            ],
            rationale="Detour proposed by local LLM",
            operating_mode="local_llm",
            provider_name="ollama",
            model_name="qwen3.5:4b",
            attribution="Local LLM Mode — Ollama — qwen3.5:4b",
        )

    monkeypatch.setattr(orch.local_provider, "decide", mock_local)
    dec = await orch.step(tick=10, force_trigger=True)
    assert dec is not None
    assert dec.governance_outcome == "require_human"
    assert len(orch.governance.approvals_queue.pending) == 1


def test_fastapi_brain_endpoints_auth_redaction_and_mode_switching(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/api/tags"):
            return httpx.Response(200, json={"models": [{"name": "qwen3.5:4b"}]})
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": "gpt-4o-mini"}]})
        if request.url.path.endswith("/chat/completions"):
            return httpx.Response(200, json={"choices": [{"message": {"content": "OK"}}]})
        return httpx.Response(200, json={})

    _patch_httpx_mock(monkeypatch, handler)
    token = "test-control-token-xyz"
    monkeypatch.setenv("ROBOFLEET_TOKEN", token)
    engine = _make_engine("small", seed=7, robot_count=4)
    pacer = SimulationPacer(engine=engine)
    orch = MissionOrchestrator(engine=engine, provider_name="heuristic", rules_dir="rules")
    app = create_app(engine=engine, pacer=pacer, orchestrator=orch)
    client = TestClient(app)
    auth = {"Authorization": f"Bearer {token}"}

    # Unauthenticated mutation rejected
    unauth = client.post("/api/brain/ai/config", json={"api_key": "sk-unauth-123"})
    assert unauth.status_code in (401, 403)

    # Save Cloud AI config + key
    secret = "sk-live-abcde1234567890"
    res_save = client.post(
        "/api/brain/ai/config",
        headers=auth,
        json={
            "provider_type": "openai",
            "base_url": "https://api.example.test/v1",
            "model": "gpt-4o-mini",
            "api_key": secret,
            "activate": True,
        },
    )
    assert res_save.status_code == 200
    status_body = client.get("/api/brain/status").json()
    assert status_body["mode"] == "ai"
    assert status_body["ai_cloud"]["has_api_key"] is True
    assert secret not in json.dumps(status_body)
    assert secret not in json.dumps(client.get("/api/brain/config").json())
    assert secret not in json.dumps(client.get("/api/config/effective").json())

    # Test Cloud AI connection endpoint
    res_test_ai = client.post("/api/brain/ai/test", headers=auth, json={})
    assert res_test_ai.status_code == 200
    assert res_test_ai.json()["ok"] is True

    # Test Local LLM status & config switch
    res_local_stat = client.get("/api/brain/local/status").json()
    assert res_local_stat["ok"] is True
    assert res_local_stat["recommended_model"] == "qwen3.5:4b"
    assert res_local_stat["recommended_model_installed"] is True

    res_local_cfg = client.post(
        "/api/brain/local/config",
        headers=auth,
        json={"model": "qwen3.5:4b", "activate": True},
    )
    assert res_local_cfg.status_code == 200
    assert client.get("/api/brain/status").json()["mode"] == "local_llm"

    # Backward compatibility: legacy 'anthropic' maps cleanly to 'ai' mode
    res_legacy = client.post("/api/brain/provider", headers=auth, json={"provider": "anthropic"})
    assert res_legacy.status_code == 200
    assert res_legacy.json()["operating_mode"] == "ai"

    # Clear API key removes stored secret cleanly
    client.post("/api/brain/ai/config", headers=auth, json={"clear_api_key": True})
    assert client.get("/api/brain/status").json()["ai_cloud"]["has_api_key"] is False


@pytest.mark.asyncio
async def test_eval_ai_short_run_across_modes(tmp_path: Path) -> None:
    r_base = await run_single_eval_mode("small", "baseline", seed=42, duration_s=5, output_log_dir=tmp_path)
    r_heur = await run_single_eval_mode("small", "heuristic", seed=42, duration_s=5, output_log_dir=tmp_path)
    assert r_base["safety_rejections"] == 0
    assert r_heur["safety_rejections"] == 0
    assert r_base["decisions_count"] == 0
    assert r_heur["decisions_count"] >= 1


@pytest.mark.asyncio
async def test_optional_live_ollama_health_when_daemon_running() -> None:
    """Integration check skipped cleanly if local Ollama daemon is offline."""
    url = os.environ.get("ROBOFLEET_BRAIN__LOCAL__BASE_URL", "http://localhost:11434")
    ollama = OllamaProvider(base_url=url, model="qwen3.5:4b", timeout_s=2.0)
    health = await ollama.check_health(force=True)
    if health.status == "error":
        pytest.skip("Local Ollama daemon is not running on this machine")
    assert isinstance(health.available_models, list)
