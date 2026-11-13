# RoboFleet Roadmap

## Phase 1: Dynamic Core and Realism Pack
- [ ] 01-bootstrap: Setup repo structure, pyproject.toml, Makefile, toolchain (ruff, mypy, pytest), CLAUDE.md, and 4 agent skills.
- [ ] 02-contracts: Define Pydantic v2 core contracts (StaticWorld, DynamicState, Layout, Robot, Order, Event, Alert, Sku, Bin) with SemVer, `meta.environment`, and schema exporter.
- [ ] 03-config-and-registry: Layered config system (defaults < scenario < env < CLI), generic Registry[T], and magic numbers checker.
- [ ] 04-rule-engine: Declarative YAML rule engine (placement, movement, alert) with embedded tests, `rules lint/test/list`, and hot reload.
- [ ] 05-world-and-layout: World grid model, parametric generator, ASCII layout loader, graph connectivity validator, and standard/small/large presets with ASCII renders in docs.
- [ ] 06-realism-pack: Indian quick-commerce catalogue (1,500+ realistic SKUs, INR, categories, temperature/hazard classes), affinities matrix, demand profile schemas, and bin slotting with hard constraints.
- [ ] 07-sim-core: Tick loop, non-bypassable SafetyGuard (exclusive mover), battery dynamics, A* flow planner, wander dispatcher, event logging, and state hash.
- [ ] 08-cli-and-drills: CLI suite (`run`, `render`, `validate-layout`, `export-schemas`, `hash`, `config explain`, `rules`, `drills`) and verify CD-1 through CD-5 pass.
- [ ] 09-verification-and-report: Run 3600s exit demo with 20 robots (0 collisions, deterministic), run property tests (Hypothesis), write docs and `docs/phase1-report.md`.
