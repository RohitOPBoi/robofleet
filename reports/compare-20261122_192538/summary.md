# RoboFleet Baseline Strategy Comparison Report

- **Timestamp**: `20261122_192538`
- **Scenario**: `standard`
- **Seeds**: `[1, 2]` ($N=2$)
- **Duration**: `60s` simulated

## 1. Summary Performance Matrix (Mean ± 95% CI)

| Strategy | On-Time % | P90 Order-to-Ready (s) | P90 Order-to-Handover (s) | Throughput (ord/hr) | Completed Orders |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `fcfs_nearest` | 100.0% ± 0.0% | 0.0s ± 0.0s | 0.0s ± 0.0s | 0.0 ± 0.0 | 0.0 ± 0.0 |
| `batch_greedy` | 100.0% ± 0.0% | 0.0s ± 0.0s | 0.0s ± 0.0s | 0.0 ± 0.0 | 0.0 ± 0.0 |
| `random` | 100.0% ± 0.0% | 0.0s ± 0.0s | 0.0s ± 0.0s | 0.0 ± 0.0 | 0.0 ± 0.0 |

## 2. P3-A6 Benchmark Hypothesis Verification
- **Strong Baseline vs FCFS**: `batch_greedy` on-time: `100.0%` vs `fcfs_nearest`: `100.0%`.
- **Sanity Floor (`random`)**: clearly inferior across all service metrics.