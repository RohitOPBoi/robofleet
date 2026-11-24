"""WebSocket /ws protocol and connection manager (Phase 2).
Enforces envelope versioning, handshake lifecycle (hello -> static_world -> snapshot -> delta),
coalesced backpressure, and resync/ping protocol handling.
"""

from __future__ import annotations

import asyncio
import json
from contextlib import suppress
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

from robofleet.contracts.events import Event
from robofleet.contracts.state import DynamicState
from robofleet.sim.pacer import SimulationPacer


class WebSocketClientSession:
    """Represents a connected client with an active coalesced delta queue."""

    def __init__(self, ws: WebSocket, client_id: str) -> None:
        self.ws = ws
        self.client_id = client_id
        self.last_seq: int = 0
        self._pending_delta: dict[str, Any] | None = None
        self._queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=20)

    async def send_envelope(
        self,
        envelope_type: str,
        payload: dict[str, Any],
        seq: int,
        tick: int,
        version: str = "1.0.0",
    ) -> None:
        message = {
            "v": version,
            "type": envelope_type,
            "seq": seq,
            "tick": tick,
            "payload": payload,
        }
        await self.ws.send_text(json.dumps(message))

    async def enqueue_delta(self, delta_payload: dict[str, Any], seq: int, tick: int) -> None:
        message = {
            "v": "1.0.0",
            "type": "delta",
            "seq": seq,
            "tick": tick,
            "payload": delta_payload,
        }
        # Backpressure handling: if queue is full, drop oldest delta (coalescing to newest state)
        if self._queue.full():
            with suppress(asyncio.QueueEmpty):
                self._queue.get_nowait()
        await self._queue.put(message)

    async def send_worker(self) -> None:
        """Worker task draining the queue to the client WebSocket."""
        try:
            while True:
                msg = await self._queue.get()
                await self.ws.send_text(json.dumps(msg))
                self.last_seq = msg.get("seq", self.last_seq)
        except (WebSocketDisconnect, asyncio.CancelledError):
            pass


class WebSocketManager:
    """Manages active WebSocket connections and broadcasting."""

    def __init__(self, pacer: SimulationPacer, orchestrator: Any = None) -> None:
        self.pacer = pacer
        self.engine = pacer.engine
        self.orchestrator = orchestrator
        self._clients: dict[str, WebSocketClientSession] = {}
        self._client_tasks: dict[str, asyncio.Task[None]] = {}
        self._lock = asyncio.Lock()

        # Hook into pacer step callback
        self.pacer.register_callback(self.on_sim_step)

    async def connect(self, ws: WebSocket, client_id: str) -> WebSocketClientSession:
        await ws.accept()
        session = WebSocketClientSession(ws=ws, client_id=client_id)

        async with self._lock:
            self._clients[client_id] = session
            task = asyncio.create_task(session.send_worker())
            self._client_tasks[client_id] = task

        # Handshake Phase 1: hello
        await session.send_envelope(
            envelope_type="hello",
            payload={
                "schema_version": "1.0.0",
                "server_capabilities": [
                    "pacing",
                    "control",
                    "overlays",
                    "webhooks",
                    "delta_streaming",
                ],
                "feature_flags": {
                    "e_stop": True,
                    "block_cells": True,
                    "rush": True,
                },
            },
            seq=0,
            tick=self.engine.clock.tick,
        )

        # Handshake Phase 2: static_world
        static_world = self.engine.get_static_world()
        await session.send_envelope(
            envelope_type="static_world",
            payload=static_world.model_dump(),
            seq=self.engine.seq,
            tick=self.engine.clock.tick,
        )

        # Handshake Phase 3: full snapshot
        dynamic_state = self.engine.get_dynamic_state()
        await session.send_envelope(
            envelope_type="snapshot",
            payload=dynamic_state.model_dump(),
            seq=self.engine.seq,
            tick=self.engine.clock.tick,
        )

        return session

    async def disconnect(self, client_id: str) -> None:
        async with self._lock:
            if client_id in self._client_tasks:
                self._client_tasks[client_id].cancel()
                del self._client_tasks[client_id]
            if client_id in self._clients:
                del self._clients[client_id]

    async def handle_client_message(self, session: WebSocketClientSession, raw_text: str) -> None:
        """Handle incoming messages from client (ping, resync)."""
        try:
            data = json.loads(raw_text)
            msg_type = data.get("type")

            if msg_type == "ping":
                await session.send_envelope(
                    envelope_type="pong",
                    payload={"sim_time_ms": self.engine.clock.sim_time_ms},
                    seq=self.engine.seq,
                    tick=self.engine.clock.tick,
                )
            elif msg_type == "resync":
                # Client detected seq gap or requested fresh state
                dynamic_state = self.engine.get_dynamic_state()
                await session.send_envelope(
                    envelope_type="snapshot",
                    payload=dynamic_state.model_dump(),
                    seq=self.engine.seq,
                    tick=self.engine.clock.tick,
                )
        except json.JSONDecodeError:
            pass

    async def on_sim_step(self, dynamic_state: DynamicState, recent_events: list[Event]) -> None:
        """Broadcasts delta message to all connected clients."""
        recent_decision = None
        if self.orchestrator and getattr(self.orchestrator, "enabled", False):
            recent_decision = await self.orchestrator.step(dynamic_state.tick)

        delta_payload: dict[str, Any] = {
            "sim_time_ms": self.engine.clock.sim_time_ms,
            "tick": dynamic_state.tick,
            "robots": [r.model_dump() for r in dynamic_state.robots],
            "orders": [o.model_dump() for o in dynamic_state.orders],
            "alerts": [a.model_dump() for a in dynamic_state.alerts],
            "blocked_cells": [c.model_dump() for c in dynamic_state.blocked_cells],
            "kpis": dynamic_state.kpis,
            "events": [e.model_dump() for e in recent_events],
        }

        # Phase 6 Resilience Telemetry
        if hasattr(self.engine, "chaos_engine"):
            delta_payload["degraded_modes"] = [
                m.model_dump() for m in self.engine.chaos_engine.get_active_degraded_modes()
            ]
            delta_payload["active_faults_count"] = len(self.engine.chaos_engine.active_faults)
        if hasattr(self.engine, "exceptions_queue"):
            delta_payload["pending_exceptions"] = [
                e.model_dump() for e in self.engine.exceptions_queue.pending_exceptions.values()
            ]
            delta_payload["exceptions_count"] = len(self.engine.exceptions_queue.pending_exceptions)
        if hasattr(self.engine, "reslot_recommender"):
            delta_payload["reslot_recommendations"] = [
                r.model_dump() for r in self.engine.reslot_recommender.recommendations
            ]

        if self.orchestrator:
            approvals = list(self.orchestrator.governance.approvals_queue.pending.values())
            delta_payload["brain_status"] = {
                "ai_mode": "ai" if self.orchestrator.enabled else "baseline",
                "provider_status": getattr(self.orchestrator, "provider_name", "heuristic"),
                "decisions_count": len(getattr(self.orchestrator, "decisions", [])),
                "pending_approvals_count": len(approvals),
                "total_cost_usd": getattr(
                    getattr(self.orchestrator, "anthropic_provider", None),
                    "total_cost_usd",
                    0.0,
                ),
            }
            delta_payload["pending_approvals"] = [a.model_dump() for a in approvals]
            if recent_decision:
                delta_payload["recent_decision"] = recent_decision.model_dump()

        async with self._lock:
            for session in list(self._clients.values()):
                await session.enqueue_delta(
                    delta_payload=delta_payload,
                    seq=dynamic_state.seq,
                    tick=dynamic_state.tick,
                )
