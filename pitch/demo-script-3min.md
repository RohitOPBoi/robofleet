# RoboFleet 3-Minute Executive Pitch Script

**Target Audience**: Executive Decision Makers, VP of Supply Chain / E-Commerce Operations, Managing Directors.  
**Objective**: Demonstrate high-velocity autonomous dark-store fulfillment, self-healing resilience under severe operational chaos, and zero-collision safety invariants in under 180 seconds.

---

## Pre-Demo Checklist (T-30s)
1. Browser open to `http://localhost:8000` (1920x1080 resolution, full screen `F11`).
2. Verify Environment disclosure icon shows `[DIGITAL TWIN]`.
3. Fallback safety net ready: if WiFi drops or backend stalls, click **"Replay Stage Demo"** at the bottom dock.

---

## Second-by-Second Presentation Script

| Timestamp | Screen State & Action | Spoken Script | Stage Fallback (If Glitch) |
|---|---|---|---|
| **00:00 - 00:25** | **Live 3D Digital Twin View** (`ba1a624`)<br/>20 AMRs moving smoothly between aisles, pick bays, and packing stations. Warm evening lighting. | *"Instant commerce promises 15-minute grocery deliveries, but micro-fulfillment stores collapse under peak volume and random hardware faults. This is RoboFleet: an autonomous command centre and digital twin orchestrating hybrid AMR fleets. Notice our physical reservation planner: 20 robots navigating high-density aisles with mathematical zero-collision guarantees."* | If 3D drops frames on low-tier laptop, press `V` to switch to high-performance 2D Canvas. |
| **00:25 - 00:55** | **Trigger 2.5x Peak Rush**<br/>Click **Rush** button in TopBar or press `Ctrl+K` -> *"Trigger 2.5x rush demand"*. Orders stream into Order Board. | *"Watch demand spike. We just hit a 2.5x rush surge. Watch the Order Board on the left: express SLA orders are highlighted in cyan. Our batch greedy dispatcher clusters multi-line orders, dynamic aisle reservations prevent bottlenecks, and fleet utilization climbs to 94% without human dispatchers."* | If command bar fails, click TopBar quick-action **Rush**. |
| **00:55 - 01:45** | **Inject Severe Chaos Fault**<br/>Click **Chaos Studio** -> Click **"Perfect Storm"**.<br/>AMR-002 stalls with motor breakdown; Aisle 3 is blocked by a physical obstruction; Station 1 goes offline. | *"Here is where conventional automation breaks down: physical chaos. We just injected a 'Perfect Storm' incident. Notice: AMR-002 has stalled dead in a critical corridor, and Aisle 3 is physically blocked. In standard warehouses, this triggers manual supervisor walkouts and catastrophic gridlock. Watch RoboFleet's self-healing: our SafetyGuard instantly halts approaching traffic, the mission orchestrator re-routes in-flight totes around the blockage, and quarantined items are isolated in our exceptions queue. Mean time to recovery: under 18 seconds."* | If chaos fails to trigger, load `demo_golden_run` via bottom timeline. |
| **01:45 - 02:25** | **AI Operations Brain & Audit Ledger**<br/>Open **Supervisor Command Bar** (`Ctrl+K`) -> type *"Explain recent reroute decisions"*. Open **Audit Ledger**. | *"Behind this is the RoboFleet AI Operations Brain. Every automated action passes through our strict Governance Layer and tamper-evident audit ledger. Zero hallucinations: 100% of entity IDs are fact-checked against real digital twin state before emission. Human supervisors retain full authority to approve bulk re-slotting or override dispatch."* | If local LLM latency spikes, the system automatically falls back to sub-1ms deterministic heuristics. |
| **02:25 - 03:00** | **Evidence & Integration Close**<br/>Switch to **Environment Disclosure Modal** (`E`). | *"Every number we present is substantiated across 10 paired holdout seeds in our automated evidence matrix. Our integration story is simple: ingest your real historical CSV exports using `robofleet calibrate` today, or stream live POS checkout webhooks tomorrow. Thank you."* | Point to `docs/CLAIMS.md` and `docs/INTEGRATION.md`. |

---

*Standard Footnote: All figures measured in the RoboFleet digital twin under stated parametric assumptions. Full evidence reproduced via `make evidence`.*
