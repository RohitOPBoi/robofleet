# RoboFleet Playbook — 00 Master Plan

Put this whole folder in your repo at `docs/playbook/`. Every build prompt and review prompt in this playbook tells Claude Code to read this file first. It is the single source of truth for principles, standing rules and the phase map.

---

## 1. What changed from the earlier plan (and why)

| # | Change | Why (finding behind it) |
|---|---|---|
| 1 | **Presentation stance: a product, not a prototype.** No "sample data" watermarks scattered through the UI. One clear *Environment* panel and a claims policy instead. | You want to pitch to companies. Scattered disclaimers look amateur; unsupported claims fail diligence. One honest disclosure plus real evidence is stronger than either. |
| 2 | **Dynamic core instead of "frozen contracts".** Everything tunable is config or data; behaviours are chosen through registries; rules and constraints are data; contracts are versioned and *evolvable*. | You need to change things later without rewrites. |
| 3 | **Data adapters are first-class.** The order generator is just one adapter. CSV replay and a webhook ingest adapter exist from Phase 2. | Gives a real answer to "can it run on our data?" |
| 4 | **Constraint/policy engine as data.** Placement rules (temperature, weight, chemical isolation), movement zones, alert rules and AI-command gating all use one rule engine. | The slotting repo's hard-constraint idea, but not hard-coded. Also what makes "no locked constraints" real. |
| 5 | **Honest AI value claim.** The AI is measured on resilience, recovery and explanation, against a strong baseline, with multiple seeds. | WareMax found simple dispatch heuristics are hard to beat on raw throughput. |
| 6 | **LLM runs behind a provider port with a heuristic fallback and a replay mode.** | Latency, cost and non-determinism must never freeze a live demo. |
| 7 | **Licence-aware reuse.** Only MIT, Apache-2.0 and BSD sources may be copied (with attribution). Repos with no visible licence are ideas only. | Several repos show no licence file. |
| 8 | **Review gate after every phase** with a strict, evidence-only review prompt and a prioritised change list. | You asked for it, and it keeps quality from drifting. |
| 9 | **Realism pack from Phase 1.** Researched, sourced assumptions; Indian quick-commerce-style catalogue in INR; demand curves with peaks and event spikes. | Makes the demo feel like a real store without faking claims. |

---

## 2. Product definition and presentation stance

**RoboFleet** is an AI-led operations command centre and digital twin for robot-assisted dark stores. It runs a store from order arrival to dispatch handoff, shows it live in 2D and 3D, and keeps the human supervisor in a small oversight and exception role.

### Presentation stance (applies to every phase)
- It is presented as a **digital-twin product**: realistic store, realistic robots, realistic demand, realistic UI. No "lorem", "sample", "dummy", "test data", "TODO" or placeholder text anywhere a viewer can see it.
- There is exactly **one disclosure surface**: an *Environment* panel (reachable from the footer badge "Digital Twin"), showing: mode (digital twin), demand source (for example "Synthetic Demand Engine, calibrated profile"), robot layer (simulated fleet), and which adapters are live. The pitch deck has one matching slide.
- **Claims policy.** Never claim real customers, real stores, deployed robots or production results. Every number used in a pitch must come from a reproducible run artifact in `reports/` and be phrased as "measured in the RoboFleet digital twin under the stated assumptions". Every such claim is listed in `docs/CLAIMS.md` with its artifact.
- Why this is the right trade-off: it lets the demo look and feel real, answers "is this simulated?" in one clean statement, and survives technical due diligence.

---

## 3. Architecture principles

