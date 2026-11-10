# RoboFleet

AI-led operations command centre and digital twin for robot-assisted dark stores.

## Overview
RoboFleet runs a dark store from order arrival to dispatch handoff, shows it live in 2D and 3D, and keeps the human supervisor in an oversight and exception-handling role.

## Architecture Principles
1. **Dynamic Core**: Config over constants, rules as data, registries over conditionals.
2. **Safety Boundary**: Non-bypassable `SafetyGuard` enforces physical invariants.
3. **Reproducible Truth**: Bit-for-bit deterministic simulation with named seed streams.
4. **Realism Pack**: Indian quick-commerce metro catalogue (1,500+ SKUs in INR) with realistic diurnal demand curves.

## Quickstart
```bash
# Setup development environment
uv venv --python 3.12
uv pip install -e ".[dev]"

# Run tests & lint
make lint
make test

# Run Phase 1 standard simulation (20 robots, 1 hour simulated)
python -m robofleet.cli run --scenario standard --duration 3600
```
