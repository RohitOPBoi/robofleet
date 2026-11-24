# RoboFleet Customer Data Calibration Report

- **Input File**: `examples\customer_orders_sample.csv`
- **Calibrated At**: `2026-11-22T21:43:42.321315+00:00`
- **Rows Processed**: 527
- **Valid Lines Retained**: 527
- **Anomalies Detected**: 0

## 1. Fitted Operational Parameters

| Parameter Domain | Metric | Calibrated Value | Notes |
|---|---|---|---|
| Demand Arrival | Poisson Mean Rate | `10.46 orders/hr` | Average diurnal arrival rate |
| Demand Arrival | Diurnal Peak Hour | `Hour 17:00` | 8.8% of daily volume |
| Basket Size | Mean Units/Order | `2.55 +/- 1.55` | Median: 2.0, P90: 5.0 |
| Catalogue | Unique SKUs | `50` | Total volume: 641 units |
| Catalogue | Top 20% SKU Share | `55.4%` | Adherence: Moderate |

## 2. Diurnal Arrival Profile (24h Normalized Curve)

```json
[
  0.012,
  0.012,
  0.012,
  0.012,
  0.012,
  0.012,
  0.0319,
  0.0319,
  0.0319,
  0.0319,
  0.0319,
  0.0319,
  0.0558,
  0.0558,
  0.0558,
  0.0558,
  0.0558,
  0.0876,
  0.0876,
  0.0876,
  0.0876,
  0.0359,
  0.0359,
  0.0359
]
```

## 3. Data Integrity & Anomaly Summary

Zero data anomalies detected. Perfect input conformity.
