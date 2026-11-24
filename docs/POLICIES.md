# Declarative Policy Rules Reference (Phase 5)

All operational constraints in RoboFleet are governed by declarative YAML policies evaluated by the `RuleEngine` (`backend/src/robofleet/rules/engine.py`). Rules are organized into four scopes:
1. `placement`: SKU storage and inventory slotting.
2. `movement`: Physical grid movement, aisle traversal, and keepout boundaries.
3. `alert`: Reactive warning and fault detection.
4. `command`: Phase 5 AI governance layer gating typed AI proposals.

---

## Command Governance Policies (Phase 5)

### 1. `command_never_strand_low_battery`
- **File:** `rules/command_never_strand_low_battery.yaml`
- **Scope:** `command`
- **Severity:** `CRITICAL`
- **Effect:** `deny`
- **Description:** Never assign a task to a robot with battery below 15% unless task is send_to_charge.
- **Rule Condition:**
  ```yaml
  when:
    all:
      - field: "command.command_type"
        op: "=="
        value: "assign_task"
      - field: "robot.battery_percent"
        op: "<"
        value: 15.0
  ```

### 2. `command_hold_zone_limit`
- **File:** `rules/command_hold_zone_limit.yaml`
- **Scope:** `command`
- **Severity:** `WARN`
- **Effect:** `deny`
- **Description:** Cannot hold a zone if 2 or more zones are already held (zone hold capacity cap).
- **Rule Condition:**
  ```yaml
  when:
    all:
      - field: "command.command_type"
        op: "=="
        value: "hold_zone"
      - field: "held_zones_count"
        op: ">="
        value: 2
  ```

### 3. `command_bulk_reroute_human`
- **File:** `rules/command_bulk_reroute_human.yaml`
- **Scope:** `command`
- **Severity:** `WARN`
- **Effect:** `require_human`
- **Params:** `timeout_ticks: 40`, `default_action: deny`
- **Description:** Rerouting with avoid cells requires human supervisor approval.
- **Rule Condition:**
  ```yaml
  when:
    all:
      - field: "command.command_type"
        op: "=="
        value: "reroute_robot"
      - field: "command.avoid_cells"
        op: "!="
        value: null
  ```

---

## Placement & Movement Rules (Phases 1-3)

- `placement_bin_capacity_exceeded` (`rules/placement_capacity.yaml`): Max 100 items or 25kg per bin.
- `placement_chemical_near_perishable` (`rules/placement_chemical_isolation.yaml`): Chemical SKUs isolated from perishables.
- `placement_heavy_on_top_shelf` (`rules/placement_heavy_shelf.yaml`): Items $> 5$kg restricted to bottom 2 shelf tiers.
- `placement_temperature_mismatch` (`rules/placement_temperature.yaml`): Chilled/frozen items must reside in appropriate temperature zone.
- `movement_supervisor_keepout` (`rules/movement_supervisor_zone.yaml`): AMRs barred from supervisor handoff cells.
- `alert_low_battery` (`rules/alert_low_battery.yaml`): Alert raised when battery drops below 20%.
- `alert_robot_waiting_too_long` (`rules/alert_robot_waiting.yaml`): Alert raised when AMR is blocked for $> 30$ ticks.

---

## 3. Resilience, Chaos & Recovery Policies (Phase 6)

### 1. `recovery_reassign_on_breakdown`
- **Scope:** `chaos_recovery`
- **Trigger:** `robot_breakdown` or unrecoverable `robot_comms_drop`
- **Policy:** The unfulfilled pick tasks assigned to the faulted AMR are reclaimed and re-inserted into the active dispatch queue. The nearest idle AMR with battery $\ge 20\%$ is dispatched.

### 2. `recovery_dynamic_reroute_blocked_aisle`
- **Scope:** `chaos_recovery`
- **Trigger:** `aisle_blocked`
- **Policy:** A* space-time search graph removes transit edges intersecting the blocked coordinate. Robots with existing reservations intersecting the block are recalculated via alternate corridors.

### 3. `recovery_replica_substitution_or_short`
- **Scope:** `chaos_recovery`
- **Trigger:** `bin_missing_stock` or `item_damaged`
- **Policy:**
  1. Search for replica bin containing identical SKU in the same temperature zone.
  2. If replica found with $Q \ge \text{needed}$, dynamically update AMR retrieval target to replica bin.
  3. If no replica available, apply short line policy: fulfill available order lines, isolate damaged unit, and notify customer of partial fulfillment.

### 4. `recovery_station_failover_rebalance`
- **Scope:** `chaos_recovery`
- **Trigger:** `station_offline` or `station_slowdown`
- **Policy:** Active picking queue at faulted station is frozen. Totes in transit are re-vectored to the nearest operational picking station with queue depth $< \text{threshold}$.

### 5. `replenishment_lite_urgent_preemption`
- **Scope:** `replenishment`
- **Policy:** Customer SLA express orders strictly preempt shelf replenishment runners. Shelf restock operations yield transit aisles and station docking cells.

