# RoboFleet Extension Guide (Change Drills CD-1 to CD-9)

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
To add a thermal zone, increase fleet count to 50, and resize the store grid:
1. Edit `scenarios/custom_store.yaml`:
```yaml
name: "custom_hyperlocal_store"
robot_count: 50
layout:
  preset: "custom"
  width: 32
  height: 24
  zones:
    - name: "ambient_aisles"
      temperature: "ambient"
      top_left: [1, 1]
      bottom_right: [20, 22]
    - name: "subzero_frozen_vault"
      temperature: "frozen"
      top_left: [21, 1]
      bottom_right: [30, 10]
```
2. Run simulation with the scenario:
```bash
python -m robofleet.cli run --scenario custom_store --ticks 1000
```
Both 2D Map and 3D Digital Twin dynamically generate geometries and floor slabs from `StaticWorld` without frontend code changes (P4-A2).

---

## Change Drill 4a (CD-4a): Add a New Robot Kind Visual (<= 2 Files)

To add a new specialized robot visual (e.g., `forklift_amr`):
1. In `frontend/src/components/Scene3D/AssetRegistry.ts`, define the procedural builder:
```typescript
export const buildForkliftAMR: RobotModelBuilder = ({ statusColor, hasTote }) => {
  const group = new THREE.Group();
  // Add chassis, mast, forks, and status beacon
  return group;
};

// Register in pluggable dictionary
ROBOT_ASSET_REGISTRY["forklift_amr"] = buildForkliftAMR;
```
2. In backend domain/configuration, set `robot.kind = "forklift_amr"`.
Files touched: 1 frontend file (`AssetRegistry.ts`) + 1 scenario config. Verified in `backend/tests/test_phase4_3d.py`.

---

## Change Drill 9 (CD-9): Add Camera Waypoints and Lighting Presets (<= 2 Files)

To add a new custom camera tour path or lighting preset:
1. In `frontend/src/components/Scene3D/CameraController.tsx`:
Add waypoint vector to `waypoints.current`:
```typescript
{
  pos: new THREE.Vector3(15, 8, 25),
  target: new THREE.Vector3(15, 0, 15),
  duration: 8,
}
```
2. In `frontend/src/components/Scene3D/Environment3D.tsx`:
Add a new lighting preset (e.g., `neon_cyber`):
```typescript
case "neon_cyber":
  return {
    ambientColor: "#1e1b4b",
    ambientIntensity: 0.4,
    sunColor: "#ec4899",
    sunIntensity: 1.5,
    sunPos: [width / 2, 10, height / 2],
    shadowBias: -0.0005,
  };
```
Files touched: 2 files. Verified in `tools/audit_phase4_3d.py`.

---

## Change Drill 5 (CD-5): Swap Order Dispatching Strategy (<= 2 Files + Config)

1. Implement `DispatcherStrategy`:
```python
# backend/src/robofleet/fleet/dispatch/custom.py
from robofleet.contracts.commands import DispatchStrategy

class CustomStrategy:
    def dispatch(self, orders, robots, layout, bins, skus, task_mgr, station_mgr, current_tick, rng):
        return destinations
```
2. Register the strategy:
```python
from robofleet.registry.generic import strategy_registry
strategy_registry.register("custom_strategy", CustomStrategy)
```
3. Configure in scenario YAML:
```yaml
dispatcher:
  type: "custom_strategy"
  params: {}
```

---

## Change Drill 7 (CD-7): Add a New KPI (<= 2 Files + Config)

1. Implement a new `MetricProvider` adhering to the CA-7 protocol:
```python
from robofleet.fleet.metrics import MetricProvider

class CarbonOffsetMetricProvider:
    name = "carbon_offset_kpi"

    def compute(self, orders, robots, current_tick, tick_hz):
        moving_amrs = sum(1 for r in robots if r.state.name == "MOVING")
        return {"carbon_saved_kg": float(moving_amrs * 0.12)}
```
2. Register with `metric_provider_registry`:
```python
from robofleet.registry.generic import metric_provider_registry
metric_provider_registry.register("carbon_offset_kpi", CarbonOffsetMetricProvider)
```
3. Verified in CLI Change Drills `robofleet drills` touching $\le 2$ files.

---

## Change Drill 6 (CD-6): Add a New Specialist to Mission Orchestrator (<= 2 Files Plus Prompt)

Specialists implement a simple protocol: `propose(brief: SituationBrief) -> list[DecisionProposal]`.

1. Create specialist implementation in `backend/src/robofleet/brain/specialists/replenishment.py`:
```python
from robofleet.contracts.brain import DecisionProposal, SituationBrief, SetStationPolicyCommand

class ReplenishmentSpecialist:
    name = "replenishment"
    
    def propose(self, brief: SituationBrief) -> list[DecisionProposal]:
        proposals = []
        # Inspect depleted bins and propose priority stowing
        return proposals
```
2. Create prompt file `prompts/replenishment_v1.txt`.
3. Register the specialist in `MissionOrchestrator.__init__` (`robofleet/brain/orchestrator.py`).
4. Verify with `robofleet drills`. Touching $\le 2$ files.

---

## Change Drill 8 (CD-8): Add Operational Governance Policy (0 Code Files)

To add a safety or regulatory governance rule gating AI actions:
1. Create `rules/command_<policy_name>.yaml`:
```yaml
id: command_max_consecutive_reroutes
version: 1.0.0
scope: command
description: "Deny rerouting the same AMR more than 3 times in 100 ticks"
severity: WARN
effect: deny
enabled: true
when:
  all:
    - field: "command.command_type"
      op: "=="
      value: "reroute_robot"
tests:
  - name: "valid reroute allowed"
    context: { command: { command_type: "reroute_robot" } }
    expected_match: true
```
2. The `GovernanceLayer` automatically discovers and evaluates all `scope: command` policies at runtime. Hot-reload without restarting via `orchestrator.governance.reload_policies()`.

