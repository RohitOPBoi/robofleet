# Phase 3 — Fleet Engine and Baseline Operations

Run the build prompt first, then the review prompt in a **fresh** session. Phase 2 must be tagged `phase-2-complete` before starting.

---

=== BEGIN PHASE 3 BUILD PROMPT ===

# ROLE AND MISSION
You are the lead engineer for Phase 3 of 7 of RoboFleet. Build the real **order-to-dispatch operation** without AI: orders flow through picking stations, consolidation and the dispatch bay, handled by a fleet of 20 to 50 robots in traffic, driven by **pluggable baseline strategies**. This also produces the benchmark the AI must beat in Phase 5, so the baselines must be strong and honest.

# READ FIRST
1. `docs/playbook/00-master-plan.md` (SR-1 to SR-12, change axes, presentation stance).
2. `docs/playbook/01-review-protocol.md` (build to pass it).
3. `docs/phase2-report.md`, `ARCHITECTURE.md`, `CONTRACTS.md`, `EXTENDING.md`, `ADAPTERS.md`, `reviews/phase-2-review.md` (all its P0 to P2 items must be resolved or explicitly accepted).

# HOW TO WORK
GSD loop; SR-1 to SR-12. Simplicity first: reuse Phase 1 and 2 machinery. Evolve contracts additively. Phase 1 safety and determinism guarantees must still hold; the SafetyGuard remains the only mover.

# PHASE GOAL (exit demo)
Run the standard store at realistic evening demand with 20 robots: orders arrive, items are retrieved from bins by robots, brought to picking stations, picked into order totes, consolidated, placed at the dispatch bay, and handed over by a simulated supervisor. The 2D UI shows the whole journey. A strategy comparison command produces a table of KPIs for several baseline strategies on identical seeds. Raising to 50 robots and a rush overlay works without gridlock.

# NON-GOALS
No LLM or agents, no 3D, no failures beyond what Phase 1 hooks already provide (Phase 6), no replenishment or re-slotting (Phase 6).

# SPECIFICATION

