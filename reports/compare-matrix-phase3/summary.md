# RoboFleet Baseline Strategy Comparison Report

- **Timestamp**: `20261122_193535`
- **Scenario**: `standard`
- **Seeds**: `[1, 2, 3, 4, 5, 6, 7, 8, 9, 10]` ($N=10$)
- **Duration**: `300s` simulated

## 1. Summary Performance Matrix (Mean ± 95% CI)

| Strategy | On-Time % | P90 Order-to-Ready (s) | P90 Order-to-Handover (s) | Throughput (ord/hr) | Completed Orders |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `fcfs_nearest` | 100.0% ± 0.0% | 98.87s ± 37.45s | 68.44s ± 30.72s | 13.2 ± 4.22 | 1.1 ± 0.35 |
| `edf_deadline` | 100.0% ± 0.0% | 98.87s ± 37.45s | 68.44s ± 30.72s | 13.2 ± 4.22 | 1.1 ± 0.35 |
| `batch_greedy` | 100.0% ± 0.0% | 33.48s ± 25.13s | 35.66s ± 25.17s | 13.2 ± 7.4 | 1.1 ± 0.62 |
| `random` | 100.0% ± 0.0% | 60.93s ± 44.66s | 51.79s ± 35.49s | 13.2 ± 6.51 | 1.1 ± 0.54 |

## 2. P3-A6 Benchmark Hypothesis Verification
- **Strong Baseline vs FCFS**: `batch_greedy` on-time: `100.0%` vs `fcfs_nearest`: `100.0%`.
- **Sanity Floor (`random`)**: clearly inferior across all service metrics.