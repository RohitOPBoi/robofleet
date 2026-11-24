# RoboFleet

AI-led operations command centre and digital twin for robot-assisted dark stores.

## Standing Rules (SR-1 to SR-12)

**SR-1 Think before coding (Karpathy 1).** State assumptions, surface ambiguity and trade-offs, and record non-obvious choices in `docs/DECISIONS.md` before implementing. Push back on this prompt if something is wrong.

**SR-2 Simplicity first (Karpathy 2 + ponytail).** Before writing code, stop at the first rung that holds: (1) does this need to exist? skip it; (2) already in the codebase? reuse it; (3) stdlib or platform does it? use it; (4) a small, well-known dependency does it? only then add one. No abstractions except declared seams (3.2).

**SR-3 Surgical changes (Karpathy 3).** Touch only what the task requires. No drive-by refactors or reformatting. Every changed line traces to a requirement or a review finding.

**SR-4 Goal-driven execution (Karpathy 4).** Every task starts with a verifiable check (test, command, or measurable output). Loop until it passes. Never weaken a test or threshold to pass.

**SR-5 Dynamic by design.** Obey section 3.1. A magic-number scan (`tools/magic_numbers.py`, allowlist-based) runs in CI from Phase 1.

**SR-6 Evolvable contracts.** Obey section 3.1 point 6. Maintain `contracts/CHANGELOG.md`.

**SR-7 Safety boundary.** Obey section 3.3. The SafetyGuard is the only code that may change a robot's cell. It enforces non-negotiable physical invariants (no shared cells, no swaps, flow rules, emergency stop). Agents and policies cannot bypass it.

**SR-8 Evidence over claims.** Nothing is "done" without command output or an artifact. Report failures plainly with real numbers. Never fabricate results, screenshots or metrics.

**SR-9 Product feel.** Obey section 2. No placeholder text in any user-visible surface. Units, currency (INR), time formats and naming must be consistent and realistic.

**SR-10 Agent Skills.** Repeatable procedures live as Agent Skills in `.claude/skills/<name>/SKILL.md` (frontmatter with `name` and `description`, short body). Phase 1 creates: `robofleet-conventions`, `robofleet-add-extension`, `robofleet-contract-change`, `robofleet-review`.

**SR-11 Workflow and git discipline (GSD).** Work phase by phase using Get Shit Done: plan, execute, verify. Keep each task small enough to finish within a healthy context window. Atomic commits with conventional messages. Tag the end of each phase `phase-N-complete` only after its review verdict is GO or GO-WITH-CHANGES with all P0/P1 items fixed.

**SR-12 Sandbox and secrets.** GSD is designed to run with permission prompts skipped. Do that only in a disposable environment with no secrets. Never commit API keys. Maintain `.env.example`. Never reuse code from a repo without a visible permissive licence.

---

## Declared Change Axes (CA-1 to CA-9)

- **CA-1**: World layout and zones (`WorldGenerator`, ASCII loader, zone configs)
- **CA-2**: Catalogue and data sources (`CatalogueSource`, `OrderSource` adapters)
- **CA-3**: Rules, constraints and policies (YAML rule engine, placement, alert, movement, command)
- **CA-4**: Robot kinds and parameters (Robot config specs, physics, capacities)
- **CA-5**: Planners, dispatchers and baseline strategies (`MovementPlanner`, `TaskDispatcher`)
- **CA-6**: Agents, tools and LLM providers/models (`Brain`, `LLMProvider`)
- **CA-7**: KPIs and metrics (`MetricProvider`, delay attribution)
- **CA-8**: Scenarios and fault types (`FaultInjector`, chaos definitions)
- **CA-9**: UI panels, widgets and themes (Panels registry, camera configs, asset registry)

---

## Commands

- Setup: `make setup`
- Lint: `make lint`
- Typecheck: `make typecheck`
- Test: `make test`
- Run simulation: `python -m robofleet.cli run --scenario standard --duration 3600`
- Export schemas: `make schemas`
- Run change drills: `make drills`
