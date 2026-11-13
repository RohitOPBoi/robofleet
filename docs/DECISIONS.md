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
