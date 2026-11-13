# Phase 1 — Dynamic Core and Realism Pack

Copy the text between the BEGIN and END markers into Claude Code. Run the build prompt first, then the review prompt in a **fresh** session.

---

=== BEGIN PHASE 1 BUILD PROMPT ===

# ROLE AND MISSION
You are the lead engineer for Phase 1 of 7 of RoboFleet. Build the **Dynamic Core**: a deterministic, configuration-driven digital twin of a robot-assisted dark store, with a rule engine, extension seams, evolvable contracts, a realistic data pack and a non-bypassable safety layer. It runs headless. There is no web server, UI or AI in this phase.

# READ FIRST
1. `docs/playbook/00-master-plan.md` (principles, Standing Rules SR-1 to SR-12, declared change axes CA-1 to CA-9). If the folder is missing, stop and tell the user.
2. `docs/playbook/01-review-protocol.md` (your work will be reviewed against it; build to pass it).

# HOW TO WORK
- Use GSD. Treat this prompt as the phase goal. Discuss assumptions first (SR-1), plan small tasks, execute, verify each. Run `/gsd:help` to confirm command names.
- Follow SR-1 to SR-12. In particular: simplicity first with the ponytail ladder; surgical changes; every task starts with a runnable check; no magic numbers in logic; no abstractions except declared seams.
- Commit atomically with conventional messages. Tag `phase-1-complete` only at the very end.
- Decisions go in `docs/DECISIONS.md`. Assumptions go in `docs/ASSUMPTIONS.md` with sources.

# PHASE GOAL (exit demo)
`python -m robofleet.cli run --scenario standard --duration 3600` runs 20 robots for one simulated hour in a realistic store with zero collisions and is bit-for-bit deterministic. Five "change drills" (below) pass, proving that layout, rules, robot count and strategies can be changed without touching code.

# NON-GOALS
No FastAPI, WebSockets, frontend, 3D, LLM calls, real order-to-robot fulfilment, picking logic or agents. Define interfaces and data shapes for later phases, and implement only the null/placeholder behaviour described here.

# SPECIFICATION

## A. Bootstrap
- Create the layout in section 5 of the master plan (only the folders needed now).
- Python 3.12+, `uv` (fallback pip), `pyproject.toml`, `Makefile` (setup, lint, typecheck, test, run, schemas, drills), ruff, mypy `--strict` on `src`, pytest, hypothesis, pytest-cov. Runtime deps: `pydantic>=2`, `pyyaml`, `numpy`. Nothing else without a recorded reason.
- Install/prepare: GSD, Karpathy guidelines, ponytail (SR-12 caution about permission-skipping applies).
- Write `CLAUDE.md` containing SR-1 to SR-12 verbatim, the commands, and the declared change axes.
- Create four Agent Skills under `.claude/skills/` (frontmatter `name`, `description`; short body):
  - `robofleet-conventions`: coding conventions, SR summary, how to run checks.
  - `robofleet-add-extension`: step-by-step for adding a seam implementation (Protocol, registry, config key, example, test).
  - `robofleet-contract-change`: procedure for additive vs breaking schema changes (bump, migrate, changelog, review).
  - `robofleet-review`: runs `docs/playbook/01-review-protocol.md` for a named phase (read-only, writes `reviews/phase-N-review.md`).

## B. Config system (CA-1, CA-4)
- Pydantic v2 config models, layered: `defaults.yaml` < scenario YAML < environment variables (`ROBOFLEET_*`) < CLI `--set key=value`.
- Validation errors must name the field path and the allowed values.
- `config explain --scenario X` prints every effective value with its origin layer.
- Structural settings (layout, robot count at start) need a restart. Tunables (rates, thresholds, rules) may be hot-reloaded where the engine can do so safely; document which is which in `docs/CONFIG.md`.
- JSON Schema of the config is exported to `contracts/jsonschema/config.schema.json`.
- `tools/magic_numbers.py`: flags numeric or string literals in `src/` outside `config/`, tests and an explicit allowlist file (with a comment per entry). Runs in `make lint`.

## C. Registry and ports (declared seams only)
- A small generic `Registry[T]`: `register(name, factory)`, `create(spec)` where `spec = {type: name, params: {...}}`, validated against the factory's param model, with a helpful error listing known names.
- Protocols (each with a null or example implementation and a test): `WorldGenerator` (CA-1), `CatalogueSource` (CA-2), `OrderSource` (CA-2, null only now), `MovementPlanner`, `TaskDispatcher` (CA-5), `Constraint` (CA-3), `MetricProvider` (CA-7), `FaultInjector` (CA-8), `Brain` (CA-6, null only now), `EventSink`.
- Do not add any other abstraction layer.