### 3.1 Dynamic core
1. **Config over constants.** No numeric or string tunable appears in logic. All tunables live in Pydantic config models with defaults, validation and documentation, layered as: `defaults.yaml` < `scenario.yaml` < environment variables < CLI overrides. `config explain` prints the effective value and its origin.
2. **Registries over conditionals.** Behaviours are chosen by name in config (`{type: reservation_astar, params: {...}}`) and resolved through a typed `Registry`. No `if strategy == "x"` chains.
3. **Rules as data.** Constraints, alert rules, zone restrictions and AI-command policies are declarative rules loaded from YAML, validated, versioned, hot-reloadable, and testable with `rules lint` and `rules test`.
4. **Ports and adapters.** The engine talks to the outside world only through ports (`OrderSource`, `CatalogueSource`, `LLMProvider`, `EventSink`, `MetricProvider`). The simulated feed is one adapter among others.
5. **Event-sourced truth.** Every state change is an event in an append-only log with a sequence number. Replay, audit and evaluation are built on it.
6. **Evolvable contracts.** SemVer on all schemas. Additive changes are minor. Breaking changes need a migration function, a version bump, a decision record and a passing review gate. Clients must tolerate unknown fields.

### 3.2 Dynamic does not mean speculative
Karpathy rule 2 ("simplicity first") and ponytail ("does it need to exist?") forbid speculative flexibility. Resolution: **extension seams exist only for the declared change axes below.** Anything else is written plainly. A seam is a Protocol + registry + config key + one example implementation + one test, and nothing more.

**Declared change axes:**
CA-1 world layout and zones · CA-2 catalogue and data sources (adapters) · CA-3 rules, constraints and policies · CA-4 robot kinds and parameters · CA-5 planners, dispatchers and baseline strategies · CA-6 agents, tools and LLM providers/models · CA-7 KPIs and metrics · CA-8 scenarios and fault types · CA-9 UI panels, widgets and themes.

### 3.3 Safety boundary
The **SafetyGuard** is the only code that may change a robot's cell. It enforces non-negotiable physical invariants (no shared cells, no swaps, flow rules, emergency stop). Agents and policies cannot bypass it. A human can change its *parameters* through validated, logged config; an AI agent cannot.

---

## 4. System overview and stack

```
Adapters (demand engine | CSV replay | webhook ingest)
        │  orders
        ▼
  Order queue ──► AI Operations Brain ──► typed Commands ──► Governance (rule engine)
                  (Orchestrator +                                  │ approved
                   specialists,                                    ▼
                   heuristic fallback)                        Simulation engine
                        ▲                                   (fleet, traffic, stations,
                        │ situation brief                    SafetyGuard, faults)
                        └─────────── events/state ◄───────────────┘
                                          │
                                  WebSocket stream (snapshot + deltas)
                                   ┌──────┴───────┐
                                2D map         3D scene
                          + order board + alerts + decision log + KPIs + controls
```

**Stack (verify current stable versions at build time; do not trust this list blindly):**
- Backend: Python 3.12+, FastAPI, Pydantic v2, uvicorn, pytest, hypothesis, ruff, mypy.
- Frontend: TypeScript, React, Vite, Canvas 2D for the map, react-three-fiber with drei for 3D, Playwright for end-to-end tests.
- Storage: NDJSON event logs plus SQLite (audit log, run registry). No external services needed.
- AI: Anthropic API behind an `LLMProvider` port. Suggested starting points (verify at build time): `claude-sonnet-5-5` for the orchestrator, `claude-haiku-5-5` for fast specialists.

---

## 5. Target repository layout

```
robofleet/
├── CLAUDE.md                       # standing rules (from section 6)
├── .claude/skills/                 # project Agent Skills (section 6, SR-10)
├── .planning/                      # GSD state (committed)
├── backend/src/robofleet/
│   ├── contracts/  config/  registry/  rules/  layout/  catalogue/
│   ├── sim/  fleet/  adapters/  brain/  governance/  api/  tools/  cli/
├── backend/tests/
├── frontend/                       # Phase 2+
├── scenarios/  rules/  profiles/   # YAML data (config, rules, demand profiles)
├── contracts/jsonschema/  contracts/CHANGELOG.md
├── reports/                        # reproducible run artifacts
├── docs/ (ARCHITECTURE, CONFIG, CONTRACTS, EXTENDING, ASSUMPTIONS, CLAIMS, DECISIONS, PHASES, LAYOUT)
└── docs/playbook/                  # this folder
```

