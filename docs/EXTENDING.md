# RoboFleet Extension Guide (Change Drills CD-1 to CD-5)

This guide documents the exact, minimal-step procedures for extending RoboFleet along the declared change axes without modifying core simulation logic.

---

## Change Drill 1 (CD-1): Add Rules in YAML (0 Code Files)

All business logic rules live in `rules/*.yaml`. To add a new rule:

1. Create a new YAML rule file (e.g. `rules/placement_fragile_bottom.yaml`):
```yaml
id: placement_fragile_bottom
version: 1.0.0
scope: placement
description: "Fragile items must be slotted on bottom levels (L1 or L2) to prevent drop damage"
severity: warning
effect: deny
enabled: true
when:
  all:
    - field: "sku.fragile"
      op: "=="
      value: true
    - field: "bin.level"
      op: ">"
      value: 2
test_cases:
  - name: "fragile on top level fails"
    context:
      sku: { fragile: true }
      bin: { level: 3 }
    expected_match: true
  - name: "fragile on bottom level passes"
    context:
      sku: { fragile: true }
      bin: { level: 1 }
    expected_match: false
```
2. Verify and test the rule:
```bash
python -m robofleet.cli rules lint
python -m robofleet.cli rules test rules/placement_fragile_bottom.yaml
```

---

## Change Drill 2 (CD-2): Add Zone, Change Robot Count & Grid Size (0 Code Files)

Store topology, zone boundaries, and fleet counts are purely declarative.

1. Create or modify a scenario configuration (e.g. `scenarios/custom_store.yaml`):
```yaml
fleet:
  robot_count: 35
layout:
  grid_width: 50
  grid_height: 35
  zones:
    - name: "express-packing-zone"
      description: "Dedicated priority dispatch zone"
      min_x: 2
      max_x: 8
      min_y: 2
      max_y: 6
```
2. Run simulation or validate layout:
```bash
python -m robofleet.cli validate-layout --scenario custom_store
python -m robofleet.cli run --scenario custom_store --duration 60
```

---

## Change Drill 3 (CD-3): Add a New Event Type (<= 3 Files + Docs)

1. **`backend/src/robofleet/contracts/events.py`**: Add event model to discriminated union:
```python
class StationCongestionPayload(BaseModel):
    station_id: str
    queue_depth: int


class StationCongestionEvent(BaseEvent):
    event_type: Literal["station.congested"] = "station.congested"
    payload: StationCongestionPayload
```
2. **`backend/src/robofleet/contracts/events.py`**: Add `StationCongestionEvent` to `EventUnion`.
3. Export updated schemas:
```bash
python -m robofleet.cli export-schemas
```

---

## Change Drill 4 (CD-4): Swap Catalogue / Order Source (0 Code Files)

To switch from synthetic catalogue generation to CSV replay:

1. Update `catalogue.source` in your scenario config:
```yaml
catalogue:
  source: "csv"
  csv_path: "data/custom_catalogue.csv"
```
2. Run the simulation. The generic registry automatically instantiates `CsvCatalogueSource`.

---

## Change Drill 5 (CD-5): Register a New Strategy (<= 2 Files + Config)

1. Implement `MovementPlanner` or `TaskDispatcher` protocol:
```python
# backend/src/robofleet/sim/custom_planner.py
from robofleet.interfaces.protocols import MovementPlanner


class GreedyPlanner(MovementPlanner):
    def __init__(self, **params):
        self.params = params

    def plan_next_step(self, robot_id, current_cell, target_cell, world_state):
        # Implementation...
        pass
```
2. Register the strategy in the registry:
```python
from robofleet.registry.generic import planner_registry

planner_registry.register("greedy", GreedyPlanner)
```
3. Configure the strategy in `scenario.yaml`:
```yaml
strategies:
  planner:
    type: "greedy"
    params: {}
```
