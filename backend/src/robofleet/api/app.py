"""FastAPI application factory and REST endpoints (Phase 2).
Publishes OpenAPI, WebSocket /ws, token-gated control channel, environment disclosure,
and webhook order ingestion.
"""

from __future__ import annotations

import asyncio
import os
import time
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
    Response,
    Security,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, ValidationError

from robofleet.adapters.demand_engine import SyntheticDemandEngine
from robofleet.adapters.webhook import WebhookOrderSource
from robofleet.api.ws import WebSocketManager
from robofleet.brain.credentials import PROVIDER_PRESETS, SecretRedactingFilter, resolve_preset
from robofleet.brain.orchestrator import MissionOrchestrator
from robofleet.brain.providers.ai_mode import UnifiedAIProvider
from robofleet.brain.providers.ollama import OllamaProvider
from robofleet.brain.supervisor import SupervisorCommandParser
from robofleet.config.models import AICloudConfig, LocalLLMConfig
from robofleet.contracts.commands import (
    BlockCellsCommand,
    EmergencyStopCommand,
    ResumeCommand,
    ScaleFleetCommand,
    UnblockCellsCommand,
)
from robofleet.contracts.common import Coordinate
from robofleet.sim.engine import SimEngine
from robofleet.sim.pacer import SimulationPacer
from robofleet.sim.recording import RunReplayer

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


class ScaleFleetRequest(BaseModel):
    target_count: int = Field(ge=1, le=100, description="Desired active fleet size")


class OrderIngestLine(BaseModel):
    sku_id: str
    quantity: int = Field(default=1, ge=1)


class OrderIngestRequest(BaseModel):
    order_id: str
    lines: list[OrderIngestLine]
    priority: int = Field(default=1, ge=1, le=10)
    deadline_tick: int | None = None
    sla_tier: str = "standard"


class BrainModeRequest(BaseModel):
    enabled: bool
    mode: Literal["heuristic", "ai", "local_llm", "replay", "baseline"] | None = None


class BrainProviderRequest(BaseModel):
    provider: Literal["heuristic", "ai", "local_llm", "replay", "anthropic", "baseline"]


class AICloudConfigUpdateRequest(BaseModel):
    provider_type: str | None = None
    provider_label: str | None = None
    api_compatibility: Literal["openai_chat", "openai_responses", "anthropic_messages"] | None = None
    base_url: str | None = None
    model: str | None = None
    organization_id: str | None = None
    project_id: str | None = None
    timeout_s: float | None = Field(default=None, ge=1.0, le=180.0)
    max_tokens: int | None = Field(default=None, ge=64, le=8192)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    retry_count: int | None = Field(default=None, ge=0, le=5)
    fallback_policy: Literal["heuristic", "safe_wait"] | None = None
    api_key: str | None = None
    clear_api_key: bool = False
    activate: bool = False


class LocalLLMConfigUpdateRequest(BaseModel):
    base_url: str | None = None
    model: str | None = None
    timeout_s: float | None = Field(default=None, ge=1.0, le=180.0)
    context_length: int | None = Field(default=None, ge=512, le=32768)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=64, le=4096)
    retry_count: int | None = Field(default=None, ge=0, le=5)
    max_concurrency: int | None = Field(default=None, ge=1, le=4)
    fallback_policy: Literal["heuristic", "safe_wait"] | None = None
    activate: bool = False


class BrainApprovalActionRequest(BaseModel):
    action: Literal["approve", "reject"]


class SupervisorCommandRequest(BaseModel):
    query: str
    confirm: bool = False


class ChaosInjectRequest(BaseModel):
    fault_type: str = Field(description="Registered fault type")
    target_id: str = Field(default="system", description="Target robot, aisle, station, bin, or system")
    duration_ticks: int = Field(default=200, ge=1, le=5000)
    severity: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)


class ChaosLoadScenarioRequest(BaseModel):
    scenario_name: str = Field(description="Chaos scenario file name or path")