---

## 6. Standing Rules (SR-1 to SR-12)

These apply to every phase. Build prompts and review prompts cite them by ID.

**SR-1 Think before coding (Karpathy 1).** State assumptions, surface ambiguity and trade-offs, and record non-obvious choices in `docs/DECISIONS.md` before implementing. Push back on this prompt if something is wrong.

**SR-2 Simplicity first (Karpathy 2 + ponytail).** Before writing code, stop at the first rung that holds: (1) does this need to exist? skip it; (2) already in the codebase? reuse it; (3) stdlib or platform does it? use it; (4) a small, well-known dependency does it? only then add one. No abstractions except declared seams (3.2).

**SR-3 Surgical changes (Karpathy 3).** Touch only what the task requires. No drive-by refactors or reformatting. Every changed line traces to a requirement or a review finding.

**SR-4 Goal-driven execution (Karpathy 4).** Every task starts with a verifiable check (test, command, or measurable output). Loop until it passes. Never weaken a test or threshold to pass.

**SR-5 Dynamic by design.** Obey section 3.1. A magic-number scan (`tools/magic_numbers.py`, allowlist-based) runs in CI from Phase 1.

**SR-6 Evolvable contracts.** Obey section 3.1 point 6. Maintain `contracts/CHANGELOG.md`.

**SR-7 Safety boundary.** Obey section 3.3.

**SR-8 Evidence over claims.** Nothing is "done" without command output or an artifact. Report failures plainly with real numbers. Never fabricate results, screenshots or metrics.

**SR-9 Product feel.** Obey section 2. No placeholder text in any user-visible surface. Units, currency (INR), time formats and naming must be consistent and realistic.

**SR-10 Agent Skills.** Repeatable procedures live as Agent Skills in `.claude/skills/<name>/SKILL.md` (frontmatter with `name` and `description`, short body). Phase 1 creates: `robofleet-conventions`, `robofleet-add-extension`, `robofleet-contract-change`, `robofleet-review` (runs the review protocol for a given phase).

**SR-11 Workflow and git discipline (GSD).** Work phase by phase using Get Shit Done: plan, execute, verify. Keep each task small enough to finish within a healthy context window. Atomic commits with conventional messages. Tag the end of each phase `phase-N-complete` only after its review verdict is GO or GO-WITH-CHANGES with all P0/P1 items fixed.

**SR-12 Sandbox and secrets.** GSD is designed to run with permission prompts skipped. Do that only in a disposable environment (container or throwaway VM) with no secrets. Never commit API keys. Maintain `.env.example`. Never reuse code from a repo without a visible permissive licence.

---

## 7. Tooling setup (one-time; verify commands, versions change)

1. **Get Shit Done (GSD).** `npx get-shit-done-cc@latest`, choose Claude Code and global or local. Verify with `/gsd:help`. GSD keeps its state in `.planning/` and drives a plan, execute, verify loop per phase. Run `/gsd:help` to confirm the exact command names in your installed version. As far as I know the loop is new-project, discuss, plan, execute, verify.
2. **Karpathy guidelines.** In Claude Code: `/plugin marketplace add forrestchang/andrej-karpathy-skills` then `/plugin install andrej-karpathy-skills@karpathy-skills`. Or append that repository's `CLAUDE.md` to your project `CLAUDE.md`. They give the four principles behind SR-1 to SR-4.
3. **Ponytail.** `/plugin marketplace add DietrichGebert/ponytail` then `/plugin install ponytail@ponytail`. Commands include `/ponytail-review` and `/ponytail-audit`. Note: the project's headline savings (about 54% less code) come from its own benchmark. An independent test measured far smaller gains (about 15% less code), and only where there was room to over-build. Expect a modest effect and keep SR-2 as a rule, not a plugin.
4. **Agent Skills.** Created by Phase 1 inside the repo (SR-10).

