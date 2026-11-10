# RoboFleet Configuration Guide

## Layering Precedence
Configuration is evaluated in strict order from lowest to highest priority:
1. `scenarios/defaults.yaml`
2. `scenarios/<scenario>.yaml` (specified via `--scenario <name>`)
3. Environment variables: `ROBOFLEET_<KEY_PATH>` (e.g., `ROBOFLEET_ROBOT_COUNT=30`, `ROBOFLEET_TIMING__TICK_HZ=20`)
4. CLI overrides: `--set key.path=value` (e.g. `--set layout.preset=large`)

## Structural vs Tunable Settings

### Structural Settings (Require Process Restart)
- `layout.*`: Grid dimensions, rack rows, cell sizes, and static station counts.
- `robot_count`: Initial AMR spawn count.
- `catalogue.sku_count`: Initial catalogue population size.

### Tunable Settings (Hot-Reloadable / Dynamic)
- `timing.tick_hz`: Wall-clock pacing and frequency.
- `battery.*`: Battery thresholds and charge rates.
- `rules.rules_dir`: Declarative YAML rules reloaded on file change without restarting.
- `planner.params.*`: Replanning and deadlock wait thresholds.
- `dispatcher.params.*`: Dwell timings.

## Explaining Configuration
Run:
```bash
python -m robofleet.cli config explain --scenario standard
```
This prints every effective configuration value alongside its origin layer (`defaults`, `scenario`, `env`, or `cli`).
