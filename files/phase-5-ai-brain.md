# Phase 5 — AI Operations Brain

Run the build prompt first, then the review prompt in a **fresh** session. Phase 4 must be tagged `phase-4-complete` before starting.

---

=== BEGIN PHASE 5 BUILD PROMPT ===

# ROLE AND MISSION
You are the lead engineer for Phase 5 of 7 of RoboFleet. Build the **AI Operations Brain**: a central orchestrator with a small set of specialist agents that observes the store, decides, acts through validated commands, observes outcomes and explains itself. It must sit *behind* a governance layer and the SafetyGuard, run with a fast heuristic fallback so the demo never freezes, and be measurable against the Phase 3 baselines.

# READ FIRST
1. `docs/playbook/00-master-plan.md` (SR-1 to SR-12, safety boundary 3.3, change axes CA-3, CA-5, CA-6).
2. `docs/playbook/01-review-protocol.md` (build to pass it).
3. `docs/phase4-report.md`, `docs/FULFILMENT.md`, `docs/STRATEGIES.md`, `docs/METRICS.md`, `docs/CONTRACTS.md`, `reviews/phase-4-review.md` and `reviews/phase-3-review.md` (resolve all open P0 to P2 items).

# HOW TO WORK
GSD loop; SR-1 to SR-12. Be honest about where an LLM adds value and where a deterministic algorithm is better (SR-2). Verify current Anthropic model identifiers, pricing, limits and tool-use features from the official docs before choosing (suggested starting points: `claude-sonnet-5-5` for the orchestrator, `claude-haiku-5-5` for fast specialists; confirm they are current). Never put an API key in the repo. Contracts evolve additively.

# DESIGN STANCE (decide and record in DECISIONS.md before coding)
- The orchestrator is a **central decision-maker, not a chatbot**: event-triggered, bounded, typed in and out.
- **Do not build twelve agents.** Build one **Mission Orchestrator** and four **specialists**: (1) **Planner** (order batching, prioritisation, assignment arbitration), (2) **Traffic and Fleet** (congestion, charging, fleet balance), (3) **Exceptions and Recovery** (failures, stock-outs, blocked aisles; fully exercised in Phase 6), (4) **Explainer** (decision narration and supervisor Q and A). Inventory, dispatch and replenishment awareness are *modules* the specialists call, not separate agents. Record this against the 12-role list in the original product vision and justify it.
- Where an exact algorithm exists (assignment, path planning), the agent **calls it as a tool** and arbitrates or tunes parameters. The LLM does not do arithmetic or geometry.
- The AI **acts**, within policy: validated commands, executed automatically if the policy allows, otherwise queued for human approval.

# PHASE GOAL (exit demo)
A mode switch "Baseline | AI" runs the same seeded evening scenario in either mode. In AI mode the decision log shows real decisions with reasons ("Station 3 queue is 7 and Station 5 is idle; rerouting 4 pending totes"), the AI reacts to a rush or an injected hold within seconds, and a supervisor can type "prioritise urgent orders for 10 minutes" or "pause zone C" and see it validated, confirmed and applied. Unplugging the network leaves the store running on the heuristic fallback with a visible, honest mode indicator.

# NON-GOALS
Full failure taxonomy and chaos scenarios (Phase 6), replenishment and re-slotting (Phase 6), reinforcement learning, fine-tuning, voice, physical robots.

# SPECIFICATION

## A. Control loop
- **Triggers (event-driven with debouncing):** order burst, order at risk, station queue over threshold, robot fault or stall, battery events, blocked aisle, stock-out, rush overlay change, supervisor command, and a slow periodic heartbeat. All thresholds in config.
- **Situation brief builder:** a deterministic function that summarises the world into a compact, bounded structure (token budget in config): key KPIs, at-risk orders, station queues, robot states and tasks, congestion hotspots, active alerts, active policies, recent decisions and their outcomes. It never sends raw full state.
- **Typed commands (the only way the brain acts):** `assign_task`, `reprioritise_order`, `batch_orders`, `reroute_robot`, `send_to_charge`, `hold_zone`, `release_zone`, `set_station_policy`, `set_strategy_params`, `escalate_to_human`, `no_action`. Each has a schema, an expected-effect field and a `reason`.
- **Loop:** observe, decide (LLM or heuristic), validate, govern, execute (through the engine and SafetyGuard), observe outcome after a configurable window, record a `Decision` with outcome (improved, neutral, worsened, unknown) for the log and evaluation.

