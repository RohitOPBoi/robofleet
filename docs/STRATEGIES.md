# Baseline Fulfilment Dispatcher Strategies

RoboFleet provides four distinct fulfilment dispatcher strategies (extension seam **CA-5**) registered in `strategy_registry` and configurable via YAML (`dispatcher.type`).

---

## 1. Baseline Comparison Summary

| Strategy Name | Order Selection Rule | Robot Selection Rule | Station Assignment | Battery Handling |
| :--- | :--- | :--- | :--- | :--- |
| **`fcfs_nearest`** | First-Come First-Served (`created_tick`) | Minimum Manhattan distance $d(\text{AMR}, \text{Bin})$ | Static default station | Reactive re-route at low battery threshold ($< 20\%$) |
| **`edf_deadline`** | Earliest Deadline First (`deadline_tick`, `-priority`) | Minimum Manhattan distance $d(\text{AMR}, \text{Bin})$ | Static default station | Reactive re-route at low battery threshold ($< 20\%$) |
| **`batch_greedy`** (Strong Baseline) | Earliest Deadline First with urgency sorting | Minimum Marginal Travel Cost $d(\text{AMR}, \text{Bin}) + d(\text{Bin}, \text{Station})$ | Dynamic queue-length load balancing | Proactive safety buffer ($> \text{low} + 5\%$) |
| **`random`** (Sanity Floor) | Uniform random shuffle | Uniform random shuffle | Uniform random station | Reactive re-route at low battery threshold ($< 20\%$) |

---

## 2. Strategy Architectural Details

### 1. `batch_greedy` (Strong Baseline)
Designed as an industry-credible operations heuristic:
1. **Marginal Travel Cost**: Rather than blindly sending the closest robot to a bin, it evaluates the total travel circuit:
   $$\text{Cost}(R) = \|\text{pos}(R) - \text{pos}(\text{Bin})\|_1 + \|\text{pos}(\text{Bin}) - \text{dock}(\text{Station})\|_1$$
2. **Station Load Balancing**: Ranks stations by active approach queue length:
   $$\text{Queue}(S) = |\text{robot\_queues}[S]|$$
   Orders are assigned to the least-congested station with available approach capacity. Multi-line orders retain their station affinity to prevent cross-station fragmentation.
3. **Proactive Battery Awareness**: Robots with battery $\le 25\%$ will not accept new transport tasks and instead proceed to open chargers before entering a critical state.

### 2. `fcfs_nearest` (Standard Operations Baseline)
Standard FIFO industrial warehouse dispatcher:
- Evaluates orders in arrival order (`created_tick`).
- Dispatches the nearest idle AMR.
- Does not account for station queue congestion or return travel distances.

### 3. `edf_deadline` (SLA Urgency Baseline)
Designed to minimize order tardiness:
- Sorts unassigned and in-flight orders by deadline urgency:
  $$\text{Priority Key} = (\text{deadline\_tick}, -\text{priority})$$
- Nearest idle robot dispatched to fulfill urgent lines first.

### 4. `random` (Sanity Floor Floor Baseline)
- Randomizes order selection, robot pairing, and station allocation.
- Serves as the statistical sanity floor; any viable heuristic must substantially outperform `random`.

---

## 3. Extension Seam CA-5: Adding New Strategies

RoboFleet enforces that a new strategy can be introduced by creating a single class implementing `FulfilmentStrategy` and registering it in `strategy_registry`:

```python
from robofleet.registry.generic import strategy_registry

class CustomDispatchStrategy:
    name = "custom_strategy"

    def dispatch(self, orders, robots, layout, bins, skus, task_mgr, station_mgr, current_tick, rng):
        ...
        return destinations

strategy_registry.register("custom_strategy", CustomDispatchStrategy)
```
Passes Change Drill **CD-5** with $\le 2$ files touched.
