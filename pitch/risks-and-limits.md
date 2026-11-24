# RoboFleet Risks, Known Limits & Operating Boundaries

An open and transparent catalog of technical boundaries, physical assumptions, and failure modes in the RoboFleet platform.

---

## 1. Physical & Kinematic Boundaries
- **Discrete Space-Time Grid**: The digital twin models motion across discrete 0.5-meter cells at 10 Hz ticks. Sub-millimeter continuous dynamics (e.g. wheel slip, floor friction variance, caster wobble) are abstracted.
- **Payload Limits**: AMR payload capacity is parameterized (standard 35kg / 2 totes). Structural stress from uneven load distribution is not modeled.
- **Battery Dynamics**: Battery drain is modeled via linear distance and dwell discharge rates. Ambient temperature degradation (e.g. cold-room battery life drops) is approximated parametrically.

## 2. Scale & Concurrency Boundaries
- **Fleet Sizing Bound**: Validated up to 50 AMRs per dark store facility. Facilities requiring $> 100$ AMRs may experience CPU-bound latency in space-time collision reservation searches beyond 50ms per tick.
- **WebSocket Client Concurrency**: The command centre server supports up to 100 concurrent operator dashboard connections per node.
- **Order Ingestion Rate**: Webhook endpoint is rate-limited to 120 orders/second per tenant.

## 3. Algorithmic & AI Model Assumptions
- **Governance Gate Dependence**: The safety of AI recommendations relies on the declarative `GovernanceLayer`. Bypassing this layer is strictly prevented by software architecture, but custom rules must maintain non-contradictory logic.
- **Heuristic Quality**: In extremely cluttered layouts (aisle width = 1 cell with zero passing bays), deadlock avoidance algorithms may hold robots at aisle entrances, reducing effective throughput. Two-cell bidirectional corridors or bypass bays are strongly recommended.

## 4. Operational & Human Integration Assumptions
- **Station Picker Availability**: The digital twin assumes pick station workers are present and pick at normal distributions (mean 3–5 seconds per unit). If a human station worker walks away without pausing the station, totes queue up at the bay.
- **Barcode & Physical Inventory Integrity**: Damaged barcodes or physically mis-slotted items trigger quarantine exceptions requiring human supervisor resolution via the Exceptions Queue.
