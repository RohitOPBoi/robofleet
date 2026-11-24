# RoboFleet Order Adapters Architecture (CA-2)

## 1. Overview

RoboFleet decouples order generation from simulation execution through the `OrderSource` port protocol. Three distinct adapters implement this interface and can be selected purely through configuration without modifying any simulation code.

```
+-----------------------------------------------------------------+
|                      OrderSource Protocol                       |
|   poll_orders(current_tick: int) -> list[Order]                 |
+-----------------------------------------------------------------+
         ^                              ^                    ^
         |                              |                    |
+------------------+         +--------------------+   +---------------+
|  demand_engine   |         |     csv_replay     |   |    webhook    |
| (Synthetic Model)|         | (Historical Replay)|   | (REST Ingest) |
+------------------+         +--------------------+   +---------------+
```

---

## 2. Adapters

### 2.1 Synthetic Demand Engine (`demand_engine` — Default)
- **Mathematical Basis**: Non-homogeneous Poisson arrival process parameterized by hourly diurnal curves from `profiles/*.yaml`.
- **Basket Sampling**:
  - Basket sizes follow a Poisson distribution with configurable mean ($\mu = 4.2$, bounded $[1, 12]$).
  - SKU selection uses catalog popularity scores weighted by the empirical co-purchase affinity matrix generated in Phase 1.
  - Ensures all ordered SKUs exist and have active inventory.
- **SLA & Priority**:
  - SLA tiers: `standard` (75%), `express` (20%), `scheduled` (5%).
  - Express orders receive priority 5 and tighter deadline windows (e.g. 20 simulated minutes).
  - Orders nearing deadline within `orders.at_risk_threshold_ticks` are tagged `at_risk=True` and trigger `order.at_risk` events.
- **Dynamic Overlays**:
  - `rain`: $+50\%$ arrival rate multiplier for 2 hours.
  - `match_night`: $+120\%$ arrival rate multiplier for 3 hours.
  - `rush`: $+150\%$ arrival rate burst for 5 minutes.

### 2.2 CSV Replay Adapter (`csv_replay`)
- **Use Case**: Replaying historical operational logs or customer-provided order traces.
- **File Format**: Standard CSV with header:
  ```csv
  order_id,arrival_tick,sku_ids,quantities,priority,deadline_tick
  ORD-001,10,SKU-0001;SKU-0005,1;2,1,500
  ```
- **Validation**:
  - Strictly validates row integrity: matching lengths between `sku_ids` and `quantities`, positive quantities, deadline strictly greater than arrival tick.
  - Immediate clear error reports naming row number and invalid column.

### 2.3 Webhook Ingest Adapter (`webhook`)
- **Use Case**: Real-time integration with external ERP or WMS platforms via HTTP POST.
- **Endpoint**: `POST /api/ingest/orders`
- **Security & Idempotency**:
  - Requires Bearer authentication with `ROBOFLEET_TOKEN`.
  - Idempotency enforced via in-memory deduplication index on `order_id`. Duplicate order submissions return `409 Conflict`.
  - Token-bucket rate limiter caps ingestion at configurable rate (default 50 orders/sec). Bursts exceeding limit return `429 Too Many Requests`.
- **Payload Schema**:
  ```json
  {
    "order_id": "ORD-LIVE-9042",
    "lines": [
      {"sku_id": "SKU-0012", "quantity": 2},
      {"sku_id": "SKU-0089", "quantity": 1}
    ],
    "priority": 3,
    "deadline_tick": 1800,
    "sla_tier": "express"
  }
  ```

---

## 3. Switching Adapters via Config (CD-4)

To switch between adapters, no code edits are required. Simply update `scenarios/*.yaml` or supply command-line overrides:
```bash
# Run with CSV replay
python -m robofleet.cli serve --set orders.adapter=csv_replay --set orders.csv_file=scenarios/sample_orders.csv

# Run with Webhook Ingest
python -m robofleet.cli serve --set orders.adapter=webhook
```