## D. Rule engine (CA-3)
Declarative rules in YAML, one engine used for placement constraints, movement-zone restrictions and alert rules now, and for AI-command gating in Phase 5.
- Rule fields: `id`, `description`, `scope` (placement | movement | alert | command), `when` (condition), `effect` (deny | warn | require_human | alert | score_penalty), `severity`, `params`, `enabled`, `version`.
- Conditions are structured dicts (`all`/`any`/`not`, `field`, `op`, `value`) evaluated by a small function (about 50 lines). No eval. Field paths resolve against a typed context object.
- Commands: `rules lint` (schema and field-path validation), `rules test <file>` (runs table-driven cases embedded in the rule file), `rules list`.
- Ship starter rules in `rules/`: temperature-zone match for placement; heavy items not on the top shelf level; chemical-cleaning items not near perishables; capacity/weight limits; robot-waiting-too-long alert; low-battery alerts; keep-out zone for movement (supervisor area). Each has embedded test cases.
- Hot reload of `rules/` on file change in `run` mode, emitting `rules.reloaded` events. Invalid rule files must be rejected without disturbing the running rule set.

## E. Contracts (SR-6)
- Pydantic v2 models in `contracts/` with no imports from `sim/`. `schema_version` follows SemVer, starting `1.0.0`. Top-level payloads carry `meta.environment = {mode: "digital_twin", data_source: <string>, robot_layer: "simulated"}` (the Environment panel in Phase 2 reads this).
- Static vs dynamic split: `StaticWorld` (sent once: layout, catalogue, bins, stations, chargers, config summary) and `DynamicState` (every update: robots, orders, alerts, blocked cells, station state, KPIs, tick, seq). `WorldSnapshot` = both.
- Models to define fully now (even if unused until later): `Order`, `OrderLine`, `Task`, `Command` variants, `Event` (discriminated union on `type`), `Alert`, `Robot`, `Station`, `Charger`, `Bin`, `Sku`, `Layout`, `Cell`, `Decision` (for Phase 5).
- Extensibility: payloads include an optional free-form `ext: dict` where later features may attach data without a schema bump. Clients must ignore unknown fields.
- `tools/schema_compat.py`: compares committed schemas to the current models and classifies the change as none/patch/minor/breaking; CI fails if the classification exceeds the declared version bump. A `migrate(payload, from_version, to_version)` registry exists (empty but tested).
- `export-schemas` writes JSON Schemas plus example payloads; a test fails on undeclared drift. Maintain `contracts/CHANGELOG.md`.

## F. World model (CA-1)
- Grid of square cells, 1 cell = a configurable size in metres. Origin top-left; x east; y south. Headings N,E,S,W (N is y-1).
- Time is an integer tick count; `tick_hz` configurable; `sim_time_ms` derived. Never read the wall clock inside the core.
- Determinism: one root seed; independent named random streams via `numpy.random.SeedSequence`; adding a stream never changes existing ones; sorted-ID iteration; `state_hash(world)` = SHA-256 of canonical JSON of the dynamic state.
- Cell types: WALL, FLOOR, SHELF, STATION, PACK, DISPATCH, SUPERVISOR_DESK, CHARGER, PARKING. Each walkable cell has a `flow` (BOTH or allowed exit headings).
- **Layouts are data.** Provide (a) a parametric generator (grid size, rack rows, rack length, aisle width, cross-aisle width, rack levels, counts of stations/packs/chargers/parking, right-hand traffic on or off) and (b) a loader for hand-drawn ASCII layout files with a legend. Both produce the same `Layout` contract and pass the same validator.
- Validator (runs automatically): directed graph strongly connected under flow rules; every shelf has an access cell; every station has a connected queue; chargers, parking and dispatch reachable and not blocked in; counts match; parking at least robot count plus a configurable margin. Errors are specific.
- Zones are named regions in config (for example "storage-west", "supervisor-area") used by rules and, later, by commands like "pause zone C".
- Presets shipped as YAML: `small` (10 robots), `standard` (20 robots), `large` (50 robots). Exact geometry is your design; the standard store must look like a plausible compact dark store (see G for sizing research). Produce ASCII renders in `docs/LAYOUT.md`.

