# Contracts Changelog

All contracts adhere to Semantic Versioning (SemVer 2.0.0).

## [1.0.0] - 2026-11-22
### Added
- Initial contracts for Phase 1: Dynamic Core.
- `StaticWorld`: Grid layout, catalogue, bins, stations, chargers, config summary.
- `DynamicState`: Robots, orders, alerts, blocked cells, station states, tick, sequence.
- `WorldSnapshot`: Union of `StaticWorld` and `DynamicState`.
- `Robot`, `Layout`, `Cell`, `Sku`, `Bin`, `Station`, `Charger`, `Order`, `Task`, `Alert`, `Event`.
- `meta.environment` contract for single disclosure surface (`mode`, `data_source`, `robot_layer`).
- `ext: dict` field on dynamic contracts for backwards-compatible extensibility without schema bumps.
