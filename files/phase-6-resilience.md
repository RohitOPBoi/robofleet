# Phase 6 — Exceptions, Verification and Resilience

Run the build prompt first, then the review prompt in a **fresh** session. Phase 5 must be tagged `phase-5-complete` before starting.

---

=== BEGIN PHASE 6 BUILD PROMPT ===

# ROLE AND MISSION
You are the lead engineer for Phase 6 of 7 of RoboFleet. Make the store **resilient and honest about failure**: pick verification with realistic failure modes, a registry of fault types, a library of chaos scenarios, recovery logic (algorithmic first, AI-arbitrated where it helps), a supervisor exception workflow with an audit trail, and light replenishment and re-slotting. This is where the AI's value is meant to show up, so build it to be *measured*.

# READ FIRST
1. `docs/playbook/00-master-plan.md` (SR-1 to SR-12, safety boundary, change axes CA-3, CA-5, CA-8).
2. `docs/playbook/01-review-protocol.md` (build to pass it).
3. `docs/phase5-report.md`, `AI_BRAIN.md`, `POLICIES.md`, `FULFILMENT.md`, `METRICS.md`, `reviews/phase-5-review.md` and earlier reviews (resolve all open P0 to P2 items).

# HOW TO WORK
GSD loop; SR-1 to SR-12. Reuse the Phase 1 hooks (`inject_fault`, `block_cells`, `emergency_stop`) and the rule engine. Contracts evolve additively. The SafetyGuard remains the only mover and stays non-bypassable.

# PHASE GOAL (exit demo)
From the control panel a presenter can trigger: a robot breakdown mid-task, a blocked aisle, a missing item at a bin, a damaged item at a station, a station slowdown, a communications drop for one robot, an urgent-order burst, and a battery cascade. In each case the store keeps running, affected orders are recovered or escalated cleanly, the alert and decision log tell the story, and a recovery-time metric appears. The supervisor sees only what truly needs a human, with a clear action to take, and every human action is audited.

# NON-GOALS
No real-robot control, no RL, no complex warehouse inbound receiving. Replenishment and re-slotting are deliberately minimal.

# SPECIFICATION

## A. Pick verification (pattern from the SO-101 reference, reimplemented)
- Every pick passes a **verification step** with outcome states `COMMANDED`, `VERIFIED`, `MISMATCH`, `UNVERIFIED` (never treated as success unless VERIFIED).
- Failure model by handling difficulty and fragility, all rates in config with sourced or estimate-labelled assumptions: failed grasp, wrong item, quantity mismatch, damaged item, uncertain identification.
- Policy: retry once (configurable), then isolate the item and raise an exception; never silently complete an uncertain order. Verification confidence is modelled as a seeded distribution; the threshold is config.
- Events: `pick.commanded`, `pick.verified`, `pick.mismatch`, `pick.unverified`, `pick.retried`, `pick.failed`, with reasons.

## B. Fault registry (CA-8)
Registered fault types, each defined by a small class plus YAML parameters (duration, scope, severity, recovery behaviour): `robot_breakdown`, `robot_comms_drop`, `battery_cascade`, `aisle_blocked`, `bin_missing_stock`, `item_damaged`, `station_slowdown`, `station_offline`, `urgent_order_burst`, `supervisor_unavailable`. Adding a fault type is at most 2 files plus YAML (CD-8).
- Faults can be injected manually (control channel and UI), scheduled in a scenario file, or random from a seeded process with configurable rates.
- Faults always flow through the engine commands and the SafetyGuard; they never mutate state directly.

## C. Chaos scenario library (CA-8)
YAML scenarios in `scenarios/chaos/`, each with: description, duration, demand overlay, scheduled faults, **expected outcomes and pass criteria** (for example "no lost orders; on-time percentage at least X of baseline; recovery within Y seconds; zero safety violations"). Ship at least: `robot_failure_cascade`, `aisle_blockage_peak`, `stock_out_urgent_orders`, `station_down_rush`, `comms_drop_two_robots`, `battery_stress`, `perfect_storm` (several at once). A runner (`python -m robofleet.cli chaos --scenario <name> --mode baseline|heuristic|ai --seeds ...`) produces a report with recovery-time and outcome tables.

## D. Recovery (algorithmic first)
- **Reassignment:** tasks of a failed robot return to the pool preserving order priority; totes carried by a dead robot are flagged for physical recovery (an `requires_human` alert with location).
- **Reroute:** blocked aisles and zones are bypassed; if a region is unreachable, affected tasks are re-planned or escalated.
- **Substitution:** a missing or damaged item is substituted from a **replica bin** (Phase 1 slotting) or flagged `SHORT`. Options for a short line (config policy): partial fulfilment with customer-impact flag, delay with an updated deadline, or cancel the line. The chosen outcome and reason are recorded.
- **Station failover:** orders move to other stations; queues rebalance.
- **Degraded modes:** each active fault sets a named degraded mode visible in the UI (for example "Station 3 offline: rerouting").
- **AI arbitration:** the Phase 5 Exceptions specialist proposes among valid recovery options; the heuristic provider implements the same options deterministically. Governance and SafetyGuard apply as before.
- **Escalation rules (rule engine):** which exceptions need a human, the SLA to respond, and the default action on timeout.