## G. Realism pack (CA-2)
Research first, then build. Use web search to find typical figures for Indian quick-commerce dark stores and grocery baskets: store area, SKU count, items per order, order value, delivery promise, daily order volume, peak patterns. Record each figure with source URL, date and confidence in `docs/ASSUMPTIONS.md`; mark anything you could not source as "engineering estimate". Parameters elsewhere must reference these assumption IDs in comments.
- **Catalogue:** `catalogue.sku_count` configurable (default about 1,500, supports up to 6,000). Brand-neutral, realistic product names with pack sizes (for example "Toned Milk 500 ml", "Whole Wheat Bread 400 g") across: dairy, bakery, fruit and vegetables, snacks, beverages, staples, household, personal care, frozen, baby, pet. Fields: `sku_id`, `name`, `category`, `pack_size`, `mrp_inr`, `popularity_rank`, `size_class`, `fragile`, `handling_difficulty`, `unit_weight_g`, `dimensions_mm`, `temperature_class` (ambient/chilled/frozen), `shelf_life_days`, `hazard_class` (none/chemical). No placeholders.
- **Affinities:** a seeded co-purchase matrix (for example bread with butter and eggs) so later baskets look real.
- **Demand profile files** in `profiles/`: hourly multipliers, weekday/weekend, and overlays (rain, match night, festival evening, payday). These are consumed by the Phase 2 demand engine; in Phase 1 only the loader and schema exist, with tests.
- **Bins and slotting:** each SHELF cell holds N levels (configurable); each level is a bin with id `BIN-x-y-Lk`, one SKU, quantity, capacity. Static slotting uses the rule engine: apply placement rules as hard constraints, then a popularity-times-proximity score; top-K popular SKUs get replica bins in different aisle segments; about 5 percent of bins start empty. `inventory.locate(sku_id)` exists.
- Everything above is generated deterministically from the seed and also loadable from user files (CSV/JSON) through `CatalogueSource` adapters (`generated`, `csv`).

## H. Simulation core
- **Robots:** `robot_id` (R-001...), `kind` (config-defined; one kind ships), `cell`, `heading`, `state` (IDLE, MOVING, WAITING, CHARGING, UNAVAILABLE; reserve PICKING and others), `battery_pct`, `motion` (from_cell, to_cell, progress as integer per-mille), `current_task_id`, `carrying`, `blocked_ticks`, `fault`.
- **Motion:** cell to cell. Crossing time and turn time derived from configurable speed, cell size and turn cost. A moving robot reserves both its current and next cell, so sharing and swapping are impossible by construction.
- **Tick order (contract, document it):** 1 apply queued commands; 2 brain (null); 3 order source (null); 4 dispatcher; 5 planner proposes move intents; 6 SafetyGuard validates and commits; 7 update motion, battery, state; 8 evaluate alert rules; 9 emit events; advance tick.
- **SafetyGuard:** the only code allowed to change a robot's cell. Enforces walkable, unblocked, unoccupied, unreserved destination; flow direction; no sharing or swapping; emergency stop (all, robot, or zone); UNAVAILABLE robots stay put and act as obstacles. Emits `safety.move_denied` with a reason code. Raises `SafetyViolation` if an invariant is ever broken. Its parameters come from config (changes are logged).
- **Planner (placeholder, registry name `astar_flow`):** A* on the directed flow graph; priority by longest wait then robot id; replan after a configurable wait with seeded jitter; yield move after a longer wait; deadlock incident counted and raised as a CRITICAL alert after a still longer wait. All thresholds are config.
- **Dispatcher (placeholder, `wander`):** keeps robots busy by sending idle robots to random reachable destinations (bin access cells, station queues, pack points, dispatch bay, parking) with seeded dwell time. Clearly labelled as a placeholder.
- **Battery:** configurable drain by state, charge rate and thresholds; initial charge seeded; robots seek the nearest free charger below the low threshold; alerts via rules.
- **Hooks (implemented now, used later):** `inject_fault`, `clear_fault`, `block_cells`, `unblock_cells`, `emergency_stop`, `resume`, all queued commands applied at tick step 1 and logged.
- **Alerts:** produced by the rule engine from state; fields: `alert_id`, `severity`, `category`, `message`, `entity_ids`, `cell`, `raised_tick`, `resolved_tick`, `requires_human`, `auto_resolved`. They auto-clear when the condition ends.
- **Events:** append-only, strictly increasing `seq`, with `tick`, `sim_time_ms`, `type`, `payload`. Emit: sim lifecycle, robot state changes and arrivals, replans, battery and charge events, faults, safety denials, e-stop and resume, blocked and unblocked cells, alert raised and cleared, `rules.reloaded`. Reserve (do not emit) the order, task, inventory and `ai.decision` types. Do not log every cell step.

