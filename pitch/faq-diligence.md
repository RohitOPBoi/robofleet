# RoboFleet Technical Diligence & Operator FAQ

Honest, evidence-backed answers to the hardest questions technical, supply chain, and operations buyers ask.

---

### Q1: Is this a real deployment with live physical robots, or a software simulation?
**A**: **RoboFleet is a digital twin and AI operations command centre.** 
The robotics kinetics (AMR wheel velocities, motor stalls, battery discharge) and spatial store layout are simulated via a deterministic, tick-based physics engine. However, the order stream and business workflows are 100% real: the platform ingests live commercial order feeds via REST webhooks (`/api/orders/webhook`) and historical CSV exports (`robofleet calibrate`), mapping them into space-time fulfillment schedules. We do not claim deployed hardware in third-party physical stores.

### Q2: How does RoboFleet guarantee zero collisions between AMRs?
**A**: Through our **Reservation $A^*$ Planner (`reservation_astar`)** and physical **`SafetyGuard` barrier**.
Robots do not merely pathfind in 2D space $(x, y)$; they reserve space-time cells $(x, y, t)$ along an explicit time dimension. If cell $(x_1, y_1)$ is reserved at tick $t_k$, no other robot can reserve that cell or execute a head-on swap edge $(u \leftrightarrow v)$ at that tick. Even if an AMR stalls or drops comms, the non-bypassable `SafetyGuard` locks adjacent cells, preventing collisions. Over 100,000+ simulated ticks across paired holdout seeds, collisions remain strictly 0.

### Q3: What happens when the AI Operations Brain makes a mistake or hallucinates?
**A**: **The AI operates strictly behind a two-tier deterministic governance and safety gate.**
The AI Brain (Claude / LLM specialists) can only propose decisions (`DecisionProposal`); it cannot execute commands directly. Every proposal must pass the declarative `GovernanceLayer` (which enforces battery minimums, hold zone limits, and human approval policies for high-risk actions) and the physical `SafetyGuard`. Furthermore, 100% of entity IDs in AI explanations are fact-checked against the live `SituationBrief` via an automated regex gate—hallucinated IDs are stripped before emission.

### Q4: What happens if the external AI API (Anthropic/OpenAI) fails or the internet drops?
**A**: **Sub-tick deterministic failover.**
The Mission Orchestrator monitors provider health via a circuit breaker. Upon an API error, rate limit, timeout, or network disconnect, the engine falls back within $< 1$ms (the same tick) to deterministic rule-based heuristics (`heuristic` provider). Operational throughput continues without dropped frames, stalls, or human intervention.

### Q5: How was the baseline chosen for comparison claims?
**A**: We benchmark against two industry-standard dispatchers: First-Come-First-Served nearest-robot (`fcfs_nearest`) and Earliest-Deadline-First (`edf_deadline`). We do not benchmark against a deliberately weakened strawman; `fcfs_nearest` represents the standard heuristic used by entry-level AMR fleet managers. All performance deltas are validated across 10 paired holdout seeds using Cohen's $d$ effect sizes.

### Q6: What are the limits of the simulation engine?
**A**: 
- **Fleet Scale**: The Python simulation engine easily sustains up to 50 active AMRs at 60 fps. Beyond 100 AMRs, reservation collision checks become CPU-bound.
- **Physics Fidelity**: Acceleration, deceleration, and turning arcs are modeled via discrete grid transitions (0.5m cell resolution). Wheel slip, floor friction variance, and aerodynamic drag are not modeled.
- **Comms Latency**: WiFi latency is modeled as stochastic packet delay and dropouts; RF multipath propagation is not simulated.

### Q7: What does a 6-week commercial pilot look like?
**A**: 
1. **Weeks 1–2 (Calibration)**: Client provides past order CSV exports. We run `robofleet calibrate` to fit arrival curves and SKU velocity profiles into the digital twin.
2. **Weeks 3–4 (What-If Optimization)**: Digital twin runs simulated stress tests (2x–3x rushes, layout adjustments) to identify fulfillment bottlenecks before touching store operations.
3. **Weeks 5–6 (Live Webhook Dry-Run)**: Client connects staging POS/e-commerce checkout webhooks to `/api/orders/webhook` for real-time dispatch verification.

### Q8: What hardware is required to run RoboFleet?
**A**: Any modern machine or container running Python 3.11+ and Node 18+. The entire stack can be launched locally via `docker compose up` or `make demo` on a standard laptop in under 10 minutes.
