# RoboFleet Supervisor Workflow & Governance Specification

## 1. Supervisor Role & Governance Model

In automated dark stores, human operators and supervisors act as safety monitors and final decision arbiters for operational edge cases. RoboFleet Phase 6 establishes a human-in-the-loop governance structure that guarantees operational progress while adhering to physical safety constraints.

---

## 2. Exceptions Queue Contract

The Exceptions Queue (`backend/src/robofleet/audit/exceptions_queue.py`) captures edge-case items that cannot be resolved algorithmically with high confidence:

1. **Damaged Goods / Packaging Failure**: Crushed item barcode or ruptured liquid containers requiring physical inspection.
2. **Physical Tote / AMR Recovery**: Mechanically locked AMR or dropped tote requiring human manual runner dispatch or AMR towing.
3. **Unresolvable Stockout**: Primary bin depleted and all replica bins exhausted across ambient, chilled, and frozen zones.
4. **Manual Policy Override**: Re-slotting moves, zone temperature reassignment, or manual order line cancellation.

### SLA Timeouts & Safe Default Actions
Every exception item carries an SLA timeout ($300\text{--}600\text{ ticks}$, equivalent to $30\text{--}60\text{ seconds}$). If a supervisor does not take action within the SLA window, the system automatically triggers a safe default policy:

| Exception Type | Default Action | Rationale |
| :--- | :--- | :--- |
| `damaged_item` | `mark_line_unfulfillable` | Prevents station tote blockage; completes order with partial fulfillment |
| `robot_breakdown` | `reassign_task` | Handoff unpicked lines to nearest operational AMR; frees customer order |
| `stockout_shortage` | `short_line_and_dispatch` | Fulfills remaining items in order; generates customer refund notification |
| `station_offline` | `rebalance_queue` | Distributes pending orders across remaining online stations |

---

## 3. Manual Override Validation Rules (Phase 1 Physical Invariants)

Supervisors cannot bypass physical safety invariants. When a supervisor submits a manual override (e.g. approving a re-slotting move or assigning an order to a shelf), the `ManualOverrideValidator` verifies four hard constraints:

1. **Zone Temperature Compatibility**:
   - Ambient SKUs $\to$ Ambient shelves only
   - Chilled SKUs $\to$ Chilled shelves only
   - Frozen SKUs $\to$ Frozen shelves only
2. **Heavy Shelf Height Limit**:
   - Heavy items ($> 5.0\text{ kg}$) are restricted to bottom shelves ($level \le 1$). Placing items $> 5\text{ kg}$ on upper tiers ($level > 1$) is strictly rejected to prevent structural collapse.
3. **Chemical / Hazmat Separation**:
   - Cleaning chemicals and hazardous aerosols cannot be co-located in the same shelf bay or adjacent bins as food or consumable SKUs.
4. **Bay Weight Capacity**:
   - Cumulative weight in a shelf bay cannot exceed `max_weight_kg` ($250.0\text{ kg}$).

---

## 4. Key Performance Indicator: Human Interventions

RoboFleet continuously tracks:
$$\text{Human Interventions per 100 Orders} = \frac{\text{Total Manual Resolutions}}{\text{Total Orders Ingested}} \times 100$$
- **Target**: $< 2.0\text{ interventions per 100 orders}$ in steady-state production.
- **Chaos Stress Target**: $< 5.0\text{ interventions per 100 orders}$ under correlated multi-fault conditions.