## I. CLI and tools
`python -m robofleet.cli` with: `run`, `render` (ASCII), `validate-layout`, `export-schemas`, `hash`, `config explain`, `rules lint|test|list`, `drills` (runs the five change drills in a temp copy and reports files touched). `run` writes `events.ndjson`, `final_snapshot.json` and `metrics.json` (collisions, deadlocks, distance, per-robot utilisation, denials by reason, final hash, wall-clock seconds, sim-seconds per wall-second) into `runs/`. Optional `tools/heatmap.py` for a congestion PNG.

## J. Documentation
`README.md`, `CLAUDE.md`, `docs/ARCHITECTURE.md`, `CONFIG.md`, `CONTRACTS.md`, `EXTENDING.md` (how to do each change axis in the fewest steps), `LAYOUT.md`, `ASSUMPTIONS.md`, `DECISIONS.md`, `PHASES.md`, `THIRD_PARTY.md`, `phase1-report.md`.

# CHANGE DRILLS THIS PHASE MUST PASS (and document in EXTENDING.md)
- **CD-1:** add a new placement rule and a new alert rule in YAML only, with embedded test cases. 0 code files.
- **CD-2:** add a new zone, change robot count and grid size via config only. 0 code files.
- **CD-3:** add a new event type. At most 3 files plus docs.
- **CD-4:** swap the catalogue source from `generated` to `csv` via config. 0 code files.
- **CD-5:** register a new planner or dispatcher strategy. At most 2 files plus config.

# ACCEPTANCE CRITERIA
- **P1-A1** All three presets generate, validate and render; ASCII maps are in `docs/LAYOUT.md`; a hand-drawn ASCII layout also loads and validates.
- **P1-A2** Catalogue has at least the configured SKU count; zero placeholder names (automated check); every SKU stocked in at least one bin; popular SKUs are measurably closer to stations on average than unpopular ones (test with numbers); placement rules reject violating placements (tests).
- **P1-A3** Rule engine: `rules lint` and `rules test` pass on shipped rules; invalid rule file is rejected without disturbing the running set (test); hot reload works (test).
- **P1-A4** Config: layering order proven by tests; `config explain` shows origins; bad config gives path-specific errors; magic-number scan passes.
- **P1-A5** Contracts: JSON Schemas committed; schema drift test and `schema_compat` pass; examples validate; snapshot round-trips; unknown fields are tolerated; migration registry tested.
- **P1-A6** Determinism: same scenario and seed gives identical hashes at ticks 100, 1000 and final across two runs; different seed differs.
- **P1-A7** Standard preset, 20 robots, 3600 simulated seconds: zero `SafetyViolation`, zero shared cells, zero swaps, verified every tick by an independent test-side checker, not by the SafetyGuard.
- **P1-A8** Standard run has zero unresolved deadlock incidents; the large preset (50 robots, at least 1800 s) has zero safety violations and any deadlocks resolved, with the count reported.
- **P1-A9** Every robot visits at least 20 distinct destinations in the standard run.
- **P1-A10** Emergency stop (all, single robot, zone) halts within one tick and holds until resume (tests). Blocked cells are avoided and routing continues. Faulted robots stay as obstacles and raise alerts.
- **P1-A11** Battery cycle works: robots charge; none reaches 0 percent in the standard run (if one does, fix the dispatcher; do not hide it).
- **P1-A12** Hypothesis properties: random valid layout parameters give a valid layout or a clear error; random command sequences never cause a safety violation.
- **P1-A13** Quality: ruff, ruff format check, mypy strict and pytest pass; coverage of `sim/`, `layout/`, `contracts/`, `rules/` at least 85 percent.
- **P1-A14** Performance measured and reported: target the standard hour in under 120 s and the large 30-minute run in under 5 minutes on a normal laptop. If missed, profile, fix hotspots, and report real numbers either way.
- **P1-A15** The five change drills pass via `make drills`, with files-touched counts recorded.
- **P1-A16** Four project Agent Skills exist with valid frontmatter and work when invoked.
- **P1-A17** `docs/ASSUMPTIONS.md` has sourced entries (URL, date, confidence) for store size, SKU count, basket size, order volume and delivery promise; unsourced items are labelled as estimates.
- **P1-A18** All documents in J exist and are accurate; every documented command runs as written.

# FINAL REPORT
Write `docs/phase1-report.md` and print it: each criterion PASS/FAIL with evidence, measured numbers, decisions and deviations with reasons, known limitations, and handoff notes for Phase 2 (how to run a scenario, where the seams are, what Phase 2 should build first). Then stop. Do not start Phase 2.

