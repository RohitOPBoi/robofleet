# RoboFleet Architecture — Phase 1: Dynamic Core

## 1. System Overview & Boundaries

RoboFleet Phase 1 is a headless, discrete-event digital twin of a robot-assisted quick-commerce metro dark store. It provides a deterministic simulation core, declarative rule engine, non-bypassable safety boundary, layered configuration, and realistic Indian grocery catalogue.

```
                           +------------------------+
                           |  CLI & Runner Tooling  |
                           +-----------+------------+
                                       |
                +----------------------+----------------------+
                |                      |                      |
     +----------v----------+ +---------v----------+ +---------v----------+
     |   Layered Config    | |  Declared Registry | |  YAML Rule Engine  |
     | (defaults/scenario) | | (planners/dispatch)| | (placement/alerts) |
     +----------+----------+ +---------+----------+ +---------+----------+
                |                      |                      |
                +----------------------+----------------------+
                                       |
                           +-----------v------------+
                           |   Simulation Engine    |
                           |   (Discrete Ticks)     |
                           +-----------+------------+
                                       |
         +-----------------------------+-----------------------------+
         |                             |                             |
+--------v---------+          +--------v---------+          +--------v---------+
|  World / Layout  |          |   SafetyGuard    |          | Contract Payloads|
| (Graph & Bins)   |          | (Exclusive Mover)|          | (Snapshot/Events)|
+------------------+          +------------------+          +------------------+
```

---

## 2. The 9-Step Tick Contract

Every simulation tick advances logical time by an integer count (`tick_hz = 10`, 100ms per tick). The tick loop executes in strict chronological order:

1. **Apply Queued Commands:** Process external inputs (`emergency_stop`, `resume`, `block_cells`, `unblock_cells`, `inject_fault`, `clear_fault`).
2. **Brain Step:** Invokes active `Brain` protocol implementation (null placeholder in Phase 1).
3. **Order Source Step:** Invokes active `OrderSource` protocol implementation (null placeholder in Phase 1).
4. **Dispatcher Step:** Allocates tasks/destinations to idle robots via `TaskDispatcher` protocol (default: `wander` with dwell times).
5. **Planner Propose Move Intents:** Computes path step intents via `MovementPlanner` protocol (default: `astar_flow` with traffic heuristics).
6. **SafetyGuard Validate & Commit:** Exclusive mutation point. Validates collision-freedom, swap-prevention, flow adherence, e-stops, and reservations. Commits robot positions.
7. **Update Physical State:** Updates motion progress, battery drain/charge rates, charging station connections, and operational states.
8. **Evaluate Alert Rules:** Evaluates declarative YAML rules against dynamic world state to raise or auto-resolve active alerts.
9. **Emit Events & Advance:** Emits typed events with monotonically increasing sequence IDs (`seq`), updates metrics, advances `tick += 1`.

---

## 3. Core Invariants & Safety Boundary (SR-7)

1. **SafetyGuard Exclusivity:** No component outside `SafetyGuard.validate_and_apply_moves` is permitted to mutate `robot.cell`. Dispatchers and Planners output *intents* only.
2. **Cell Reservation & Swap Immunity:** Moving robots reserve both their source and destination cells across the duration of a move transition. Stationary robots lock their occupied cell. Head-on swaps and double-occupancies are physically impossible by construction.
3. **Discrete Determinism:** All state progression depends strictly on the initial `seed`, `config`, and injected command sequence. No wall-clock time (`time.time()`) is referenced inside core logic. Independent `SeedSequence` streams prevent cross-component RNG coupling. Canonical JSON serialization with SHA-256 state hashing provides bit-for-bit auditability.
4. **Zero Magic Numbers (SR-5):** All thresholds, rates, speeds, and dimensions reside in typed Pydantic models in `config/models.py`. The `tools/magic_numbers.py` scanner strictly gates PRs against undeclared literals.

---

## 4. Declared Extension Seams (CA-1 to CA-9)

All extension points use generic typed registries (`Registry[T]`) backed by runtime protocols:
- **CA-1 World / Layout:** `WorldGenerator` (parametric generator and ASCII layout loader).
- **CA-2 Catalogue / Orders:** `CatalogueSource` (`generated`, `csv`) and `OrderSource`.
- **CA-3 Business Rules:** Declarative YAML rule engine (placement, movement zones, alerts, AI gating).
- **CA-4 Configuration:** Layered hierarchy (`defaults.yaml` < `scenario.yaml` < `ROBOFLEET_*` env < CLI `--set`).
- **CA-5 Dispatcher & Planner:** `TaskDispatcher` (`wander`) and `MovementPlanner` (`astar_flow`).
- **CA-6 Operations Brain:** `Brain` interface (Phase 5).
- **CA-7 Metrics:** `MetricProvider` for fleet KPIs (Phase 3).
- **CA-8 Fault Injection:** `FaultInjector` for chaos experiments (Phase 6).
- **CA-9 Visualization & Sinks:** `EventSink` streaming outputs (`events.ndjson`, snapshots).
