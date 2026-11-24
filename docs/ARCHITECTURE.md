# RoboFleet Architecture — Phase 1, 2, 3, 4 & 5: Streaming Core, 3D Twin & AI Operations Brain

## 1. System Overview & Boundaries

RoboFleet combines a deterministic simulation core with an asynchronous streaming API, an order-to-dispatch operations fleet engine, a high-fidelity 3D digital twin, and an AI Operations Brain:
- **Headless Core (`robofleet.sim`)**: Strictly synchronous, discrete-event simulation engine with a non-bypassable safety boundary (`SafetyGuard`), deterministic RNG stream hierarchy, declarative YAML rule engine, and slotting logic.
- **Fleet Fulfilment & Station Operations Engine (`robofleet.fleet`)**: Multi-step task lifecycle manager (`TaskManager`), bounded pick station queues with item handling difficulty multipliers (`PickingStationManager`), courier dispatch bay with Poisson rider arrivals (`DispatchBayManager`), and exact WareMax delay attribution decomposition.
- **Space-Time Reservation Planner (`ReservationAStarPlanner`, CA-5)**: Cooperative space-time A* maintaining a rolling vertex/edge reservation table and wait-for graph cycle resolution.
- **Baseline Strategy Dispatchers (`robofleet.fleet.strategies`, CA-5)**: Four pluggable dispatchers (`fcfs_nearest`, `edf_deadline`, `batch_greedy`, `random`) registered in `strategy_registry`.
- **AI Operations Brain (`robofleet.brain`, CA-6, Phase 5)**: Mission Orchestrator coordinating 4 specialists (`Planner`, `Traffic & Fleet`, `Exceptions & Recovery`, `Explainer`), evaluated behind a declarative `GovernanceLayer` (CA-3), backed by an `LLMProvider` Port with automatic circuit breaker and 1-tick heuristic failover.
- **Wall-Clock Pacing Layer (`SimulationPacer`)**: Lives outside the core. Converts discrete ticks to real-time execution with configurable speed multipliers (`0.1x` to `20x`), pause/resume, and single-step capabilities.
- **Streaming & Control Layer (`robofleet.api`)**: Asynchronous FastAPI server publishing OpenAPI, WebSocket `/ws` at 10 Hz with coalesced backpressure, token-gated control endpoints (`/api/control/*`), brain endpoints (`/api/brain/*`), runtime fleet scaling (`/api/control/fleet/scale`), and webhook order ingest.
- **Operations Command Centre (`frontend/`)**: React + Three.js + Vite + TypeScript command centre with 2D Canvas Map, high-performance 3D WebGL digital twin, Decision Log panel, Human-in-the-loop Approvals drawer, and Natural Language Supervisor Command Bar.

```
+-------------------------------------------------------------------------+
|                  RoboFleet Live Command Centre (UI)                     |
|  [TopBar KPIs] [2D/3D Map (60fps)] [Decision Log] [Approvals] [NL Bar]  |
+------------------------------------+------------------------------------+
                                     |
                         HTTP REST / WebSocket /ws
                                     |
+------------------------------------v------------------------------------+
|                         FastAPI & Uvicorn API                           |
|       /api/environment   /api/control/*   /api/brain/* (Token)          |
+------------------------------------+------------------------------------+
                                     |
+------------------------------------v------------------------------------+
|                      SimulationPacer (Wall-Clock)                       |
|          speed_multiplier (0.1x-20x) | pause/resume | step_once         |
+------------------------------------+------------------------------------+
                                     |
+------------------------------------v------------------------------------+
|                      AI Mission Orchestrator (CA-6)                     |
|   BriefBuilder -> Specialists (Planner/Traffic/Exceptions/Explainer)    |
|   GovernanceLayer (CA-3) -> ApprovalsQueue -> Explainer Fact Verifier   |
+------------------------------------+------------------------------------+
                                     |
+------------------------------------v------------------------------------+
|                  SimEngine (Deterministic Tick Loop)                    |
|   Step 1: Commands      Step 4: Dispatcher     Step 7: Physical State   |
|   Step 2: AI Execution  Step 5: Planner        Step 8: Rules / Alerts   |
|   Step 3: Orders        Step 6: SafetyGuard    Step 9: Events & Advance |
+-------------------------------------------------------------------------+
```

---

## 2. Pacing & Concurrency Model

1. **Isolation**: The core `SimEngine` has zero knowledge of asyncio, websockets, or network requests.
2. **Step Invocation**: `SimulationPacer` schedules `engine.step()` inside an asyncio worker task, calculates elapsed wall-clock time, and regulates sleep intervals:
   $$\Delta t_{\text{sleep}} = \frac{1}{\text{tick\_hz} \times \text{speed\_multiplier}}$$
3. **Control Translation**: All supervisory actions from `/api/control/*` and approved AI decisions from `/api/brain/*` are mapped to typed `CommandUnion` objects and queued for atomic execution during Step 1 of the next simulation tick.

---

## 3. WebSocket Envelope Contract (`/ws`)

Every frame carries version, type, sequence number, tick, and payload:
```json
{
  "v": "1.0.0",
  "type": "hello | static_world | snapshot | delta | ping | pong | resync | error",
  "seq": 450,
  "tick": 450,
  "payload": { ... }
}
```
Clients detect sequence continuity. If $\text{seq}_{\text{in}} > \text{seq}_{\text{last}} + 1$, the client requests `{"type": "resync"}`.
Slow clients receive coalesced deltas via a bounded outbound queue (20 items max), eliminating memory bloat.

---

## 4. Phase 5 AI Operations Brain & Governance Architecture

1. **Specialist Consolidation**: Exactly 1 Mission Orchestrator coordinates 4 specialized roles:
   - `PlannerSpecialist`: order prioritization & pick load balancing.
   - `TrafficFleetSpecialist`: AMR charging & junction congestion bypass.
   - `ExceptionsRecoverySpecialist`: zone isolation & human escalation.
   - `ExplainerSpecialist`: grounded plain-language rationale synthesis.
2. **Deterministic Situation Brief**: Extracts bounded operational summary from live state, hashed via SHA256. Zero unbounded prompt injection.
3. **Governance Seam (CA-3)**: All AI actions are typed commands (`BrainBaseCommand`) evaluated against declarative YAML rules in `rules/`. Commands can be approved, denied, or queued for human approval.
4. **Anti-Hallucination Gate**: Explainer strictly verifies all referenced entity IDs against the brief before emission.
5. **Failover Invariant**: LLM errors or network drops instantly trigger the fast deterministic heuristic baseline within one simulation tick ($< 1$ms).