---

## 8. Phase map

| Phase | Name | Output you can run | Review gate focus |
|---|---|---|---|
| 1 | Dynamic Core and Realism Pack | Deterministic headless twin: 20 robots, rule engine, config system, realistic store data, 5 change drills pass | Safety, determinism, dynamism, data realism |
| 2 | Live Data and 2D Command Centre | Browser command centre: live orders from adapters, 2D map, alerts, KPIs | Protocol robustness, UI quality, adapter seam |
| 3 | Fleet Engine and Baseline Operations | Orders flow end to end with strong baselines, 20 to 50 robots | Correctness invariants, traffic, KPI integrity |
| 4 | 3D Experience | 3D scene in sync with 2D, cinematic camera | Performance, fidelity, sync |
| 5 | AI Operations Brain | AI-led operation with governance, decision log, NL commands, fallback | Safety of AI actions, real value, cost and latency |
| 6 | Exceptions, Verification and Resilience | Chaos scenarios, recovery, supervisor workflow, audit | Recovery evidence, invariants under chaos |
| 7 | Evidence, Pitch and Flagship Hardening | Reproducible evidence, pitch kit, hardened packaged demo | Claims audit, soak, flagship checklist |

### Phase cycle (every phase)
1. Run the **build prompt** with GSD (discuss, plan, execute, verify).
2. Run the **review prompt** in a fresh Claude Code session. The reviewer is read-only and produces a verdict and a change list.
3. If the verdict is GO-WITH-CHANGES or NO-GO, turn the change list into GSD tasks, fix, and re-run the review (scoped to the changed items plus regression).
4. When the verdict is GO, tag `phase-N-complete` and update `docs/PHASES.md`.

---

## 9. Repo reuse map (what we take from each reference project)

| Source | Take | Licence rule |
|---|---|---|
| Stxqq/forklift | Renderer structure, space-time A*, reservation table, deterministic design, lane rules | MIT: may reuse with attribution |
| Skelf-Research/waremax | Order-generator config model, baselines, delay attribution, API/stream pattern, evaluation method | MIT: may reuse with attribution |
| NVIDIA MAIW | Recommend, govern, execute, observe loop; SOP-style agents; scenario overlay; fault injection | Apache-2.0: may reuse with attribution |
| devansedmak/so101-zeroshot-picking-cell | Verify, retry once, honest alert; move states COMMANDED/VERIFIED/MISMATCH/UNVERIFIED | MIT: may reuse with attribution |
| Kaizoku-04/AMR_BOT | Message contracts, task claims, liveness ideas | Check licence; ideas only by default |
| Anas1806/coeproject | Hard/soft constraint split, fairness check, override audit log, edge cases | No licence visible: **ideas only** |
| fenixkz/automated_warehouse | Order/task/job separation, SKU list shape | No licence visible: **ideas only** |
| DiyaJabin | Nothing (plan only) | Skip |
| Unverified 16 (GOFR, RWARE, RAWSim-O, Open-RMF, LCBA, lgarbayo, Sentry, etc.) | Concept references only until read and licence-checked | Do not copy any code |

Every reused snippet gets a header comment with source, licence and date, and an entry in `docs/THIRD_PARTY.md`.

---

## 10. Assumptions register and claims register
- `docs/ASSUMPTIONS.md`: every modelling parameter (store size, SKU count, basket size, demand curve, robot speed, pick times, handoff time, failure rates) with value, source URL or "engineering estimate", date and confidence. Created in Phase 1, extended in every phase.
- `docs/CLAIMS.md`: every external claim with the artifact that proves it. Created in Phase 3, audited in Phase 7.
