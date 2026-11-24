# RoboFleet Architecture Decision Records (ADRs)

## ADR-001: Dynamic Core over Hardcoded Constraints
- **Date**: 2026-11-22
- **Status**: Accepted
- **Context**: Previous designs had frozen slotting rules, hardcoded grid sizes, and locked dispatchers. To pitch to real companies and support different warehouse footprints, everything tunable must be data or config.
- **Decision**: All tunables live in layered Pydantic v2 configs (`defaults.yaml` < `scenario.yaml` < env < CLI). Behaviours are resolved through typed registries. Placement and movement rules are declarative YAML.
- **Consequences**: Zero magic numbers in code. Extension seams exist along declared change axes (CA-1 to CA-9).

## ADR-002: SafetyGuard as Non-Bypassable Physical Boundary
- **Date**: 2026-11-22
- **Status**: Accepted
- **Context**: In later phases (Phase 3 traffic, Phase 5 LLM brain, Phase 6 chaos), AI agents or planners propose moves. If any agent could mutate coordinates, collisions or swaps could occur.
- **Decision**: The `SafetyGuard` is the only code in the entire repository permitted to mutate a robot's cell. Planners and agents only produce `MoveIntent` or `Command` proposals. Any invariant violation immediately aborts or rejects.
- **Consequences**: Absolute physical guarantee against collision, cell sharing, or swapping.

## ADR-003: Deterministic Simulation via Named Seed Streams
- **Date**: 2026-11-22
- **Status**: Accepted
- **Context**: Headless simulations must be reproducible across platforms and runs.
- **Decision**: Simulation tick is an integer tick. Wall clock is never read inside the core. Random numbers use `numpy.random.SeedSequence` with named independent streams (`sim`, `demand`, `picker`, `faults`). Adding a stream never disturbs existing streams. State hash is SHA-256 of canonical JSON.
- **Consequences**: Exact bit-for-bit replayability for identical seed and inputs.

## ADR-004: AI Operations Brain Architecture & Specialist Consolidation (Phase 5)
- **Date**: 2026-11-23
- **Status**: Accepted
- **Context**: The high-level product vision proposed 12 discrete agents (dispatch, traffic, slotting, picking, replenishment, supervisor, battery, exception, analytics, etc.). Running 12 autonomous LLM agents produces massive latency (3–8s roundtrip), uncontrollable token expenditure ($20+/hr), and coordination deadlocks.
- **Decision**:
  1. Consolidate into **one Mission Orchestrator** and **four Specialist Agents**:
     - `Planner`: Order batching, prioritization, picking station load arbitration.
     - `Traffic & Fleet`: Congestion avoidance, battery management, fleet balance.
     - `Exceptions & Recovery`: Blocked aisle recovery, faulted AMR recovery, stock-out mitigation.
     - `Explainer`: Plain-language decision rationales grounded in the brief, supervisor NL Q&A.
  2. Inventory tracking, dispatch algorithms, and path planning are **deterministic tools** called by the specialists. The LLM does not do geometry or arithmetic.
  3. Strict **Governance Layer (CA-3)** and **SafetyGuard (ADR-002)**: LLM output can only generate schema-valid `BrainCommand` proposals. Every proposal passes declarative policy checks (deny, require-human, auto-approve). The engine and SafetyGuard have final authority.
  4. **Multi-Provider Seam (CA-6)**: `anthropic`, `heuristic` (0ms offline baseline), and `replay`. Immediate 1-tick failover to `heuristic` if the API encounters errors, timeouts (>2s), or budget limits.
- **Consequences**: Deterministic stability, verifiable safety, sub-second heuristic fallback, bounded cost, and explainable decision audit trails.

## ADR-005: Chaos Engineering, Failure Taxonomy, and Autonomous Self-Healing Recovery (Phase 6)
- **Date**: 2026-11-23
- **Status**: Accepted
- **Context**: In real-world micro-fulfilment dark stores, hardware breaks, items go missing, aisles get blocked, barcode scanners fail, and stations jam. Systems that assume happy-path execution either freeze or silently corrupt inventory.
- **Decision**:
  1. **Strict Failure Taxonomy (CA-8)**: 10 typed fault definitions (`robot_breakdown`, `robot_comms_drop`, `battery_cascade`, `aisle_blocked`, `bin_missing_stock`, `item_damaged`, `station_slowdown`, `station_offline`, `urgent_order_burst`, `supervisor_unavailable`). Adding a fault type requires at most 2 files plus YAML (CD-8).
  2. **Non-Bypassable Safety Invariant**: All faults, emergency stops, and dynamic obstacles flow strictly through engine commands and the `SafetyGuard`. SafetyGuard remains the only entity that moves robots and never permits collisions or illegal cell sharing under any chaos condition.
  3. **Pick Verification Contract (SO-101 pattern)**: Every physical pick requires formal verification (`COMMANDED`, `VERIFIED`, `MISMATCH`, `UNVERIFIED`). Picks are retried once; unverified picks are never treated as success, items are isolated, and exceptions are escalated.
  4. **Algorithmic-First Self-Healing with AI Arbitration**:
     - Failed AMRs immediately return uncompleted tasks to the pending queue preserving priority; carried totes are flagged for human retrieval.
     - Missing/damaged items search replica bins or trigger short-line policies (`partial_fulfilment`, `delay`, `cancel`).
     - Blocked cells trigger dynamic A* detours.
     - Exceptions specialist proposes recovery plans; heuristic fallback mirrors same deterministic logic.
  5. **Append-Only SQLite Audit Trail**: Every human and AI state modification is recorded with user, role, before/after state, rationale, and outcome. Manual overrides are validated against Phase 1 hard physical constraints (temperature, weight, chemical, level safety); invalid attempts are rejected and logged.
  6. **Deliberately Minimal Replenishment & Re-slotting**: Rule-driven replenishment where urgent order work strictly outranks restock. Re-slotting engine generates recommendations only (no automatic stock moves) and enforces a congestion guard.
- **Consequences**: Verifiable resilience, zero lost orders, truthful MTTR metrics, full audit compliance, and safe degraded-mode operations.

