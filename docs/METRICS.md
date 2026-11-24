# RoboFleet Metrics & Operations KPI Engine (CA-7)

This document specifies the operational KPIs, mathematical definitions, cycle-time percentile derivations, and the WareMax delay attribution decomposition (Phase 3).

---

## 1. Primary Operations KPIs

| Metric Key | Description | Unit | Mathematical Definition |
| :--- | :--- | :---: | :--- |
| **`throughput_orders_per_hr`** | Rate of orders completed | orders/hr | $\frac{N_{\text{completed}}}{\Delta T_{\text{sim\_hours}}}$ where $\Delta T_{\text{sim\_hours}} = \frac{\text{tick}}{3600 \times \text{tick\_hz}}$ |
| **`on_time_percentage`** | SLA on-time delivery rate | % | $100 \times \frac{\sum [T_{\text{handover}} \le T_{\text{deadline}}]}{N_{\text{completed}}}$ |
| **`order_to_ready_mean_s`** | Average cycle time from receipt to packed ready | seconds | $\frac{1}{N_{\text{ready}}} \sum \frac{T_{\text{ready}} - T_{\text{created}}}{\text{tick\_hz}}$ |
| **`order_to_ready_p90_s`** | 90th percentile order-to-ready latency | seconds | $P_{90}(\{(T_{\text{ready}} - T_{\text{created}}) / \text{tick\_hz}\})$ |
| **`order_to_handover_p90_s`** | 90th percentile total cycle time to rider handoff | seconds | $P_{90}(\{(T_{\text{handover}} - T_{\text{created}}) / \text{tick\_hz}\})$ |
| **`station_utilization_pct`** | Average pick station busy time | % | $100 \times \frac{1}{|S|} \sum_{s \in S} \frac{\text{busy\_ticks}_s}{\text{total\_ticks}}$ |
| **`supervisor_utilization_pct`** | Dispatch bay supervisor handoff desk busy time | % | $100 \times \frac{\text{supervisor\_busy\_ticks}}{\text{total\_ticks}}$ |
| **`fleet_utilization`** | Percentage of AMRs actively moving or picking | % | $100 \times \frac{N_{\text{moving}} + N_{\text{picking}}}{N_{\text{fleet}}}$ |
| **`deadlock_incidents`** | Total resolved traffic deadlock cycles | count | Incremented upon wait-for graph cycle detection |
| **`collisions_count`** | Physical safety boundary violations | count | Strictly 0 enforced by SafetyGuard |

---

## 2. WareMax Delay Attribution Decomposition (P3-A8)

When an order arrives past its committed SLA deadline ($T_{\text{handover}} > T_{\text{deadline}}$), RoboFleet decomposes total lateness into six operational stages:

$$\text{Total Lateness (ticks)} = \max(0, T_{\text{handover}} - T_{\text{deadline}})$$

### Stage Durations
1. **Waiting for AMR** ($\Delta t_{\text{wait}}$): $T_{\text{planned}} - T_{\text{created}}$
2. **AMR Travel** ($\Delta t_{\text{travel}}$): $T_{\text{at\_station}} - T_{\text{retrieving}}$
3. **Station Queue** ($\Delta t_{\text{station\_queue}}$): $T_{\text{picking}} - T_{\text{at\_station}}$
4. **Picking Duration** ($\Delta t_{\text{pick}}$): $T_{\text{consolidating}} - T_{\text{picking}}$
5. **Consolidation Duration** ($\Delta t_{\text{consolidation}}$): $T_{\text{packed}} - T_{\text{consolidating}}$
6. **Supervisor Bay Handoff** ($\Delta t_{\text{supervisor}}$): $T_{\text{handover}} - T_{\text{packed}}$

$$\text{Total Duration} = \Delta t_{\text{wait}} + \Delta t_{\text{travel}} + \Delta t_{\text{station\_queue}} + \Delta t_{\text{pick}} + \Delta t_{\text{consolidation}} + \Delta t_{\text{supervisor}}$$

### Exact Proportional Decomposition
To guarantee that the attributed stage delays sum strictly to $\text{Total Lateness}$ without rounding errors:
$$P_i = \text{round}\left(\text{Total Lateness} \times \frac{\Delta t_i}{\text{Total Duration}}\right) \quad \text{for } i \in \{\text{wait}, \text{travel}, \text{queue}, \text{pick}, \text{cons}\}$$
$$P_{\text{supervisor}} = \text{Total Lateness} - \sum_{i \ne \text{supervisor}} P_i$$

**Strict Invariant (P3-A8)**:
$$P_{\text{wait}} + P_{\text{travel}} + P_{\text{queue}} + P_{\text{pick}} + P_{\text{cons}} + P_{\text{supervisor}} \equiv \text{Total Lateness}$$

---

## 3. Worked Hand-Calculation Scenario (P3-A7)

The following deterministic hand-worked scenario is programmatically verified in `test_metrics_worked_example_hand_calculation`:

### Input Scenario
- Simulation Duration: 120 ticks at $\text{tick\_hz} = 1$ ($\Delta T = 120\text{ s} = \frac{120}{3600}\text{ hr} = \frac{1}{30}\text{ hr}$).
- Three completed orders:

| Order | $T_{\text{created}}$ | $T_{\text{deadline}}$ | $T_{\text{ready}}$ | $T_{\text{handover}}$ | On-Time? | Ready Latency | Handover Latency | Lateness |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`O1`** | 10 | 100 | 50 | 60 | Yes ($60 \le 100$) | 40s | 50s | 0s |
| **`O2`** | 20 | 80 | 70 | 90 | No ($90 > 80$) | 50s | 70s | 10s |
| **`O3`** | 30 | 150 | 110 | 120 | Yes ($120 \le 150$) | 80s | 90s | 0s |

### Hand Calculation Steps
1. **Total Completed Orders**: $3$
2. **On-Time Count**: $2$ (orders `O1` and `O3`)
3. **On-Time Percentage**:
   $$\text{On-Time \%} = \frac{2}{3} \times 100\% = 66.67\%$$
4. **Throughput (orders/hr)**:
   $$\text{Throughput} = \frac{3 \text{ orders}}{120 / 3600 \text{ hr}} = 3 \times 30 = 90.0 \text{ orders/hr}$$
5. **Cycle Times Percentiles**:
   - Order-to-ready latencies: $[40, 50, 80]$ seconds.
   - Order-to-handover latencies: $[50, 70, 90]$ seconds.

Verified by `backend/tests/test_phase3_fulfilment.py::test_metrics_worked_example_hand_calculation`.

---

## 4. Phase 5 AI Operations Brain Metrics

| Metric Key | Description | Unit | Mathematical Definition / Invariant |
| :--- | :--- | :---: | :--- |
| **`ai_decision_latency_ms`** | Total wall-clock time from brief construction to executed commands | ms | Heuristic: $< 20$ms; Claude: $< 2000$ms |
| **`governance_denial_rate`** | Share of AI proposed commands rejected by declarative policies | % | $100 \times \frac{N_{\text{denied}}}{N_{\text{proposed}}}$ |
| **`human_approval_rate`** | Share of enqueued approval requests approved by supervisor | % | $100 \times \frac{N_{\text{approved}}}{N_{\text{enqueued}}}$ |
| **`hallucination_audit_rate`** | Share of referenced entity IDs audited and sanitized by Explainer | % | Strictly 100% (0 unverified entity IDs emitted) |
| **`circuit_trip_count`** | Number of times LLM provider tripped open to heuristic fallback | count | Increments when consecutive failures $\ge 3$ |
| **`total_brain_cost_usd`** | Cumulative token expenditure for LLM provider API calls | USD ($) | $\sum (\text{tokens}_{\text{in}} \times P_{\text{in}} + \text{tokens}_{\text{out}} \times P_{\text{out}})$ |
| **`safety_rejections_count`** | Commands rejected by physical SafetyGuard | count | Strictly 0 (Physical Invariant) |

---

## 5. Phase 6 Resilience & Chaos Metrics (CA-7)

| Metric Key | Description | Unit | Mathematical Definition / Invariant |
| :--- | :--- | :---: | :--- |
| **`mttd_seconds`** | Mean Time To Detect operational faults | seconds | $\frac{1}{N_{\text{faults}}} \sum \frac{T_{\text{detected}} - T_{\text{injected}}}{\text{tick\_hz}}$ |
| **`mttr_seconds`** | Mean Time To Recover from fault injection | seconds | $\frac{1}{N_{\text{faults}}} \sum \frac{T_{\text{cleared}} - T_{\text{injected}}}{\text{tick\_hz}}$ |
| **`human_interventions_per_100_orders`** | Frequency of human supervisor manual resolutions | count / 100 orders | $100 \times \frac{N_{\text{interventions}}}{N_{\text{orders}}}$ (Target: $< 2.0$) |
| **`exceptions_queue_age_ticks`** | Age of oldest active exception in queue | ticks | $\max_{i \in \text{pending}} (\text{tick} - T_{\text{raised}, i})$ |
| **`degraded_mode_duration_s`** | Cumulative duration warehouse operated in degraded mode | seconds | $\sum \frac{\Delta t_{\text{degraded}}}{\text{tick\_hz}}$ |
| **`orders_affected_count`** | Orders whose transit or picking was disrupted by chaos faults | count | Monotonically non-decreasing counter |
| **`orders_lost_count`** | Orders dropped or canceled without fulfillment | count | **Strictly 0** (Resilience Invariant) |
| **`partial_fulfilment_rate_pct`** | Share of orders fulfilled partially due to shortages | % | $100 \times \frac{N_{\text{partial}}}{N_{\text{completed}}}$ |
| **`pick_verification_error_rate`**| Discrepancy rate in commanded vs verified picks | % | Target: $\approx 2.0\%$ under SO-101 |