class ExceptionResolveRequest(BaseModel):
    action: str = Field(description="Action chosen by supervisor")
    actor: str = Field(default="supervisor", description="Supervisor identifier")
    role: Literal["viewer", "supervisor", "admin"] = Field(default="supervisor")
    reason: str = Field(default="Supervisor manual exception resolution")


class ReslotApproveRequest(BaseModel):
    actor: str = Field(default="supervisor")
    role: str = Field(default="supervisor")


class ReplayLoadRequest(BaseModel):
    recording_id: str = Field(default="golden_run_baseline", description="Recording file stem or name")


class ReplaySeekRequest(BaseModel):
    tick: int = Field(default=0, ge=0, description="Target tick to seek")


def create_app(
    engine: SimEngine,
    pacer: SimulationPacer,
    orchestrator: MissionOrchestrator | None = None,
) -> FastAPI:
    """Build and configure the FastAPI application."""
    config = engine.config
    if orchestrator is None:
        rules_dir = getattr(getattr(config, "rules", None), "rules_dir", "rules")
        orchestrator = MissionOrchestrator(engine=engine, rules_dir=rules_dir)

    cred_store = getattr(orchestrator, "credential_store", None)
    if cred_store is not None:
        import logging as _logging

        for _log_name in ("robofleet", "httpx", "httpcore", "uvicorn.error", "uvicorn.access"):
            _logger_obj = _logging.getLogger(_log_name)
            if not any(isinstance(f, SecretRedactingFilter) for f in _logger_obj.filters):
                _logger_obj.addFilter(SecretRedactingFilter(cred_store))

    supervisor_parser = SupervisorCommandParser()
    ws_manager = WebSocketManager(pacer=pacer, orchestrator=orchestrator)
    pacing_task: asyncio.Task[None] | None = None
    fallback_webhook_sink: WebhookOrderSource | None = None
    active_replayer: RunReplayer | None = None
    control_rate_window: list[float] = []

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

    # Security & Size-Limit Middleware (Phase 7 - P7-A5)
    @app.middleware("http")
    async def security_and_limits_middleware(request: Request, call_next: Any) -> Response:
        # Check payload size limit (1MB max body limit)
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > 1_048_576:
            return JSONResponse(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                content={"detail": "Request entity exceeds 1MB limit"},
            )

        # Rate limiting on state-changing paths (/api/control/, /api/chaos/)
        if request.method in ("POST", "PUT", "DELETE") and (
            request.url.path.startswith("/api/control/") or request.url.path.startswith("/api/chaos/")
        ):
            nonlocal control_rate_window
            now = time.monotonic()
            control_rate_window = [t for t in control_rate_window if now - t < 60.0]
            if len(control_rate_window) >= 120:  # 120 requests/minute
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={"detail": "Control channel rate limit exceeded (max 120 calls/min)"},
                )
            control_rate_window.append(now)

        response: Response = await call_next(request)

        # Inject standard security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        if request.url.path in ("/", "/index.html") or request.url.path.endswith(".html"):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response

    # CORS configuration
    cors_origins = config.server.cors_origins
    allow_creds = True
    if "*" in cors_origins:
        allow_creds = False
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=allow_creds,
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

    # Public Health & Liveness Endpoints (P7-A6)
    @app.get("/health")
    @app.get("/healthz")
    async def get_health() -> dict[str, Any]:
        return {
            "status": "ok",
            "healthy": True,
            "sim_tick": engine.clock.tick,
            "sim_time_ms": engine.clock.sim_time_ms,
            "is_paused": pacer.is_paused,
            "speed_multiplier": pacer.speed_multiplier,
            "mode": "recorded_run" if active_replayer else "digital_twin",
        }

    @app.get("/livez")
    async def get_livez() -> dict[str, Any]:
        return {"status": "alive", "tick": engine.clock.tick}

    @app.get("/readyz")
    async def get_readyz() -> dict[str, Any]:
        return {"status": "ready", "ready": True, "active_robots": len(engine.robots)}

    # Prometheus Metrics (Phase 7 - P7-A6)
    @app.get("/metrics")
    async def get_prometheus_metrics() -> Response:
        kpis = engine.get_dynamic_state().kpis
        active_robots = len([r for r in engine.robots if getattr(r.state, "value", str(r.state)) != "EMERGENCY_STOPPED"])
        queue_depth = len(engine.orders)
        th = float(kpis.get("throughput_orders_per_hr", 0.0))
        ticks = engine.clock.tick

        lines = [
            "# HELP robofleet_active_robots Total active AMRs currently in the fleet",
            "# TYPE robofleet_active_robots gauge",
            f"robofleet_active_robots {active_robots}",
            "# HELP robofleet_queue_depth Pending orders queue depth",
            "# TYPE robofleet_queue_depth gauge",
            f"robofleet_queue_depth {queue_depth}",
            "# HELP robofleet_throughput_orders_per_hr Hourly order throughput",
            "# TYPE robofleet_throughput_orders_per_hr gauge",
            f"robofleet_throughput_orders_per_hr {th:.2f}",
            "# HELP robofleet_collisions_total SafetyGuard physical barrier violations",
            "# TYPE robofleet_collisions_total counter",
            "robofleet_collisions_total 0",
            "# HELP robofleet_sim_ticks_total Total simulation ticks executed",
            "# TYPE robofleet_sim_ticks_total counter",
            f"robofleet_sim_ticks_total {ticks}",
        ]
        return Response(content="\n".join(lines) + "\n", media_type="text/plain; version=0.0.4")

    # Diagnostics Endpoint (P7-A6)
    @app.get("/api/diagnostics")
    async def get_diagnostics() -> dict[str, Any]:
        import psutil  # type: ignore[import-untyped]
        import sys
        proc = psutil.Process()
        mem_mb = proc.memory_info().rss / (1024 * 1024)
        return {
            "version": "1.0.0",
            "python_version": sys.version,
            "memory_rss_mb": round(mem_mb, 2),
            "sim_tick": engine.clock.tick,
            "tick_hz": engine.clock.tick_hz,
            "speed_multiplier": pacer.speed_multiplier,
            "is_paused": pacer.is_paused,
            "ai_mode": orchestrator.provider_name if orchestrator and orchestrator.enabled else "baseline",
            "frame_budget_target_ms": 16.67,
            "active_robots": len(engine.robots),
            "replay_active": active_replayer is not None,
        }

    @app.get("/api/environment")
    async def get_environment() -> dict[str, Any]:
        """Single disclosure surface (P2-A9, P7-A3)."""
        if active_replayer is not None:
            return {
                "mode": "recorded_run",
                "data_source": "recording_replay",
                "robot_layer": "simulated",
                "active_adapters": ["recording_replayer"],
                "schema_version": "1.0.0",
                "seed": active_replayer.metadata.get("seed", config.seed),
                "scenario": active_replayer.metadata.get("scenario", config.scenario_name),
                "active_overlays": [],
                "is_replay": True,
                "recording_id": active_replayer.metadata.get("recording_id", "golden_run_baseline"),
            }

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
            "is_replay": False,
        }

    @app.get("/api/scenarios")
    async def list_scenarios() -> list[str]:
        return ["small", "standard", "large", "custom"]

    @app.get("/api/config/effective")
    async def get_effective_config() -> dict[str, Any]:
        dump = config.model_dump()
        if "server" in dump and "auth_token" in dump["server"]:
            dump["server"]["auth_token"] = "[REDACTED]"
        if "brain" in dump:
            status_snapshot = orchestrator.get_status_summary()
            dump["brain"]["cloud"] = {
                **status_snapshot["ai_cloud"],
                "operating_mode": status_snapshot["operating_mode"],
            }
            dump["brain"]["local"] = status_snapshot["local_llm"]
        return dump

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

    @app.post("/api/control/restart", dependencies=[Depends(verify_auth_token)])
    @app.post("/api/control/reset", dependencies=[Depends(verify_auth_token)])
    async def control_restart() -> dict[str, Any]:
        await pacer.restart()
        return {
            "status": "restarted",
            "sim_tick": engine.clock.tick,
            "sim_time_ms": engine.clock.sim_time_ms,
        }

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

    @app.post("/api/control/fleet/scale", dependencies=[Depends(verify_auth_token)])
    async def control_scale_fleet(req: ScaleFleetRequest) -> dict[str, Any]:
        engine.queue_command(ScaleFleetCommand(target_count=req.target_count))
        return {"status": "scale_queued", "target_count": req.target_count}

    @app.get("/api/metrics")
    async def get_metrics() -> dict[str, Any]:
        return engine.get_dynamic_state().kpis

    # Webhook Order Ingest (CA-2)
    @app.post("/api/ingest/orders", dependencies=[Depends(verify_auth_token)])
    @app.post("/api/orders/webhook", dependencies=[Depends(verify_auth_token)])
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

    # Phase 7 Replay & Timeline Scrubbing Endpoints (P7-A3)
    @app.get("/api/replay/recordings")
    async def list_recordings() -> list[dict[str, Any]]:
        recordings_dir = Path("runs/recordings")
        if not recordings_dir.exists():
            return []
        items = []
        for p in sorted(recordings_dir.glob("*.ndjson")):
            try:
                rep = RunReplayer(p)
                info = rep.get_info()
                items.append({
                    "id": p.stem,
                    "filename": p.name,
                    "size_bytes": p.stat().st_size,
                    "total_ticks": info["total_ticks"],
                    "duration_s": info["duration_s"],
                    "bookmarks_count": len(info["bookmarks"]),
                    "scenario": info["scenario"],
                })
            except Exception:
                items.append({"id": p.stem, "filename": p.name, "size_bytes": p.stat().st_size})
        return items

    @app.post("/api/replay/load", dependencies=[Depends(verify_auth_token)])
    async def load_recording(req: ReplayLoadRequest) -> dict[str, Any]:
        nonlocal active_replayer
        clean_id = Path(req.recording_id).name
        if clean_id.endswith(".ndjson"):
            clean_id = clean_id[:-7]
        p = (Path("runs/recordings") / f"{clean_id}.ndjson").resolve()
        base_dir = Path("runs/recordings").resolve()
        if not p.is_relative_to(base_dir) or not p.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Recording '{req.recording_id}' not found",
            )
        active_replayer = RunReplayer(p)
        pacer.pause()
        info = active_replayer.get_info()
        initial_state = active_replayer.seek(0)
        return {
            "status": "recording_loaded",
            "info": info,
            "initial_state": initial_state,
        }

    @app.post("/api/replay/seek", dependencies=[Depends(verify_auth_token)])
    async def seek_recording(req: ReplaySeekRequest) -> dict[str, Any]:
        if active_replayer is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No active recording loaded. Call /api/replay/load first.",
            )
        state = active_replayer.seek(req.tick)
        return {
            "status": "seek_complete",
            "tick": active_replayer.current_tick,
            "state": state,
        }

    @app.post("/api/replay/step", dependencies=[Depends(verify_auth_token)])
    async def step_recording() -> dict[str, Any]:
        if active_replayer is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No active recording loaded.",
            )
        state = active_replayer.step()
        return {
            "status": "stepped",
            "tick": active_replayer.current_tick,
            "state": state,
        }

    @app.post("/api/replay/exit", dependencies=[Depends(verify_auth_token)])
    async def exit_recording() -> dict[str, Any]:
        nonlocal active_replayer
        active_replayer = None
        return {"status": "replay_exited", "mode": "digital_twin"}

    @app.get("/api/replay/state")
    async def get_replay_state() -> dict[str, Any]:
        if active_replayer is None:
            return {"active": False}
        return {
            "active": True,
            "tick": active_replayer.current_tick,
            "info": active_replayer.get_info(),
            "state": active_replayer.seek(active_replayer.current_tick),
        }

    # AI Operations Brain Endpoints (Phase 5)
    @app.get("/api/brain/status")
    async def get_brain_status() -> dict[str, Any]:
        summary = orchestrator.get_status_summary()
        summary["circuit_breaker_tripped"] = summary.get("circuit_tripped", False)
        summary["pending_approvals_count"] = summary.get("approvals_pending", 0)
        return summary

    @app.post("/api/brain/mode", dependencies=[Depends(verify_auth_token)])
    async def set_brain_mode(req: BrainModeRequest) -> dict[str, Any]:
        if req.mode:
            try:
                orchestrator.set_provider(req.mode)
            except ValueError as exc:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        orchestrator.set_mode(req.enabled)
        summary = orchestrator.get_status_summary()
        return {"status": "ok", **summary}

    @app.post("/api/brain/provider", dependencies=[Depends(verify_auth_token)])
    async def set_brain_provider(req: BrainProviderRequest) -> dict[str, Any]:
        try:
            orchestrator.set_provider(req.provider)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        summary = orchestrator.get_status_summary()
        return {"status": "ok", **summary}

    @app.get("/api/brain/config")
    async def get_brain_config() -> dict[str, Any]:
        summary = orchestrator.get_status_summary()
        return {
            "enabled": summary["enabled"],
            "mode": summary["mode"],
            "operating_mode": summary["operating_mode"],
            "ai_cloud": summary["ai_cloud"],
            "local_llm": summary["local_llm"],
            "presets": [
                {
                    "id": p.id,
                    "provider_type": p.provider_type,
                    "label": p.label,
                    "api_compatibility": p.api_compatibility,
                    "default_base_url": p.default_base_url,
                    "default_model": p.default_model,
                    "suggested_models": list(p.suggested_models),
                    "env_vars": list(p.env_var_names),
                }
                for p in PROVIDER_PRESETS.values()
            ],
        }

    def _merge_cloud_config(req: AICloudConfigUpdateRequest) -> AICloudConfig:
        merged = orchestrator.brain_config.cloud.model_dump()
        updates = req.model_dump(
            exclude={"api_key", "clear_api_key", "activate"}, exclude_none=True
        )
        raw_pt = updates.get("provider_type")
        if raw_pt and raw_pt in PROVIDER_PRESETS:
            preset = PROVIDER_PRESETS[raw_pt]
            updates["provider_type"] = preset.provider_type
            updates.setdefault("provider_label", preset.label)
            updates.setdefault("api_compatibility", preset.api_compatibility)
            updates.setdefault("base_url", preset.default_base_url)
            if not updates.get("model"):
                updates["model"] = preset.default_model
        elif raw_pt and raw_pt != merged.get("provider_type"):
            preset = resolve_preset(raw_pt)
            updates.setdefault("provider_label", preset.label)
            updates.setdefault("api_compatibility", preset.api_compatibility)
            updates.setdefault("base_url", preset.default_base_url)
            if not updates.get("model"):
                updates["model"] = preset.default_model
        merged.update(updates)
        return AICloudConfig.model_validate(merged)

    @app.post("/api/brain/ai/config", dependencies=[Depends(verify_auth_token)])
    async def update_ai_config(req: AICloudConfigUpdateRequest) -> dict[str, Any]:
        try:
            new_cfg = _merge_cloud_config(req)
        except ValidationError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

        orchestrator.update_ai_cloud_config(
            new_cfg,
            api_key=req.api_key,
            clear_api_key=req.clear_api_key,
        )
        if req.activate:
            orchestrator.set_provider("ai")
        return {"status": "ok", "brain_status": orchestrator.get_status_summary()}

    @app.post("/api/brain/ai/test", dependencies=[Depends(verify_auth_token)])
    async def test_ai_connection(req: AICloudConfigUpdateRequest | None = None) -> dict[str, Any]:
        from robofleet.brain.credentials import SecretCredentialStore

        req_obj = req or AICloudConfigUpdateRequest()
        try:
            probe_cfg = _merge_cloud_config(req_obj)
        except ValidationError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

        probe_store = SecretCredentialStore()
        probe_provider = UnifiedAIProvider(cloud_config=probe_cfg, credential_store=probe_store)
        profile_keys = {
            probe_cfg.provider_type.strip().lower(),
            probe_provider.current_profile_key,
        }
        existing_key = ""
        for k in (
            orchestrator.ai_provider.current_profile_key,
            orchestrator.brain_config.cloud.provider_type.strip().lower(),
            *profile_keys,
        ):
            existing_key = orchestrator.credential_store.get_key(k)
            if existing_key:
                break

        secret_to_use = (
            req_obj.api_key.strip()
            if req_obj.api_key and req_obj.api_key.strip()
            else ("" if req_obj.clear_api_key else existing_key)
        )
        if secret_to_use:
            for k in profile_keys:
                probe_store.set_key(k, secret_to_use)
        health = await probe_provider.test_connection()
        orchestrator.ai_provider.last_health_status = health

        adapter = probe_provider.get_active_adapter()
        models = list(health.available_models)
        if health.ok and not models and hasattr(adapter, "list_models"):
            listed = await adapter.list_models()
            if isinstance(listed, list):
                models = listed
            elif isinstance(listed, tuple) and len(listed) >= 2 and listed[0]:
                models = list(listed[1])

        safe_msg = probe_store.redact(orchestrator.credential_store.redact(health.message))
        return {
            "ok": health.ok,
            "status": health.status,
            "provider": health.provider_name,
            "model": health.model_name,
            "latency_ms": health.latency_ms,
            "message": safe_msg,
            "available_models": models,
        }

    @app.get("/api/brain/local/status")
    async def get_local_llm_status() -> dict[str, Any]:
        health = await orchestrator.local_provider.check_health(force=True)
        models = list(health.available_models)
        recommended = "qwen3.5:4b"
        summary = orchestrator.get_status_summary()["local_llm"]
        return {
            "ok": health.ok,
            "status": health.status,
            "message": health.message,
            "latency_ms": health.latency_ms,
            "installed_models": models,
            "recommended_model": recommended,
            "recommended_model_installed": any(recommended in m for m in models),
            "local_llm": summary,
        }

    @app.post("/api/brain/local/config", dependencies=[Depends(verify_auth_token)])
    async def update_local_config(req: LocalLLMConfigUpdateRequest) -> dict[str, Any]:
        updates = req.model_dump(exclude={"activate"}, exclude_none=True)
        try:
            merged = {**orchestrator.brain_config.local.model_dump(), **updates}
            cfg_obj = LocalLLMConfig.model_validate(merged)
        except ValidationError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

        orchestrator.update_local_llm_config(cfg_obj)
        if req.activate:
            orchestrator.set_provider("local_llm")
        return {"status": "ok", "brain_status": orchestrator.get_status_summary()}

    @app.post("/api/brain/local/test", dependencies=[Depends(verify_auth_token)])
    async def test_local_connection(req: LocalLLMConfigUpdateRequest | None = None) -> dict[str, Any]:
        req_obj = req or LocalLLMConfigUpdateRequest()
        updates = req_obj.model_dump(exclude={"activate"}, exclude_none=True)
        merged = {**orchestrator.brain_config.local.model_dump(), **updates}
        try:
            cfg_obj = LocalLLMConfig.model_validate(merged)
        except ValidationError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

        probe_ollama = OllamaProvider()
        probe_ollama.apply_config(cfg_obj)
        health = await probe_ollama.check_health(force=True)
        if req is None or not updates:
            orchestrator.local_provider.last_health_status = health
        models = list(health.available_models)
        return {
            "ok": health.ok,
            "status": health.status,
            "provider": health.provider_name,
            "model": health.model_name,
            "latency_ms": health.latency_ms,
            "message": health.message,
            "available_models": models,
            "recommended_model": "qwen3.5:4b",
            "recommended_model_installed": any("qwen3.5:4b" in m for m in models),
        }

    @app.get("/api/brain/metrics")
    async def get_brain_metrics() -> dict[str, Any]:
        current_tick = engine.clock.tick
        return {
            **orchestrator.get_operational_metrics(),
            "deadlocks": [d.model_dump() for d in orchestrator._get_deadlocks(current_tick)],
        }

    @app.get("/api/brain/decisions")
    async def get_brain_decisions(limit: int = 50) -> list[dict[str, Any]]:
        return [d.model_dump() for d in orchestrator.decisions[-limit:]]

    @app.get("/api/brain/approvals")
    async def get_brain_approvals() -> list[dict[str, Any]]:
        return [a.model_dump() for a in orchestrator.governance.approvals_queue.pending.values()]

    @app.post("/api/brain/approvals/{request_id}", dependencies=[Depends(verify_auth_token)])
    async def act_on_approval(request_id: str, req: BrainApprovalActionRequest) -> dict[str, Any]:
        queue = orchestrator.governance.approvals_queue
        if request_id not in queue.pending:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Approval request not found or expired",
            )
        if req.action == "approve":
            cmd = queue.resolve(request_id, approve=True)
            if cmd:
                orchestrator._execute_command(cmd, engine.clock.tick)
            return {"status": "approved", "request_id": request_id}
        else:
            queue.resolve(request_id, approve=False)
            return {"status": "rejected", "request_id": request_id}

    @app.post("/api/brain/supervisor/command", dependencies=[Depends(verify_auth_token)])
    async def supervisor_command(req: SupervisorCommandRequest) -> dict[str, Any]:
        recent_ids = [d.decision_id for d in orchestrator.decisions[-5:]]
        brief = orchestrator.brief_builder.build(
            tick=engine.clock.tick,
            trigger="supervisor_query",
            engine=engine,
            recent_decision_ids=recent_ids,
            held_zone_ids=list(orchestrator.held_zones),
        )
        parsed = supervisor_parser.parse(
            text=req.query,
            current_tick=engine.clock.tick,
            brief=brief,
            engine=engine,
        )
        if req.confirm and parsed.parsed_command:
            try:
                orchestrator._execute_command(parsed.parsed_command, engine.clock.tick)
                parsed.response_text += " [Executed successfully]"
            except Exception as e:
                parsed.response_text += f" [Execution failed: {e}]"
        return parsed.model_dump()

    # Phase 6 Chaos, Resilience, Exceptions and Audit Endpoints
    @app.post("/api/chaos/inject", dependencies=[Depends(verify_auth_token)])
    async def inject_chaos_fault(req: ChaosInjectRequest) -> dict[str, Any]:
        fault = engine.chaos_engine.inject_fault(
            fault_type=req.fault_type,
            target_id=req.target_id,
            duration_ticks=req.duration_ticks,
            severity=req.severity,
            params=req.params,
            tick=engine.clock.tick,
        )
        return {"status": "injected", "fault": fault.to_contract().model_dump()}

    @app.post("/api/chaos/perfect_storm", dependencies=[Depends(verify_auth_token)])
    async def inject_perfect_storm() -> dict[str, Any]:
        faults = engine.chaos_engine.inject_perfect_storm(tick=engine.clock.tick)
        return {
            "status": "perfect_storm_injected",
            "faults": [f.to_contract().model_dump() for f in faults],
        }

    @app.post("/api/chaos/clear", dependencies=[Depends(verify_auth_token)])
    async def clear_chaos_faults() -> dict[str, Any]:
        count = engine.chaos_engine.clear_and_heal_all(tick=engine.clock.tick)
        return {"status": "cleared", "healed_count": count}

    @app.get("/api/chaos/status")
    async def get_chaos_status() -> dict[str, Any]:
        return {
            "active_faults": [f.to_contract().model_dump() for f in engine.chaos_engine.active_faults],
            "degraded_modes": [m.model_dump() for m in engine.chaos_engine.get_active_degraded_modes()],
            "mttr_by_type": engine.chaos_engine.get_mttr_by_type(),
            "scheduled_faults_count": len(engine.chaos_engine.scheduled_faults),
            "total_incidents_count": engine.chaos_engine.total_incidents_count,
        }

    @app.get("/api/chaos/scenarios")
    async def list_chaos_scenarios() -> list[str]:
        scenarios_dir = Path("scenarios/chaos")
        if not scenarios_dir.exists():
            return []
        return sorted([f.stem for f in scenarios_dir.glob("*.yaml")])

    @app.post("/api/chaos/load_scenario", dependencies=[Depends(verify_auth_token)])
    async def load_chaos_scenario(req: ChaosLoadScenarioRequest) -> dict[str, Any]:
        clean_name = Path(req.scenario_name).name
        if clean_name.endswith(".yaml"):
            clean_name = clean_name[:-5]
        target_path = (Path("scenarios/chaos") / f"{clean_name}.yaml").resolve()
        base_dir = Path("scenarios/chaos").resolve()
        if not target_path.is_relative_to(base_dir) or not target_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Chaos scenario '{req.scenario_name}' not found",
            )
        engine.chaos_engine.load_chaos_scenario(target_path, current_tick=engine.clock.tick)
        return {"status": "scenario_loaded", "scenario": clean_name}

    @app.get("/api/exceptions")
    async def get_exceptions() -> dict[str, Any]:
        return {
            "pending_exceptions": [e.model_dump() for e in engine.exceptions_queue.pending_exceptions.values()],
            "history_count": len(engine.exceptions_queue.history_exceptions),
            "human_interventions_count": engine.exceptions_queue.total_human_interventions,
            "human_interventions_per_100_orders": engine.exceptions_queue.compute_human_interventions_per_100_orders(len(engine.orders)),
            "average_queue_age_ticks": engine.exceptions_queue.get_queue_average_age_ticks(engine.clock.tick),
        }

    @app.post("/api/exceptions/{exception_id}/resolve", dependencies=[Depends(verify_auth_token)])
    async def resolve_exception(exception_id: str, req: ExceptionResolveRequest) -> dict[str, Any]:
        ok, msg = engine.exceptions_queue.resolve_exception(
            exception_id=exception_id,
            action=req.action,
            actor=req.actor,
            role=req.role,
            reason=req.reason,
            current_tick=engine.clock.tick,
        )
        if not ok:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)
        return {"status": "resolved", "exception_id": exception_id, "detail": msg}

    @app.get("/api/audit/logs")
    async def get_audit_logs(
        role: str | None = None,
        actor: str | None = None,
        action: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        return engine.audit_db.query_logs(role=role, actor=actor, action=action, limit=limit)

    @app.get("/api/audit/export.csv")
    async def export_audit_csv() -> Any:
        from fastapi.responses import Response

        csv_content = engine.audit_db.export_csv()
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=audit_ledger.csv"},
        )

    @app.get("/api/reslot/recommendations")
    async def get_reslot_recommendations() -> list[dict[str, Any]]:
        return [r.model_dump() for r in engine.reslot_recommender.recommendations]

    @app.post("/api/reslot/{recommendation_id}/approve", dependencies=[Depends(verify_auth_token)])
    async def approve_reslot_recommendation(recommendation_id: str, req: ReslotApproveRequest) -> dict[str, Any]:
        ok, msg = engine.reslot_recommender.approve_recommendation(
            recommendation_id=recommendation_id,
            actor=req.actor,
            role=req.role,
            current_tick=engine.clock.tick,
        )
        if not ok:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)
        return {"status": "approved", "recommendation_id": recommendation_id, "detail": msg}

    # WebSocket Streaming Endpoint
    @app.websocket("/ws")
    async def websocket_endpoint(ws: WebSocket) -> None:
        token = ws.query_params.get("token") or ws.headers.get("authorization", "").replace("Bearer ", "")
        expected_token = os.environ.get("ROBOFLEET_TOKEN", config.server.auth_token)
        if token and token != expected_token:
            await ws.close(code=4001, reason="Unauthorized")
            return
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
