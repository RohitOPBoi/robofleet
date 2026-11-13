"""FastAPI application factory and REST endpoints (Phase 2).
Publishes OpenAPI, WebSocket /ws, token-gated control channel, environment disclosure,
and webhook order ingestion.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from typing import Any, Literal

from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    Request,
    Security,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from robofleet.adapters.demand_engine import SyntheticDemandEngine
from robofleet.adapters.webhook import WebhookOrderSource
from robofleet.api.ws import WebSocketManager
from robofleet.contracts.commands import (
    BlockCellsCommand,
    EmergencyStopCommand,
    ResumeCommand,
    UnblockCellsCommand,
)
from robofleet.contracts.common import Coordinate
from robofleet.sim.engine import SimEngine
from robofleet.sim.pacer import SimulationPacer

security = HTTPBearer(auto_error=False)


# Request schemas
class SpeedRequest(BaseModel):
    multiplier: float = Field(ge=0.1, le=20.0, description="Simulation speed multiplier")


class RushRequest(BaseModel):
    multiplier: float = Field(default=2.5, ge=1.0, le=10.0)
    duration_s: int = Field(default=300, ge=10, le=3600)


class OverlayRequest(BaseModel):
    overlay: str = Field(description="Overlay name: rain, match_night, festival, rush")
    multiplier: float | None = None
    duration_s: int | None = None


class EmergencyStopRequest(BaseModel):
    scope: Literal["all", "robot", "zone"] = Field(
        default="all", description="'all', 'robot', or 'zone'"
    )
    target_id: str | None = None


class ResumeEmergencyRequest(BaseModel):
    scope: Literal["all", "robot", "zone"] = Field(
        default="all", description="'all', 'robot', or 'zone'"
    )
    target_id: str | None = None


class BlockCellsRequest(BaseModel):
    cells: list[Coordinate]


class OrderIngestLine(BaseModel):
    sku_id: str
    quantity: int = Field(default=1, ge=1)


class OrderIngestRequest(BaseModel):
    order_id: str
    lines: list[OrderIngestLine]
    priority: int = Field(default=1, ge=1, le=10)
    deadline_tick: int | None = None
    sla_tier: str = "standard"


def create_app(engine: SimEngine, pacer: SimulationPacer) -> FastAPI:
    """Build and configure the FastAPI application."""
    config = engine.config
    ws_manager = WebSocketManager(pacer=pacer)
    pacing_task: asyncio.Task[None] | None = None
    fallback_webhook_sink: WebhookOrderSource | None = None

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        # Startup: start pacer background loop
        nonlocal pacing_task
        pacing_task = asyncio.create_task(pacer.run())
        yield
        # Shutdown: stop pacing and cancel tasks
        pacer.stop()
        if pacing_task:
            pacing_task.cancel()
            with suppress(asyncio.CancelledError):
                await pacing_task

    app = FastAPI(
        title="RoboFleet Live Command Centre API",
        version="1.0.0",
        description="Streaming API and Control Channel for Dark Store Digital Twin",
        lifespan=lifespan,
    )

    # CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.server.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Authentication dependency
    def verify_auth_token(
        request: Request,
        auth: HTTPAuthorizationCredentials | None = Security(security),  # noqa: B008
    ) -> str:
        expected_token = os.environ.get("ROBOFLEET_TOKEN", config.server.auth_token)

        # Check Authorization header
        if auth and auth.credentials and auth.credentials == expected_token:
            return auth.credentials

        # Fallback check query param 'token'
        if request and request.query_params.get("token") == expected_token:
            return str(request.query_params["token"])

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Public Read-Only Endpoints
    @app.get("/health")
    async def get_health() -> dict[str, Any]:
        return {
            "status": "ok",
            "sim_tick": engine.clock.tick,
            "sim_time_ms": engine.clock.sim_time_ms,
            "is_paused": pacer.is_paused,
            "speed_multiplier": pacer.speed_multiplier,
            "mode": "digital_twin",
        }

    @app.get("/api/environment")
    async def get_environment() -> dict[str, Any]:
        """Single disclosure surface (P2-A9)."""
        adapter_name = config.orders.adapter if hasattr(config, "orders") else "demand_engine"
        active_overlays: list[str] = []
        if (
            isinstance(engine.order_source, SyntheticDemandEngine)
            and engine.order_source.active_overlay
        ):
            active_overlays.append(engine.order_source.active_overlay)

        return {
            "mode": "digital_twin",
            "data_source": adapter_name,
            "robot_layer": "simulated",
            "active_adapters": [adapter_name],
            "schema_version": "1.0.0",
            "seed": config.seed,
            "scenario": config.scenario_name,
            "active_overlays": active_overlays,
        }

    @app.get("/api/scenarios")
    async def list_scenarios() -> list[str]:
        return ["small", "standard", "large", "custom"]

    @app.get("/api/config/effective")
    async def get_effective_config() -> dict[str, Any]:
        return config.model_dump()

    @app.get("/api/rules")
    async def get_rules() -> list[dict[str, Any]]:
        return [
            {
                "id": r.id,
                "scope": r.scope,
                "description": r.description,
                "severity": r.severity,
                "effect": r.effect,
                "enabled": r.enabled,
            }
            for r in engine.rule_engine.list_rules()
        ]

    @app.get("/api/runs")
    async def list_runs() -> list[str]:
        from pathlib import Path

        runs_path = Path("runs")
        if not runs_path.exists():
            return []
        return sorted([p.name for p in runs_path.iterdir() if p.is_dir()], reverse=True)

    # Token-Gated Control Channel Endpoints
    @app.post("/api/control/pause", dependencies=[Depends(verify_auth_token)])
    async def control_pause() -> dict[str, Any]:
        pacer.pause()
        return {"status": "paused", "sim_tick": engine.clock.tick}

    @app.post("/api/control/resume", dependencies=[Depends(verify_auth_token)])
    async def control_resume() -> dict[str, Any]:
        pacer.resume()
        return {"status": "resumed", "sim_tick": engine.clock.tick}

    @app.post("/api/control/speed", dependencies=[Depends(verify_auth_token)])
    async def control_speed(req: SpeedRequest) -> dict[str, Any]:
        pacer.set_speed(req.multiplier)
        return {"status": "ok", "speed_multiplier": pacer.speed_multiplier}

    @app.post("/api/control/step", dependencies=[Depends(verify_auth_token)])
    async def control_step() -> dict[str, Any]:
        pacer.step_once()
        return {"status": "stepped", "sim_tick": engine.clock.tick}

    @app.post("/api/control/rush", dependencies=[Depends(verify_auth_token)])
    async def control_rush(req: RushRequest) -> dict[str, Any]:
        if isinstance(engine.order_source, SyntheticDemandEngine):
            engine.order_source.trigger_rush(multiplier=req.multiplier, duration_s=req.duration_s)
            return {
                "status": "rush_triggered",
                "multiplier": req.multiplier,
                "duration_s": req.duration_s,
            }
        return {"status": "ignored", "reason": "Active order adapter is not SyntheticDemandEngine"}

    @app.post("/api/control/overlay/apply", dependencies=[Depends(verify_auth_token)])
    async def control_apply_overlay(req: OverlayRequest) -> dict[str, Any]:
        if isinstance(engine.order_source, SyntheticDemandEngine):
            dur_ticks = int(req.duration_s * engine.clock.tick_hz) if req.duration_s else None
            engine.order_source.apply_overlay(
                name=req.overlay,
                multiplier=req.multiplier,
                duration_ticks=dur_ticks,
            )
            return {"status": "overlay_applied", "overlay": req.overlay}
        return {"status": "ignored", "reason": "Active order adapter is not SyntheticDemandEngine"}

    @app.post("/api/control/overlay/clear", dependencies=[Depends(verify_auth_token)])
    async def control_clear_overlay() -> dict[str, Any]:
        if isinstance(engine.order_source, SyntheticDemandEngine):
            engine.order_source.clear_overlay()
            return {"status": "overlay_cleared"}
        return {"status": "ignored"}

    @app.post("/api/control/emergency_stop", dependencies=[Depends(verify_auth_token)])
    async def control_emergency_stop(req: EmergencyStopRequest) -> dict[str, Any]:
        engine.queue_command(EmergencyStopCommand(scope=req.scope, target_id=req.target_id))
        return {"status": "emergency_stop_queued", "scope": req.scope, "target_id": req.target_id}

    @app.post("/api/control/resume_emergency", dependencies=[Depends(verify_auth_token)])
    async def control_resume_emergency(req: ResumeEmergencyRequest) -> dict[str, Any]:
        engine.queue_command(ResumeCommand(scope=req.scope, target_id=req.target_id))
        return {"status": "resume_queued", "scope": req.scope, "target_id": req.target_id}

    @app.post("/api/control/block_cells", dependencies=[Depends(verify_auth_token)])
    async def control_block_cells(req: BlockCellsRequest) -> dict[str, Any]:
        engine.queue_command(BlockCellsCommand(cells=req.cells))
        return {"status": "block_cells_queued", "cells_count": len(req.cells)}

    @app.post("/api/control/unblock_cells", dependencies=[Depends(verify_auth_token)])
    async def control_unblock_cells(req: BlockCellsRequest) -> dict[str, Any]:
        engine.queue_command(UnblockCellsCommand(cells=req.cells))
        return {"status": "unblock_cells_queued", "cells_count": len(req.cells)}

    # Webhook Order Ingest (CA-2)
    @app.post("/api/ingest/orders", dependencies=[Depends(verify_auth_token)])
    async def ingest_order(req: OrderIngestRequest) -> dict[str, Any]:
        nonlocal fallback_webhook_sink
        webhook_adapter: WebhookOrderSource
        if isinstance(engine.order_source, WebhookOrderSource):
            webhook_adapter = engine.order_source
        else:
            if fallback_webhook_sink is None:
                fallback_webhook_sink = WebhookOrderSource()
            webhook_adapter = fallback_webhook_sink

        try:
            order = webhook_adapter.ingest_order(
                payload=req.model_dump(),
                current_tick=engine.clock.tick,
            )
            # If not primary adapter, push directly into engine orders
            if not isinstance(engine.order_source, WebhookOrderSource):
                engine.orders.append(order)
                engine.orders_received_count += 1
                engine.emit_event(
                    "order.received",
                    {
                        "order_id": order.order_id,
                        "line_count": len(order.lines),
                        "priority": order.priority,
                        "sla_tier": order.sla_tier,
                        "deadline_tick": order.deadline_tick,
                    },
                )
            return {"status": "accepted", "order_id": order.order_id}
        except ValueError as e:
            err_msg = str(e)
            if "Duplicate order_id" in err_msg:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=err_msg) from e
            if "Rate limit" in err_msg:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=err_msg
                ) from e
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg) from e

    # WebSocket Streaming Endpoint
    @app.websocket("/ws")
    async def websocket_endpoint(ws: WebSocket) -> None:
        client_id = f"client-{uuid.uuid4().hex[:8]}"
        session = await ws_manager.connect(ws=ws, client_id=client_id)
        try:
            while True:
                data = await ws.receive_text()
                await ws_manager.handle_client_message(session=session, raw_text=data)
        except WebSocketDisconnect:
            await ws_manager.disconnect(client_id=client_id)
        except Exception:
            await ws_manager.disconnect(client_id=client_id)

    # Mount compiled frontend static files if available
    dist_path = Path("frontend/dist")
    if dist_path.exists():
        from fastapi.staticfiles import StaticFiles

        app.mount("/", StaticFiles(directory=str(dist_path), html=True), name="frontend")

    return app