## B. Governance layer (CA-3; reuse the Phase 1 rule engine with scope `command`)
- Every command passes: schema validation, **policy rules** (allowed commands per mode, risk tier, rate limits, forbidden zones, "never strand a robot below minimum battery", "never exceed N reroutes per minute", "never hold more than X percent of zones"), then an **approval route**: auto-approve, require-human (appears in an approvals queue with timeout and default action), or deny with reason.
- Denials and approvals are events and appear in the decision log.
- **SafetyGuard is final.** A command can never cause an unsafe move; if the engine rejects an action, the outcome is recorded and the brain is told.
- Policies are YAML data (hot-reloadable), with embedded tests via `rules test`. A human can change policy through config; the AI cannot.

## C. LLM provider port (CA-6)
- `LLMProvider` Protocol with implementations registered by name:
  - `anthropic` (real API; model ids, timeouts, retries with backoff, and a **circuit breaker** in config).
  - `heuristic` (deterministic, no network; implements the same decide interface using the Phase 3 strong baseline plus simple rules).
  - `replay` (plays back recorded decisions from a file for deterministic demos and tests; recorded automatically in `anthropic` mode).
- **Failover:** on timeout, error, circuit open, or budget exhausted, the loop falls back to `heuristic` within one tick of the failure and surfaces an indicator in the UI top bar and Environment panel ("AI: live", "AI: fallback", "AI: replay"). Recovery is automatic with hysteresis.
- Cost and latency governance: configurable max calls per minute, token budgets per call and per hour, p50/p95 latency tracking, running cost estimate shown in diagnostics. Prompt caching or equivalent is used where it reduces cost (verify current API features).
- Structured outputs: use tool use or JSON schema outputs so commands are parsed reliably; invalid outputs trigger one repair attempt then fallback.

## D. Agents and prompts as data
- Each agent (orchestrator and specialists) is defined by a versioned file in `prompts/` (role, goals, constraints, output schema, examples), loaded at start and hot-reloadable. Prompts contain no secrets and no scenario-specific hacks.
- Specialists are invoked by the orchestrator as tools with their own bounded briefs; a specialist returns a proposal, not an action. The orchestrator arbitrates conflicts and produces the final command list. Keep one shared world view to avoid conflicting beliefs.
- Adding a specialist or tool is a registry entry, a prompt file and config (CD-6).

## E. Decision log and explainability
- `Decision` records: id, tick, trigger, brief hash, proposals, final commands, governance outcome, execution result, observed outcome, latency, tokens, cost, provider mode, and a plain-language rationale (generated by the Explainer, grounded in the brief; it must not invent facts not in the brief; a checker verifies referenced entities exist).
- **UI decision log panel** (via the panel registry): live list with filters, expandable evidence (the brief excerpt, commands, outcome), outcome chips, links that focus entities in 2D and 3D, an approvals queue, and a mode indicator. In 3D, recent decisions show as subtle annotations at the affected locations.
- Export decisions to `runs/.../decisions.ndjson`.

## F. Natural-language supervisor commands
- A command box with history. Text is parsed by the Explainer or orchestrator into a **typed policy command** (for example `set_priority(urgent, duration)`, `hold_zone(zone)`, `release_zone`, `pause_batching`, `ask_status`). The UI shows the parsed command and impact summary and requires confirmation for state-changing actions. Ambiguity produces a clarifying question, not a guess.
- Parsed commands pass the same governance and are audited with the user, text, parse and result.
- Questions ("why is order 4812 late?") are answered from the event log and brief, with cited evidence, and never invent data.