## A. Fulfilment model (goods-to-person hybrid)
- **Order lifecycle:** RECEIVED, PLANNED, RETRIEVING, AT_STATION, PICKING, CONSOLIDATING, PACKED, READY_FOR_DISPATCH, HANDED_OVER, plus terminal CANCELLED and FAILED. Every transition is an event (`order.*`) with the actor and reason.
- **Tasks:** a `Task` is the unit of robot work: `FETCH_BIN` (go to a bin's access cell, load a tote), `DELIVER_TO_STATION`, `RETURN_BIN`, `CARRY_ORDER_TOTE` (station to pack to dispatch), `CHARGE`, `PARK`. Tasks have ids, an owner order list (a task may serve several orders when batching), a deadline, a state, and timestamps.
- **Robot capacity and carrying:** `carrying` holds tote references. Robot kinds in config define capacity (totes) and speed.
- **Stations:** each has a dock, a bounded queue, a configurable number of pick workers (simulated pickers or robotic arms; kind in config), and a service-time model: base time per item plus a handling-difficulty multiplier, a seeded distribution, and a learning-free configuration (no hidden randomness outside seeded streams). Stations emit `station.queue_changed`.
- **Pack and consolidation:** items of one order are brought together; an order cannot move past CONSOLIDATING until all lines are present; orders are never mixed (hard invariant, tested).
- **Dispatch and supervisor:** a single simulated supervisor at the desk takes ready orders from the dispatch bay and hands them to riders. Handoff time is a seeded distribution from config; a rider-arrival model (configurable) caps handoff rate. Supervisor load appears as a KPI.
- **Inventory:** picking decrements bin quantity; stock-outs are real: an order line that cannot be filled is flagged `SHORT` and raises an alert (resolution strategies come in Phase 6; for now the order is marked FAILED_PARTIAL with the reason). Conservation invariant: units removed from bins equal units in dispatched or in-flight orders.

## B. Traffic: space-time reservations (CA-5)
- Replace the placeholder planner with a registered `reservation_astar` planner (cooperative space-time A* with a reservation table, windowed horizon configurable), respecting flow lanes, blocked cells, keep-out zones and robot dimensions.
- Deadlock handling: detect cycles in the wait-for graph; resolve by deterministic priority (age then deadline then id) plus a yield or detour; count incidents. Keep the Phase 1 `astar_flow` planner registered for comparison.
- Intersection and station-queue discipline: queue cells are reserved in order; no overtaking; robots waiting for a station hold a queue slot; parking and charger access never block through-traffic (test).
- Scalability target: 50 robots in the `large` preset under a 3x rush overlay with zero safety violations and zero unresolved deadlocks over 30 simulated minutes.
- The SafetyGuard still validates every move; planners only propose.

## C. Baseline strategies (CA-5): registered by name and chosen in config
Provide at least these, each documented with its logic, and each a legitimate attempt to do well:
1. `fcfs_nearest`: serve orders first-come-first-served; assign the nearest idle robot to each task.
2. `edf_deadline`: earliest-deadline-first order priority; nearest robot; urgent orders preempt queued work.
3. `batch_greedy` (the strong baseline): batches compatible orders (shared bins or aisle segments) within a deadline-safe window; assigns robots by minimum marginal travel; balances station queues; keeps the charge policy aware (robots below a threshold are removed from the pool before an assignment that would strand them).
4. `random` (sanity floor only, never used in claims).
The strong baseline must be reviewed and tuned until a reasonable reviewer could not call it a strawman. Record tuning effort and parameters in `DECISIONS.md`.

## D. Charging and fleet management
- Charge policy (strategy-selectable): threshold-based and opportunistic (charge during lulls). Chargers have capacity and queueing; charging events are tasks.
- **Dynamic fleet size:** add or remove robots at runtime (spawn from parking; retire when idle) via a control command; the UI reflects it. Orders and tasks must remain consistent.
- Robot utilisation accounting by state, per robot and fleet.

## E. KPIs and metrics (CA-7): a `MetricProvider` registry
Compute, per run and live over a rolling window: orders received, completed, per hour; order-to-ready time (mean, median, P90, P99); order-to-handover time; on-time percentage against deadlines; late orders; correct-item and correct-quantity rate (should be 100 percent here, and verified); station utilisation and queue lengths; robot utilisation (moving, waiting, charging, idle), average robot travel and waiting per order; congestion and deadlock incidents; collisions (must be 0); supervisor utilisation; human interventions per 100 orders (alerts requiring human). Adding a KPI is one provider plus config.
- **Delay attribution** (method from WareMax, reimplemented): for each late order, attribute delay to waiting for robot, travel, station queue, pick time, consolidation, supervisor handoff.
- Metrics export to `metrics.json` and are streamed as `kpis` in the delta.

## F. Evaluation command
`python -m robofleet.cli compare --scenario standard --strategies fcfs_nearest,edf_deadline,batch_greedy --seeds 1..10 --duration 3600` runs the matrix, writes `reports/compare-<timestamp>/` with per-run metrics, a summary table (mean and standard deviation, plus 95 percent confidence intervals), and a short machine-readable manifest (git commit, config hash, seeds). Identical seeds must give identical results per strategy.

## G. UI updates (using the panel registry)
- Order board shows full lifecycle with stage chips and a per-order timeline drawer.
- 2D map overlays: task lines from robot to destination, tote icons on carrying robots, station queues, dispatch bay and supervisor activity, congestion heat.
- KPI charts panel: throughput, on-time percentage, queue lengths, utilisation over time (lightweight charting; justify any library).
- Fleet panel: robot list with state, task, battery; fleet resize control; strategy selector (pre-run) shown in the Environment panel.
- Alerts from rules: station queue overflow, order at risk, stock-out, robot waiting too long, charger starvation.

## H. Testing
- **Invariant property tests** (Hypothesis, random scenarios and seeds): no order mixing; conservation of units; every order ends in a terminal state; no robot task orphaned; no safety violation; no robot or tote duplicated; time never decreases.
- **Scenario tests** with expected qualitative outcomes (for example a rush increases queue length and risk, recovery follows).
- **Determinism**: strategy runs reproduce exact hashes.
- **Performance**: `large` 30-minute run time; per-tick cost profile; planner time per call.
- **Regression**: Phase 1 and 2 suites unchanged and passing.

## I. Documentation
`docs/FULFILMENT.md` (model, lifecycle, invariants), `docs/STRATEGIES.md` (each baseline), `docs/METRICS.md` (every KPI definition and formula), `docs/CLAIMS.md` (created now: initially empty claims with the rule for adding one), updates to ARCHITECTURE/CONFIG/EXTENDING/CONTRACTS/ASSUMPTIONS (pick time, handoff time, rider arrival, station worker counts with sources or estimate labels), `phase3-report.md`.

# CHANGE DRILLS THIS PHASE MUST PASS
- **CD-5** add a new baseline strategy through the registry: at most 2 files plus config.
- **CD-7** add a new KPI: at most 2 files plus config.
- **CD-1** add a new alert rule (for example "supervisor queue above N") in YAML only.
- **CD-2** change station count, robot count and rack rows by config only.
- **CD-3** add a new event type end to end.

# ACCEPTANCE CRITERIA
- **P3-A1** End-to-end: in the standard store at 20 robots for 3600 s of simulated evening demand, at least 99 percent of orders reach HANDED_OVER or a documented terminal state; none lost; none stuck.
- **P3-A2** Invariants hold in property tests over at least 200 random scenarios: no order mixing, unit conservation, no orphan tasks.
- **P3-A3** Safety: zero violations in standard (3600 s) and large (1800 s, 50 robots, 3x rush); zero unresolved deadlocks; incident counts reported.
- **P3-A4** Determinism: identical hashes for the same strategy, scenario and seed across two runs.
- **P3-A5** All three real baselines plus `random` run via config; the `compare` command produces the report with confidence intervals; `random` is clearly the worst on on-time percentage.
- **P3-A6** The strong baseline `batch_greedy` beats or ties `fcfs_nearest` on on-time percentage and P90 order-to-ready time across at least 10 seeds; if not, either the baseline or the claim of strength is wrong and must be fixed or explained.
- **P3-A7** KPI definitions are documented and verified by hand on a small deterministic scenario (a worked example in `METRICS.md` that a test reproduces).
- **P3-A8** Delay attribution sums to total lateness within rounding for every late order (test).
- **P3-A9** UI shows the full order journey, robot tasks and KPI charts live without console errors; 60 fps median at 50 robots (measured).
- **P3-A10** Dynamic fleet resize works at runtime without inconsistency (test and UI).
- **P3-A11** Performance reported for standard and large; the large 30-minute run finishes in under 5 minutes headless, or the miss is explained with a profile.
- **P3-A12** All Phase 1 and 2 acceptance checks still pass.
- **P3-A13** Change drills CD-1, CD-2, CD-3, CD-5, CD-7 pass with files-touched recorded.
- **P3-A14** Docs accurate; each KPI, strategy and config key documented.

# FINAL REPORT
`docs/phase3-report.md` with evidence per criterion, the strategy comparison table (with confidence intervals), measured performance, decisions, limitations (be explicit about every modelling simplification), and handoff notes for Phase 4 and 5. Stop. Do not start Phase 4.

=== END PHASE 3 BUILD PROMPT ===

---

=== BEGIN PHASE 3 REVIEW PROMPT ===

# ROLE
Independent, strict, read-only reviewer for Phase 3 of RoboFleet. Write only `reviews/phase-3-review.md`.

# READ FIRST
`docs/playbook/00-master-plan.md`, `docs/playbook/01-review-protocol.md` (apply fully), `docs/phase3-report.md` (claims to verify), `reviews/phase-2-review.md` (confirm resolved).

# VERIFY
P3-A1 to P3-A14 by running things yourself. Re-run the `compare` command with fresh seeds (not the builder's) and compare with the report.

# PHASE-SPECIFIC CHECKS
- **P3-R1 Strawman test.** Read the strong baseline's code. Would an experienced operations engineer consider it a serious, well-tuned heuristic? Try to beat it by hand-tuning one parameter or adding one obvious improvement (for example a better batching window). If you can beat it easily, the Phase 5 comparison is not credible: P1.
- **P3-R2 Invariant adversary.** Write your own invariant checker and fuzz it: random scenarios, random seeds, random fleet resizes mid-run, random block and e-stop commands, random stock levels. Look for lost orders, double-counted units, orders in impossible states, tasks assigned to retired robots.
- **P3-R3 Metric integrity.** Recompute five KPIs from the raw event log with an independent script and compare with `metrics.json`. Check definitions: on-time uses deadlines in the order, not a proxy; order-to-ready starts at receipt, not at planning.
- **P3-R4 Statistics.** Are the seeds, sample sizes and confidence intervals computed correctly? Are comparisons using paired seeds? Is any claim made from a single seed?
- **P3-R5 Traffic quality.** Run the 50-robot 3x-rush scenario 10 times with different seeds; list any deadlock, long wait, or livelock (robots moving without progress). Inspect the heat map for pathological hotspots. Check the planner's worst-case call time.
- **P3-R6 Model plausibility.** Are pick times, handoff times and rider arrival plausible for quick commerce, and sourced or labelled as estimates? Does the throughput of the standard store look plausible (orders per hour per robot) compared with what is publicly known? Flag magnitudes that would make a domain expert laugh.
- **P3-R7 Strategy seam.** Do CD-5 and CD-7 honestly. Report time and files.
- **P3-R8 UI truthfulness.** Pick 20 random moments; compare what the UI shows with the event log and snapshot. Any mismatch is P1.
- **P3-R9 Overreach and debt.** List special cases, flags and hacks added to make scenarios pass. Check for tuning to the test seeds.
- **P3-R10 Claims.** `docs/CLAIMS.md` must not contain claims yet unsupported by reports; check any numbers quoted in docs or UI.

# CHANGE DRILLS FOR THIS PHASE
CD-1, CD-2, CD-3, CD-5, CD-7.

# PHASE 3 WORTH-IT QUESTIONS
1. Is the operation credible: would an operations person watching it believe it is a plausible store?
2. Is the benchmark good enough that beating it in Phase 5 will mean something? If not, say exactly what to change.
3. What simplifications most threaten credibility with a technical buyer?
4. Are the task, order and event models flexible enough for Phase 5 agents and Phase 6 failures without a breaking change?
5. What must change before Phase 4 and Phase 5 start?

# OUTPUT
Follow the review protocol's output template exactly: mechanical verdict, score arithmetic, change list with acceptance tests, suggested GSD task list.

=== END PHASE 3 REVIEW PROMPT ===
