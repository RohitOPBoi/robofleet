# RoboFleet 10-Minute Technical & Diligence Walkthrough Script

**Target Audience**: Head of Robotics, Principal Automation Architects, VP of Technology, Operations Diligence Teams.  
**Objective**: Deep-dive audit of the architectural seams, formal space-time reservation planning, chaos self-healing taxonomy, statistical evidence reproducibility, and live customer CSV ingestion.

---

## 1. Architecture & Digital Twin Foundation (00:00 - 02:30)
- **Visual**: 2D/3D Split View (`Key V` -> split mode).
- **Narrative**:
  - Introduction to the deterministic digital twin (`SimEngine`).
  - Explanation of the parametric layout generator (`docs/playbook/phase-1-mvp.md`), cell coordinate system, one-way directional aisle rules, and charging pads.
  - Walkthrough of the `reservation_astar` planner: space-time $(x, y, t)$ grid reservations. Demonstrate that head-on collisions and vertex swaps are mathematically impossible.
  - Review of the **Environment Disclosure Modal**: explain the strict separation between simulated robotics kinetics and real commercial order ingestion.

## 2. Order Dispatching & Fulfillment Heuristics (02:30 - 04:30)
- **Visual**: Order Board + Selected AMR Panel.
- **Narrative**:
  - Contrast baseline FCFS against `batch_greedy` and Earliest Deadline First (`edf_deadline`).
  - Trigger high-velocity demand surge (2.5x rush multiplier).
  - Inspect AMR tote carrying mechanics, pick dwell times, and station handover buffers.
  - Highlight real-time KPI streaming over WebSocket (`throughput_orders_per_hr`, `order_to_ready_p90_s`, `fleet_utilization`).

## 3. Resilience, Chaos Injection & Self-Healing (04:30 - 06:45)
- **Visual**: Chaos Control Modal + Incident Timeline + Exceptions Queue.
- **Narrative**:
  - Open Chaos Control Studio. Review the 10 failure taxonomy categories (hardware breakdowns, sensor drift, station faults, barcode misreads, stock-outs).
  - Inject multi-robot motor stall and corridor blockage.
  - Observe automatic detection: MTTD $< 2.5\text{s}$.
  - Observe automatic mitigation: dynamic corridor avoidance, task reassignment, and re-reservation without deadlocks.
  - Open **Exceptions Queue**: demonstrate how pick verification discrepancies (damaged goods, barcode misreads) are quarantined and surfaced to human supervisors with 1-click resolution actions.
  - Review the cryptographic **Audit Ledger** (`/api/audit/logs`): every automated and manual override is logged with role, actor, timestamp, and before/after diffs.

## 4. AI Operations Brain & Governance Gate (06:45 - 08:30)
- **Visual**: Decision Log Panel + Approvals Drawer + Natural Language Supervisor Bar.
- **Narrative**:
  - Review the Mission Orchestrator: specialized multi-agent roles (Flow, Congestion, Policy, Explainer).
  - Demonstrate the two-tier safety architecture: the AI Brain can only recommend actions; every action must pass through the deterministic `GovernanceLayer` and physical `SafetyGuard`.
  - Demonstrate approval workflows: actions exceeding risk thresholds (e.g., bulk zone lockdowns) are queued in the Approvals Drawer for human operator confirmation.
  - Demonstrate provider failover: unplug network or inject API failure; system falls back to sub-1ms deterministic heuristics with zero dropped frames.

## 5. Live Customer Data Ingestion & Calibration (08:30 - 09:30)
- **Visual**: Terminal + `examples/customer_orders_sample.csv`.
- **Narrative**:
  - Demonstrate `robofleet calibrate`: fit arrival rates, diurnal curves, basket size distributions, and SKU Pareto curves from raw customer order exports.
  - Demonstrate `csv_replay`: run the digital twin directly against client data to produce a tailored ROI and throughput estimate.
  - Demonstrate REST webhook ingest (`/api/orders/webhook`) with HMAC authentication and idempotency guarantees.

## 6. Diligence Q&A & Evidence Hand-Off (09:30 - 10:00)
- **Visual**: `reports/evidence-matrix-flagship/evidence.md` + Plots.
- **Narrative**:
  - Reiterate that every figure in the pitch deck is backed by 95% confidence intervals across paired holdout seeds ($N \ge 10$).
  - Invite technical reviewers to clone the repository and run `make verify` and `make demo` to audit the code themselves.

---

*Standard Footnote: All figures measured in the RoboFleet digital twin under stated parametric assumptions. Full evidence reproduced via `make evidence`.*
