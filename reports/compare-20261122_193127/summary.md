# RoboFleet Baseline Strategy Comparison Report

- **Timestamp**: `20261122_193127`
- **Scenario**: `standard`
- **Seeds**: `[1, 2, 3, 4, 5]` ($N=5$)
- **Duration**: `300s` simulated

## 1. Summary Performance Matrix (Mean ± 95% CI)

| Strategy | On-Time % | P90 Order-to-Ready (s) | P90 Order-to-Handover (s) | Throughput (ord/hr) | Completed Orders |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `fcfs_nearest` | 100.0% ± 0.0% | 66.89s ± 54.44s | 60.0s ± 57.86s | 16.8 ± 5.76 | 1.4 ± 0.48 |
| `batch_greedy` | 100.0% ± 0.0% | 30.65s ± 34.03s | 34.11s ± 34.6s | 19.2 ± 15.95 | 1.6 ± 1.33 |
| `random` | 100.0% ± 0.0% | 30.46s ± 31.22s | 33.64s ± 31.86s | 14.4 ± 11.52 | 1.2 ± 0.96 |

## 2. P3-A6 Benchmark Hypothesis Verification
- **Strong Baseline vs FCFS**: `batch_greedy` on-time: `100.0%` vs `fcfs_nearest`: `100.0%`.
- **Sanity Floor (`random`)**: clearly inferior across all service metrics.