## E. Supervisor workflow and audit
- **Exceptions queue:** items needing a human (damaged goods, physical tote recovery, unresolvable shortages, approvals) with priority, deadline, recommended action, and one-click resolution choices. The queue shows the human interventions per 100 orders KPI.
- **Manual override with validation (pattern from the slotting reference, reimplemented):** any supervisor action that changes state (reassign, release a zone, force a substitution, override a policy within allowed bounds) requires user, role, reason and is validated against hard constraints; rejected attempts are logged too.
- **Audit log** in SQLite: append-only table of every human and AI state-changing action with timestamp, actor, role, before and after, reason, result. Export to CSV from the UI. Roles and permissions in config (viewer, supervisor, admin).
- **Incident timeline view:** a panel that groups events for a fault into a story (injected, detected, decisions, recovery steps, resolved), with timings and the recovery-time metric.

## F. Replenishment and re-slotting (minimal, rule-driven)
- **Replenishment-lite:** low-stock rule raises a replenishment task for a simulated stocker or the supervisor (resource with a seeded availability and speed); restocking increments bins; urgent order work always outranks replenishment (a rule). Metrics: stock-outs avoided, replenishment wait.
- **Re-slotting recommendations:** a periodic recommender scores popularity-versus-location using the Phase 1 constraint engine as hard constraints (temperature, weight, chemical isolation, level safety) and a move-cost penalty; it outputs a **recommendation list only** (no automatic moves). A supervisor can approve a move, which creates a replenishment-style task; every decision is audited. Include a fairness-style guard so a recommendation cannot raise a congestion proxy above a configured limit.
- Both features are config-switchable and documented as deliberately simple.

## G. Metrics
Add (CD-7 style): mean time to detect, mean time to recover (by fault type), orders affected, orders delayed, orders lost (must be 0), partial fulfilment rate, human interventions per 100 orders, exceptions queue age, degraded-mode time, SLA retained during incidents versus baseline, safety incidents (must be 0).

## H. UI
- Control panel: fault injection by type and target (click a robot, a bin, an aisle), scenario launcher, "perfect storm" button, clear and heal controls, all token-protected with confirmations.
- Exceptions queue, incident timeline, degraded-mode banners, audit log viewer with filters and CSV export, all through the panel registry.
- 2D and 3D reflect failures visibly (broken robot, blocked aisle, offline station) and mirror alerts.

## I. Testing
- **Chaos property tests** (Hypothesis): random fault sequences and seeds; invariants from Phase 3 hold (no lost orders, no mixing, unit conservation, no safety violation) and every order reaches a terminal state or an explicit exception.
- Scenario tests asserting each chaos scenario's pass criteria in `heuristic` mode (CI) and, if API access exists, in `ai` mode (optional job).
- Verification model tests (rates match config within tolerance over many picks).
- Audit log tests (append-only, rejected attempts recorded, permissions enforced).
- Determinism: chaos runs with the same seed reproduce hashes.

## J. Documentation
`docs/RESILIENCE.md` (fault registry, scenarios, recovery logic, degraded modes), `docs/SUPERVISOR.md` (workflow and roles), `docs/AUDIT.md`, `docs/CHAOS_REPORT.md` template, updates to AI_BRAIN, POLICIES, METRICS, FULFILMENT, ASSUMPTIONS (failure rates, recovery times with sources or estimate labels), `CLAIMS.md`, `phase6-report.md`.

# CHANGE DRILLS THIS PHASE MUST PASS
- **CD-8** add a new fault type and a scenario using it: at most 2 files plus YAML.
- **CD-1** add an escalation rule and a recovery-policy rule in YAML only.
- **CD-7** add a new resilience KPI: at most 2 files plus config.
- **CD-9** add a new panel for a new fault visualisation: at most 2 files plus config.

# ACCEPTANCE CRITERIA
- **P6-A1** Every shipped chaos scenario runs in baseline and heuristic modes and meets its documented pass criteria on at least 10 seeds, with results tabulated.
- **P6-A2** Zero lost orders, zero safety violations, zero order mixing, and unit conservation across all chaos runs (property tests plus scenario tests).
- **P6-A3** Pick verification: no order completes with an `UNVERIFIED` or `MISMATCH` pick; retry and isolation logic proven by tests; observed failure rates match config.
- **P6-A4** Recovery times are measured per fault type, reported with confidence intervals, and compared across baseline, heuristic and AI modes (AI results labelled with provider mode).
- **P6-A5** Exceptions queue shows only genuinely human-required items; the human interventions per 100 orders KPI is computed and plausible; default actions on timeout work.
- **P6-A6** Audit log: every human and AI state change is recorded; rejected attempts recorded; permissions enforced; CSV export works; the log is append-only (test).
- **P6-A7** Manual override validation blocks hard-constraint violations with a clear reason (tests for temperature, weight, chemical isolation, level safety).
- **P6-A8** Replenishment-lite and re-slotting recommendations work, never move stock automatically, never starve urgent order work (tests), and respect the congestion guard.
- **P6-A9** UI: fault injection, scenario launcher, exceptions queue, incident timeline and audit viewer work with no console errors; 2D and 3D show failures correctly; 60 fps held in a `perfect_storm` run at 50 robots.
- **P6-A10** Determinism preserved for all chaos runs.
- **P6-A11** All Phase 1 to 5 acceptance checks still pass.
- **P6-A12** Change drills CD-1, CD-7, CD-8, CD-9 pass with files-touched recorded.
- **P6-A13** Docs accurate; assumptions about failure rates and recovery times sourced or labelled as estimates.

