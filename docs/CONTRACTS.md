# RoboFleet Contracts & Evolution — Phase 1

## 1. Contract Architecture

All external data transfer, persistence, and inter-service schemas reside in `robofleet.contracts`. Contracts are isolated from internal simulation logic (`sim/`) to guarantee stability, serialization guarantees, and zero circular dependencies.

### Static vs. Dynamic Separation
- **`StaticWorld`:** Sent once at connection / run startup. Encapsulates immutable environment geometry, station locations, chargers, bin definitions, catalogue metadata, and configuration summaries.
- **`DynamicState`:** High-frequency state payload emitted periodically or on-demand. Encapsulates robot coordinates, heading, battery, motion progress, order statuses, active alerts, and blocked cells.
- **`WorldSnapshot`:** Composite snapshot (`static` + `dynamic`) enabling full headless checkpointing and replay.

### Environment Metadata
Every top-level contract payload carries non-negotiable environment metadata:
```json
{
  "meta": {
    "environment": {
      "mode": "digital_twin",
      "data_source": "synthetic_generated",
      "robot_layer": "simulated"
    },
    "schema_version": "1.0.0",
    "timestamp_ms": 1732305000000
  }
}
```
This guarantees that clients (Phase 2 2D dashboard, Phase 4 3D canvas) always display unambiguous visual cues distinguishing simulated runs from physical hardware.

---

## 2. Versioning & Extensibility (SR-6)

1. **SemVer Guarantee:** Schema versions follow strict Semantic Versioning (`MAJOR.MINOR.PATCH`).
2. **Additive Free-Form Extension (`ext: dict`):** Every model includes an optional `ext: dict[str, Any]` payload. Features may attach experimental or phase-specific context without requiring a schema bump.
3. **Client Tolerance:** All contracts configure `extra = "ignore"`, ensuring older clients ignore unrecognised fields from newer minor versions.
4. **Schema Compatibility Gate:** `python -m robofleet.tools.schema_compat` validates committed schemas in `contracts/jsonschema/` against Python models, automatically categorizing changes as `NONE`, `PATCH`, `MINOR`, or `BREAKING`.
5. **Schema Migration Registry:** The `MigrationRegistry` in `robofleet.contracts.migrations` provides bi-directional payload transformation pipelines across breaking schema versions.
