# RoboFleet Empirical Assumptions & Scientific Basis (Phases 2, 3, & 4)

## 1. Demand Modeling Assumptions

### 1.1 Diurnal Arrival Rates
- **Source**: Indian quick-commerce benchmark data (Zepto, Blinkit, Instamart order distributions).
- **Pattern**: Two distinct daily peaks:
  - Lunch peak (12:00–14:00): ~1.0x to 1.1x base rate.
  - Evening peak (18:00–21:00): ~2.1x to 2.4x base rate.
  - Night trough (01:00–05:00): ~0.05x to 0.15x base rate.
- **Statistical Model**: Non-homogeneous Poisson process where instantaneous arrival intensity $\lambda(t) = \lambda_{\text{base}} \times M_{\text{hour}}(t) \times M_{\text{overlay}}(t)$.

### 1.2 Basket Characteristics
- **Size Distribution**: Poisson distribution with mean $\mu = 4.2$ items, truncated to $[1, 12]$.
- **Affinity Clustering**: SKUs are sampled from catalog popularity distribution and conditioned on the co-purchase affinity matrix (e.g. Milk + Bread, Chips + Cola).

### 1.3 SLA Tiers
- `standard`: 75% of arrivals, 45-minute nominal SLA window.
- `express`: 20% of arrivals, 15–20 minute SLA window, tagged priority 5.
- `scheduled`: 5% of arrivals, future delivery window.
- **At-Risk Threshold**: Orders are flagged `at_risk` when remaining time falls below 150 ticks (15 seconds simulated time at 10 Hz) relative to remaining fulfillment tasks.

---

## 2. Fulfilment & Station Operations Assumptions (Phase 3)

### 2.1 Pick Station Service Times
- **Base Pick Time**: 3.0 seconds (30 ticks at 10 Hz) per line item.
  - *Source / Basis*: Quick-commerce pick-to-light workstation benchmarks (picker retrieves bin from AMR pod, scans item barcode, places into order tote). [Estimate based on Blinkit/Zepto 2024 operations teardowns].
- **SKU Handling Difficulty Multiplier**:
  - $1.0\times$: Ambient dry packaged goods (instant noodles, biscuits, canned sodas).
  - $1.2\times - 1.5\times$: Chilled dairy, bakery items requiring orientation care.
  - $1.6\times - 1.8\times$: Fragile glassware, eggs, and loose fresh produce.
- **Worker Allocation**: 1 human picker per physical station dock. Bounded queue capacity of 6 AMRs per station approach aisle to prevent main thoroughfare gridlock.

### 2.2 Consolidation & Dispatch Bay Handoff
- **Order Consolidation Duration**: 2.0 seconds (20 ticks at 10 Hz) for multi-line tote review, barcode verification, and thermal/paper bag sealing.
- **Courier Rider Arrival Rate**: Poisson arrival process at 120 riders/hour (average 2 couriers per minute) matching evening peak delivery dispatch cadence.
- **Supervisor Handoff Duration**: 4.0 seconds (40 ticks at 10 Hz) nominal with $\pm 20\%$ uniform jitter representing courier app QR handoff scan and delivery bag staging. [Industry benchmark estimate].

---

## 3. 3D Digital Twin Visual Scale & Graphics Performance (Phase 4)

### 3.1 World Metric Coordinate Mapping
- **Spatial Grid Units**: 1 simulation cell coordinate $(x, y)$ maps directly to 1 Three.js world unit along $(X, Z)$ on the ground plane ($Y=0$).
- **AMR Geometry Scale**:
  - Standard AMR: Radius 0.40m, height 0.18m (conforms to standard 800mm physical aisle clearance).
  - Heavy AMR: Width 0.85m, depth 0.65m, height 0.22m (heavy payload format).
- **Racking Visual Scale**:
  - Upright height: 2.20m (realistic 3-tier dark store pick-tower shelf height).
  - Tote bins: $0.32\text{m} \times 0.22\text{m} \times 0.30\text{m}$ standard KLT Euro-container form factor.

### 3.2 Performance Budget Basis (P4-A3, P4-A4)
- **Target Hardware**: Mid-range laptop integrated GPU (e.g., Intel Iris Xe / AMD Radeon 680M / Apple M-series base).
- **Frame Budget**: 16.6 ms per frame (target 60 FPS median); no frame over 33.3 ms in the 95th percentile.
- **Draw Call Budget**: $\le 200$ draw calls at 50 AMRs. Verified in live WebGL render pipeline at 54 draw calls via GPU instancing (`instancedMesh` for racks, beams, and bins).
- **Context Loss Handling**: When the OS or graphics compositor triggers `webglcontextlost`, the viewport degrades immediately to the 2D HTML5 canvas without throwing unhandled exceptions or presenting a black screen.

---

## 4. AI Operations Brain Assumptions (Phase 5)

### 4.1 Token Budget & Latency Bounds
- **Situation Brief Token Budget**: Up to 1,200 tokens. Achieved by limiting at-risk orders to top 10, critical AMRs to top 10, congested cells to top 5, and passing aggregated counts rather than exhaustive raw entity tables.
- **Decision Latency Thresholds**:
  - Deterministic Heuristic Provider: $< 20$ ms (observed: $\approx 0.4$ ms).
  - Cloud LLM Provider (Anthropic Sonnet): $< 2000$ ms.
- **Failover Threshold**: Circuit breaker trips after 3 consecutive failures or timeouts ($> 2.0$s). Cooldown before probing is 30.0s.

### 4.2 Governance Invariants
- **Battery Floor**: 15% absolute floor below which task assignments are denied; 25% dispatch threshold where AMRs are proactively routed to chargers.
- **Zone Hold Cap**: Maximum 1 simultaneous zone hold allowed without supervisor escalation, preventing deadlocks from widespread aisle closures.
- **Human Approval Window**: 40–50 simulation ticks (4–5s) timeout window with deterministic default fallback (`deny`).

---

## 5. Resilience & Chaos Engineering Assumptions (Phase 6)

### 5.1 Pick Verification Model (SO-101)
- **Error Frequency**: $2.0\%$ baseline error probability across barcode scan and scale check (1.0% mismatch, 1.0% unverified/damaged barcode).
- **Physical Isolation**: A damaged or unreadable SKU is removed from pick stream immediately and cannot be packed into customer totes.
- **Retry Cost**: Single retry adds $1.5\text{s}$ (15 ticks) sensor re-scan delay.

### 5.2 Failure Taxonomy Time Constants (CA-8)
- **AMR Breakdown Detection (MTTD)**: Within $1.0\text{s}$ (10 ticks) via deadman position telemetry.
- **RF Telemetry Dropout**: Triggered after 3 consecutive missed heartbeat packets ($0.3\text{s}$ at 10 Hz).
- **Aisle Blockage Detection**: Vision / bumper alert within $0.2\text{s}$ (2 ticks).
- **Recovery Time Target (MTTR)**: Sub-$20\text{s}$ for autonomous algorithmic reassignment and rerouting.

### 5.3 Supervisor Queue & SLA Defaults
- **Supervisor Response Window**: $30\text{--}60\text{s}$ ($300\text{--}600\text{ ticks}$).
- **Safe Fallback Execution**: Guaranteed safe default triggers on timeout without blocking fulfillment pipeline.
- **Human Intervention Frequency**: $< 2.0$ interventions per 100 orders under nominal operating conditions.