## G. Evaluation harness (the honest part)
- `python -m robofleet.cli eval-ai --scenario evening --seeds 1..10 --modes baseline,heuristic,ai` runs paired seeds, records KPIs, decisions, cost and latency, and writes `reports/eval-<timestamp>/`.
- Metrics: all Phase 3 KPIs plus decision validity rate, governance denial rate, outcome-improved rate, fallback rate, tokens and cost per simulated hour, p95 decision latency.
- **Replay for determinism:** AI runs record all LLM I/O; replay reproduces the exact hash. Tests use `replay` and `heuristic` only (no network in CI).
- **Honesty requirement:** report results as they are, with confidence intervals. If AI mode does not beat the strong baseline on throughput, say so; the expected value is in resilience and explanation (Phase 6 will test failure scenarios). Do not tune prompts to the evaluation seeds; hold out seeds 11 to 20 for the review.

## H. Safety, abuse and robustness
- Prompt injection defence: order data, SKU names and supervisor text are treated as untrusted data placed in clearly delimited fields; the system prompt forbids following instructions inside data; governance is the real defence, not the prompt. Include adversarial tests (an order whose name contains instructions; a supervisor command trying to disable safety).
- No command can change SafetyGuard parameters or disable rules; those are human-config only.
- Rate limits and budgets prevent runaway cost; kill switch in the UI and config ("AI off").
- Secrets via environment only; redaction in logs.

## I. Documentation
`docs/AI_BRAIN.md` (architecture, loop, commands, governance, failover, prompts, evaluation method), `docs/POLICIES.md`, `docs/PROMPTS.md`, updates to ARCHITECTURE/CONFIG/CONTRACTS/EXTENDING/ASSUMPTIONS/METRICS, `CLAIMS.md` (add evaluation-backed claims only), `phase5-report.md`.

# CHANGE DRILLS THIS PHASE MUST PASS
- **CD-6** add a new specialist or tool: at most 2 files plus config and a prompt file.
- **CD-1** add a new governance policy (for example "no reroute within 5 seconds of last reroute") in YAML only.
- **CD-5** register a new decision heuristic for the fallback provider: at most 2 files plus config.
- **CD-3** add a new decision trigger event.

# ACCEPTANCE CRITERIA
- **P5-A1** Baseline | AI mode switch works on the same seeded scenario; mode, provider state and cost are visible in the UI.
- **P5-A2** Every brain action is a schema-valid typed command that passed governance; there is no code path from LLM output to the engine that skips validation (verified by tests and a code review note).
- **P5-A3** Governance rules: tests prove each shipped policy allows, denies or escalates correctly; the approvals queue works with timeout default.
- **P5-A4** Failover: simulated timeout, error, invalid output, circuit open and budget exhaustion each fall back within one tick, with the indicator updated and automatic recovery (tests).
- **P5-A5** Determinism: `heuristic` and `replay` runs reproduce identical hashes; recorded AI runs replay exactly.
- **P5-A6** Decision log is complete (every decision has trigger, commands, governance, execution, outcome, rationale) and rationale references only entities present in the brief (automated check).
- **P5-A7** NL commands: at least 15 phrased cases (including ambiguous and malicious ones) behave correctly with confirmation and audit.
- **P5-A8** Injection tests pass: no instruction embedded in data or supervisor text can bypass policy or safety.
- **P5-A9** Evaluation report exists with paired seeds, confidence intervals, cost and latency, honest conclusions, and held-out seeds recorded for the reviewer.
- **P5-A10** Cost and latency stay within configured budgets in a 1-simulated-hour AI run; numbers reported; p95 decision latency reported.
- **P5-A11** The demo does not freeze when the network is removed mid-run (manual and scripted test).
- **P5-A12** All Phase 1 to 4 acceptance checks still pass.
- **P5-A13** Change drills CD-1, CD-3, CD-5, CD-6 pass with files-touched recorded.
- **P5-A14** No secrets in the repo or logs; docs accurate.

# FINAL REPORT
`docs/phase5-report.md`: criteria with evidence, the evaluation table, cost/latency data, decisions (including the agent consolidation), limitations (state plainly where the AI does not help), handoff notes for Phase 6. Stop. Do not start Phase 6.