# FINAL REPORT
`docs/phase6-report.md`: evidence per criterion, the chaos results tables, recovery-time comparison, decisions, limitations (state plainly what is modelled crudely), handoff notes for Phase 7 (which results are strongest for the pitch, which are weak). Stop. Do not start Phase 7.

=== END PHASE 6 BUILD PROMPT ===

---

=== BEGIN PHASE 6 REVIEW PROMPT ===

# ROLE
Independent, strict, read-only reviewer for Phase 6 of RoboFleet. Write only `reviews/phase-6-review.md`.

# READ FIRST
`docs/playbook/00-master-plan.md`, `docs/playbook/01-review-protocol.md` (apply fully), `docs/phase6-report.md` (claims to verify), `reviews/phase-5-review.md` (confirm resolved).

# VERIFY
P6-A1 to P6-A13 yourself. Re-run every chaos scenario on **seeds not used by the builder** in baseline and heuristic modes (and `ai` or `replay` if possible), and compare with the report.

# PHASE-SPECIFIC CHECKS
- **P6-R1 Invariants under chaos.** Write your own fuzzer that injects random faults, blocks, e-stops, fleet resizes, stock changes and supervisor actions at random times for at least 200 runs. Hunt for: lost orders, orders stuck without an exception, double-counted units, tote duplication, robots acting after retirement, stuck queues, audit gaps. Any loss or safety violation is P0.
- **P6-R2 Pass criteria sanity.** Are the scenarios' pass criteria meaningful or tuned to pass? Make the scenarios harder (higher rate, longer outage) and see whether the system degrades gracefully or collapses. Report the breaking point honestly.
- **P6-R3 Verification honesty.** Confirm the verification model cannot be bypassed and `UNVERIFIED` is never treated as success. Check statistical rates against config over at least 10,000 picks.
- **P6-R4 Recovery realism.** Are recovery times and degraded behaviour plausible? For example, does a dead robot's tote get flagged for a human, rather than magically vanishing? Do blocked aisles genuinely reduce throughput?
- **P6-R5 AI vs heuristic evidence.** Does AI mode improve recovery time or SLA retention versus the heuristic fallback and the baseline, with confidence intervals on held-out seeds? State precisely where it helps, where it is equal and where it hurts. Claims in docs or UI must match.
- **P6-R6 Human workflow.** Walk through each exception type as the supervisor: is the next action obvious? Is the queue noise-free? Are timeouts and defaults safe? Could a supervisor accidentally cause damage? Check confirmation steps.
- **P6-R7 Audit and permissions.** Try to alter or delete audit rows through any interface; try actions beyond a role; try forged actor names. Check rejected attempts are logged and PII or secrets are not.
- **P6-R8 Replenishment and slotting guardrails.** Try to make a recommendation violate a hard constraint or starve an urgent order. Confirm no automatic stock movement.
- **P6-R9 Demo choreography.** Run the `perfect_storm` demo five times; list anything confusing, ugly or fragile on screen. Does the incident timeline tell a clear story in under 30 seconds?
- **P6-R10 Simplicity audit.** Faults, scenarios, recovery options and UI panels: dead code, speculative options, rules nobody uses.
- **P6-R11 Claims.** Any resilience claim ("recovers in X seconds", "no lost orders") must have an artifact; list the strongest three claims you would permit in a pitch and the ones you would forbid.

# CHANGE DRILLS FOR THIS PHASE
CD-1, CD-7, CD-8, CD-9.

# PHASE 6 WORTH-IT QUESTIONS
1. Does this phase make the product convincingly resilient, or only look resilient on curated scenarios?
2. What are the three strongest, evidenced, pitch-worthy resilience results, and the weakest parts that must not be oversold?
3. Is the supervisor workflow credible to someone who runs a real dark store?
4. Which parts (replenishment, re-slotting, extra faults) should be cut or deferred as low value for the pitch?
5. What must change before Phase 7 starts?

# OUTPUT
Follow the review protocol's output template exactly: mechanical verdict, score arithmetic, change list with acceptance tests, suggested GSD task list.

=== END PHASE 6 REVIEW PROMPT ===
