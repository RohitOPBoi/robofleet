# RoboFleet Streaming API and WebSocket Protocol Specification (Phase 2)

## 1. Overview

RoboFleet provides a high-throughput, low-latency streaming and supervisory control architecture for dark store digital twin operations. The API layer is implemented with asynchronous FastAPI and Uvicorn, strictly separated from the deterministic simulation core via a wall-clock pacing layer (`SimulationPacer`).

---

## 2. WebSocket Protocol (`/ws`)

### 2.1 Protocol Version & Envelopes
All WebSocket frames are serialized as JSON adhering to version `1.0.0`:
```json
{
  "v": "1.0.0",
  "type": "hello | static_world | snapshot | delta | ping | pong | resync | error",
  "seq": 1042,
  "tick": 450,
  "payload": { ... }
}
```

### 2.2 Connection Handshake Sequence
Upon connection, the server immediately streams three deterministic initialization messages:
1. `hello`: Capabilities, schema version, server timestamps.
2. `static_world`: Fixed layout grid, zones, shelf dimensions, chargers, pick stations, and catalog metadata.
3. `snapshot`: Authoritative world snapshot containing current AMR telemetry, active orders, and alerts.

### 2.3 Delta Streaming (`10 Hz`)
At 10 Hz (configurable via `server.delta_hz`), the server broadcasts coalesced deltas:
- `robots`: Dict mapping `robot_id` to changed coordinates, heading, state, battery percentage, motion progress (`from_coord`, `to_coord`, `progress`).
- `orders`: Dict mapping `order_id` to updated statuses (`RECEIVED`, `QUEUED`, `ASSIGNED`), deadline ticks, and `at_risk` flags.
- `alerts`: Active safety alerts and operational violations.
- `new_events`: Chronological list of events emitted during the pacing interval.
- `kpis`: Instantaneous metrics (throughput/hr, queue depth, fleet utilization, at-risk count).

### 2.4 Gap Detection, Resync, and Ping-Pong
- **Sequence Continuity**: Each client tracks `seq`. If `seq > last_seq + 1`, the client sends `{"type": "resync"}`. The server immediately returns an authoritative snapshot.
- **Backpressure Handling**: Each client connection maintains a bounded 20-message queue. When a slow consumer lags, the oldest unread delta is dropped in favor of the freshest state delta.
- **Heartbeat**: Clients send `{"type": "ping"}`; the server responds immediately with `{"type": "pong", "payload": {"sim_time_ms": ...}}`.

---

## 3. REST API Endpoints

### 3.1 Public Read-Only Endpoints
- `GET /health`: Basic health check, sim tick, paused state, and speed multiplier.
- `GET /api/environment`: **Single disclosure surface (P2-A9)**. Returns execution mode (`digital_twin`), active adapter (`Synthetic Demand Engine`), robot layer (`simulated`), seed, scenario name, and active overlays.
- `GET /api/scenarios`: Returns available scenario presets (`small`, `standard`, `large`).
- `GET /api/config/effective`: Returns full layered configuration.
- `GET /api/rules`: Lists active declarative rules and condition trees.
- `GET /api/runs`: Lists saved deterministic run records.

### 3.2 Token-Gated Control Channel
All state-modifying endpoints require Bearer authentication via header `Authorization: Bearer <ROBOFLEET_TOKEN>` or query parameter `?token=<ROBOFLEET_TOKEN>`:
- `POST /api/control/pause`: Pauses wall-clock simulation loop.
- `POST /api/control/resume`: Resumes wall-clock simulation loop.
- `POST /api/control/speed`: Sets speed multiplier (`0.1x` to `20.0x`). Payload: `{"multiplier": 2.5}`.
- `POST /api/control/step`: Advances simulation by exactly 1 tick.
- `POST /api/control/rush`: Injects high-demand arrival burst. Payload: `{"multiplier": 2.5, "duration_s": 300}`.
- `POST /api/control/overlay/apply`: Applies weather/event demand overlays (`rain`, `match_night`, `festival`).
- `POST /api/control/overlay/clear`: Clears active demand overlay.
- `POST /api/control/emergency_stop`: Executes immediate halt. Scope: `"all"`, `"robot"`, or `"zone"`.
- `POST /api/control/resume_emergency`: Resumes fleet operations after an emergency stop.
- `POST /api/control/block_cells`: Dynamically marks grid cells as obstructed. Payload: `{"cells": [{"x": 10, "y": 8}]}`.
- `POST /api/control/unblock_cells`: Unblocks specified grid cells.
- `POST /api/ingest/orders`: Ingests an external order through the webhook adapter with idempotency and rate limiting.