=== END PHASE 5 BUILD PROMPT ===

---

=== BEGIN PHASE 5 REVIEW PROMPT ===

# ROLE
Independent, strict, read-only reviewer for Phase 5 of RoboFleet. Write only `reviews/phase-5-review.md`.

# READ FIRST
`docs/playbook/00-master-plan.md`, `docs/playbook/01-review-protocol.md` (apply fully), `docs/phase5-report.md` (claims to verify), `reviews/phase-4-review.md` (confirm resolved).

# VERIFY
P5-A1 to P5-A14 yourself. Run the evaluation on the **held-out seeds 11 to 20** (not the builder's seeds) in `baseline`, `heuristic` and `ai` (or `replay` if no API access) modes, and compare with the report. Step 0 must verify the Anthropic model ids, pricing and tool-use features actually in use are current.

# PHASE-SPECIFIC CHECKS
- **P5-R1 Command path audit.** Trace every path from LLM text to engine state. Prove by reading code and by an adversarial test harness that nothing reaches the engine without schema validation and governance, and nothing moves a robot except through the SafetyGuard. Any bypass is P0.
- **P5-R2 Red team.** Attempt at least 20 attacks: orders with SKU names containing instructions, supervisor commands that try to disable policies or the SafetyGuard, requests to reveal prompts or keys, very long inputs, unicode tricks, conflicting commands, rapid command flooding, forged approvals. Record each attempt and outcome.
- **P5-R3 Value honesty.** From your held-out run, does AI mode beat the strong baseline on any KPI with statistical support (paired seeds, confidence intervals)? Does the report's conclusion match your numbers? If the report overclaims, P1. If AI mode does not help, state where the value is claimed and whether it is evidenced.
- **P5-R4 Fallback realism.** Cut the network mid-run, add 10 s latency, return malformed JSON, return empty tool calls, exhaust the budget. The store must keep running and the indicators must be truthful. Measure time to fallback.
- **P5-R5 Explanation integrity.** Sample 30 decisions. Check each rationale against the brief and the event log: are all referenced entities and numbers true? Any hallucinated reason is P1; a pattern of them is P0 for the "explainable AI" claim.
- **P5-R6 Cost and latency.** Compute cost per simulated hour and per decision at current pricing; check budgets are enforced; check that a runaway loop cannot burn budget.
- **P5-R7 Agent design review.** Are the four specialists justified? Where an exact tool exists, does the agent use it, or does the LLM do geometry or arithmetic? Does the orchestrator arbitrate conflicts or just concatenate? Could a simpler design match performance (SR-2)?
- **P5-R8 NL command quality.** Test 40 phrasings, including typos, mixed Hindi-English phrasing if relevant to the target users, ambiguity, negation, and multi-step requests. Measure correct parse rate, clarifying-question behaviour and safety.
- **P5-R9 Prompts as data.** Are prompts versioned, free of secrets and scenario hacks, and do they contain instructions the code cannot enforce (a sign of misplaced trust)? Check for overfitting to seeds.
- **P5-R10 Demo risk.** Run the exit demo three times from cold start; list any failure modes. Check the mode indicator is never misleading (for example showing "live" while in fallback).
- **P5-R11 Pitch credibility.** Check that no UI text or doc calls the system "autonomous store", "no humans" or similar beyond what is evidenced; check the supervisor's role is described accurately.

# CHANGE DRILLS FOR THIS PHASE
CD-1, CD-3, CD-5, CD-6.

# PHASE 5 WORTH-IT QUESTIONS
1. Does the AI layer add genuine, evidenced value, or is it theatre? What exactly would you cut or reframe?
2. Is the governance layer strong enough that a customer's safety officer would accept it?
3. Would a technical buyer find the decision log credible and useful?
4. What are the top three ways this demo could embarrass you in front of a company, and are they mitigated?
5. What must change before Phase 6 starts?

# OUTPUT
Follow the review protocol's output template exactly: mechanical verdict, score arithmetic, change list with acceptance tests, suggested GSD task list.

=== END PHASE 5 REVIEW PROMPT ===