=== END PHASE 1 BUILD PROMPT ===

---

=== BEGIN PHASE 1 REVIEW PROMPT ===

# ROLE
You are an independent, strict reviewer of Phase 1 of RoboFleet. You are read-only. You may write only `reviews/phase-1-review.md`. Do not fix anything.

# READ FIRST
`docs/playbook/00-master-plan.md`, `docs/playbook/01-review-protocol.md` (apply it in full: Step 0 freshness, universal checks U1 to U12, change drills, severity, mechanical verdict rules, worth-it assessment, output template), and `docs/phase1-report.md` (treat it as claims to verify, not as truth).

# PHASE 1 ACCEPTANCE CRITERIA TO VERIFY
Verify P1-A1 to P1-A18 from the Phase 1 build prompt, by running the commands yourself. Re-measure P1-A7, P1-A8 and P1-A14 yourself; do not copy the report's numbers.

# PHASE-SPECIFIC CHECKS
- **P1-R1 Independent safety checker.** Write your own invariant checker (separate from the builder's) and run it over the standard 3600 s run, the large 1800 s run, and a randomised fuzz of fault, block and e-stop commands with at least 10 different seeds. Any shared cell, swap, off-grid or flow-violating move is a P0.
- **P1-R2 SafetyGuard exclusivity.** Prove by grep and reading that nothing other than the SafetyGuard mutates a robot's cell, and that planners and dispatchers only return intents or commands.
- **P1-R3 Determinism leaks.** Search for wall-clock reads, unseeded randomness, dict or set iteration affecting results, floating-point accumulation in authoritative state. Run the hash test on a second Python version or machine if available.
- **P1-R4 Rule engine robustness.** Attempt injection and abuse: malformed conditions, unknown fields, deeply nested rules, huge rule files, rules referencing missing context fields. It must fail safely with clear errors and never use `eval` or execute code.
- **P1-R5 Dynamism, for real.** Perform CD-1 to CD-5 yourself on a scratch branch. Also try three unplanned changes of your own (for example: change aisle width, add a second robot kind in config, add a rule that restricts a zone during a time window). Report what required code changes and why.
- **P1-R6 Contract evolution.** Make a deliberate additive change and a deliberate breaking change on a scratch branch; confirm `schema_compat` classifies each correctly and the breaking one fails CI without a bump and migration.
- **P1-R7 Realism.** Sample 100 random SKUs: names, pack sizes, MRP in INR, temperature classes and dimensions must look plausible and internally consistent (a chilled item must not be slotted in an ambient bin; a 20 kg item must not be on the top level). Count placeholder-like names. Check the demand profiles produce plausible peaks. Check every `ASSUMPTIONS.md` URL actually supports the cited value (open at least five). Flag fabricated or unsupported sources as P1, or P0 if presented as fact.
- **P1-R8 Layout quality.** Inspect the ASCII maps: does the standard store look like a plausible compact dark store with sensible flow? Are queue lanes, charger access and the supervisor keep-out sensible? Try to create a layout that should be invalid; the validator must catch it.
- **P1-R9 Config discipline.** Run the magic-number scan, then manually inspect the allowlist for abuse. Pick ten tunables and confirm each is reachable via config and documented.
- **P1-R10 Agent Skills.** Open each of the four skills; validate frontmatter, descriptions that make them discoverable, and bodies that match reality. Invoke `robofleet-review` on a trivial dry run if possible.
- **P1-R11 Simplicity audit.** List every Protocol and registry and confirm each maps to a declared change axis with at least one real implementation and one test. Estimate deletable lines.
- **P1-R12 Product feel foundation.** Confirm `meta.environment` exists and is accurate, and that no user-visible strings contain placeholder text.

# CHANGE DRILLS FOR THIS PHASE
CD-1, CD-2, CD-3, CD-4, CD-5 (limits as in the protocol).

# PHASE 1 WORTH-IT QUESTIONS (answer in the worth-it section)
1. Is this foundation truly dynamic, or only dynamic where the builder expected change? Name the three most likely future changes that would still hurt.
2. Is the realism pack credible enough that a sceptical operations person would accept the store as plausible?
3. Is the SafetyGuard design strong enough to hold when Phase 3 introduces real traffic and Phase 5 introduces AI commands?
4. Did the builder over-engineer? What should be cut?
5. What must change before Phase 2 starts?

# OUTPUT
Follow the output template in the review protocol exactly. Finish with the change list and a suggested ordered GSD task list. State the verdict using the mechanical rules.

=== END PHASE 1 REVIEW PROMPT ===
