# RoboFleet Contracts & Evolution — Phase 2, 3, 4 & 5

## 1. Version Changelog

### Version 1.3.0 (Phase 5 AI Operations Brain Evolution)
- **Additive**: Added `BrainBaseCommand` hierarchy (`AssignTaskCommand`, `ReprioritiseOrderCommand`, `BatchOrdersCommand`, `RerouteRobotCommand`, `SendToChargeCommand`, `HoldZoneCommand`, `ReleaseZoneCommand`, `SetStationPolicyCommand`, `SetStrategyParamsCommand`, `EscalateToHumanCommand`, `NoActionCommand`).
- **Additive**: Added `SituationBrief` bounded state summary model (`BriefKPIs`, `BriefOrderSummary`, `BriefStationQueue`, `BriefRobotSummary`, `congested_cells`, `brief_hash`).
- **Additive**: Added `DecisionProposal` and `Decision` unified decision log records.
- **Additive**: Added `ApprovalRequest` for human-in-the-loop governance queue.
- **Additive**: Added `SupervisorQuery` for natural language command parsing and evidence citations.
- **Additive**: Added `BrainStatusPayload` to WebSocket delta stream.
- **Compatibility**: 100% additive; zero breaking schema changes.

### Version 1.2.0 (Phase 3 Fulfilment & Operations Evolution)
- **Additive**: Added `DelayAttribution` contract model for exact WareMax lateness decomposition (`waiting_for_robot_ticks`, `travel_ticks`, `station_queue_ticks`, `picking_ticks`, `consolidation_ticks`, `supervisor_handoff_ticks`, `total_lateness_ticks`).
- **Additive**: Added `ScaleFleetCommand` for runtime dynamic fleet resizing.
- **Additive**: Added `FulfilmentConfig` (`base_pick_time_ticks`, `consolidation_time_ticks`, `supervisor_handoff_base_ticks`, `rider_arrival_rate_per_hr`, `max_queue_capacity`).
- **Additive**: Expanded `OrderStatus` to include full lifecycle: `RECEIVED`, `QUEUED`, `PLANNED`, `RETRIEVING`, `AT_STATION`, `PICKING`, `CONSOLIDATING`, `PACKED`, `READY_FOR_DISPATCH`, `HANDED_OVER`, `FAILED_PARTIAL`, `CANCELLED`.
- **Additive**: Added `tote_id`, `ready_tick`, `handover_tick`, and `assigned_robot_ids` to `Order`.
- **Compatibility**: 100% additive; zero breaking schema changes.

### Version 1.1.0 (Phase 2 Additive Evolution)
- **Additive**: Added `Order` contract models (`OrderLine`, `OrderStatus`, `Order`) with lifecycle states (`RECEIVED`, `QUEUED`, `ASSIGNED`, `PICKING`, `PACKING`, `DISPATCHED`, `CANCELLED`).
- **Additive**: Added `DynamicKPIs` model for live operational metric reporting.
- **Additive**: Added `MotionProgress` model for sub-tick AMR interpolation (`from_coord`, `to_coord`, `progress`).
- **Additive**: Added WebSocket envelope models (`HelloPayload`, `StateDeltaPayload`, `EnvironmentDisclosure`).
- **Compatibility**: All new models are backwards-compatible with Phase 1 committed schemas (`schema_compat` check passes with `MINOR` rating).

---

## 2. Type Sharing (`make types`)

TypeScript contracts are generated directly from the Python models into `frontend/src/types/generated.ts` via `make types` (or `python tools/export_types.py`).

CI gate `test_generated_typescript_types_up_to_date()` enforces that the committed TypeScript types match the Python backend definitions without drift.
