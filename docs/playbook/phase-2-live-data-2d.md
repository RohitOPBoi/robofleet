# Phase 2 — Live Data and 2D Command Centre

Run the build prompt first, then the review prompt in a **fresh** session. Phase 1 must be tagged `phase-1-complete` before starting.

---

=== BEGIN PHASE 2 BUILD PROMPT ===

# ROLE AND MISSION
You are the lead engineer for Phase 2 of 7 of RoboFleet. Turn the Phase 1 headless twin into a **live product**: a streaming API, pluggable order adapters (including a realistic demand engine), and a professional browser command centre with a 2D live map, order board, alerts, KPIs and controls. A viewer opening the page should see a store that looks and behaves like a real operation.

# READ FIRST
1. `docs/playbook/00-master-plan.md` (SR-1 to SR-12, change axes, presentation stance in section 2).
2. `docs/playbook/01-review-protocol.md` (build to pass it).
3. `docs/phase1-report.md`, `docs/ARCHITECTURE.md`, `docs/CONTRACTS.md`, `docs/EXTENDING.md`.

# HOW TO WORK
Use GSD (discuss, plan, execute, verify). Follow SR-1 to SR-12. Simplicity first: do not add a state-management or UI framework unless you can justify it in `DECISIONS.md`. Evolve contracts additively (minor version bump, changelog, migrations if needed). Do not modify Phase 1 behaviour except where this prompt requires it; every such change is recorded.

# PHASE GOAL (exit demo)
`make demo` starts backend and frontend. In a browser at 1920x1080 you see: live orders arriving at a realistic, time-of-day-shaped rate; 20 robots moving smoothly on a 2D map; alerts appearing and clearing; KPI bar updating; controls to pause, change speed and trigger a rush. Switching the order source between the demand engine, CSV replay and webhook ingest is a config change only.

# NON-GOALS
No order fulfilment (robots still use the placeholder dispatcher; orders arrive, wait, and show deadline countdowns), no 3D, no LLM or agents.

# SPECIFICATION

## A. Backend API (FastAPI, async)
- Simulation runs in an asyncio task with a **wall-clock pacing layer** (outside the core): real-time, speed multiplier (0.5x to 20x configurable), pause/resume, single-step.
- **WebSocket `/ws`** protocol, versioned:
  - Envelope `{v, type, seq, tick, payload}`.
  - On connect: `hello` (schema version, server capabilities, feature flags), then `static_world`, then `snapshot`.
  - Then `delta` messages at a configurable rate (default 10 Hz) containing changed robots, orders, alerts, KPIs and new events since the last seq.
  - Client may send `resync` or `ping`. If a client's seq gap is detected, the server sends a full `snapshot`.
  - Backpressure: a slow client gets coalesced deltas, never an unbounded queue. Multiple clients supported.
- **Control channel** (REST or WS, same auth): pause, resume, speed, step, `scenario.start`, `overlay.apply` (rain, match night, rush), `overlay.clear`, `emergency_stop`/`resume` (scope all, robot, zone), `block_cells`/`unblock_cells`. All require a bearer token from env (`ROBOFLEET_TOKEN`); read-only streaming may be open or token-gated by config.
- REST: `GET /health`, `/api/scenarios`, `/api/config/effective`, `/api/rules`, `/api/environment`, `/api/runs`, `POST /api/ingest/orders` (webhook adapter, see C). OpenAPI published.
- Structured logging; request IDs; CORS from config; graceful shutdown that flushes the event log.
- **Type sharing:** generate TypeScript types from the JSON Schemas/OpenAPI in `make types`. A CI check fails if generated types are stale.

## B. Orders
- Implement the `Order` lifecycle states now (RECEIVED, QUEUED, plus the later states defined but unused). In this phase orders enter RECEIVED then QUEUED and show `deadline_tick`, an `at_risk` flag computed by a configurable rule (for example time remaining under a threshold relative to a nominal service time), and priority.
- Emit `order.received` and `order.at_risk` events. Store orders in memory with a bounded history (config) and in the event log.

## C. Order adapters (CA-2), all behind the `OrderSource` port
1. **`demand_engine`** (default; display name "Synthetic Demand Engine"):
   - Non-homogeneous Poisson arrivals from the Phase 1 demand profile (hourly curve, weekday/weekend, overlays such as rain, match night, festival).
   - Basket size distribution, SKU choice by popularity with the Phase 1 affinity matrix, quantity distribution, an `URGENT` share, deadline derived from a configurable SLA tier.
   - Fully seeded, replayable, with a "rush" overlay that multiplies the rate for a duration.
   - Orders reference only SKUs that exist and have stock; stock-outs are surfaced as order issues (flag only; handled in Phase 3 and 6).
2. **`csv_replay`**: replays a CSV of real or exported orders (timestamp, order id, lines, priority, deadline) at 1x or accelerated speed. Ship a documented example file and a validator that reports row-level errors.
3. **`webhook`**: `POST /api/ingest/orders` with API-key auth, JSON-schema validation, idempotency by order id, rate limiting, and clear 4xx errors. This is how an external partner would feed real orders.
- All three are selectable and parameterised by config. Document each in `docs/ADAPTERS.md` including the exact payload format.

## D. Frontend (Vite, React, TypeScript)
Build a professional operations UI. Design for projector and laptop use (1366x768 to 4K), dark theme default with a light theme, a coherent design-token system (colour, spacing, type scale), consistent iconography, and polite micro-animation.
- **Top bar:** store name, clock (sim time in local format) and speed/pause controls, connection status, KPI strip (orders in queue, orders received per hour, at-risk orders, robots moving/waiting/charging/unavailable, active alerts), Environment badge ("Digital Twin") that opens the Environment panel.
- **Left:** order board (virtualised list, tabs: Incoming, At risk, All), each order with id, line count, priority chip, countdown to deadline with risk colouring.
- **Centre:** Canvas 2D map: layout from static world; racks, aisles with lane arrows (toggle), stations, chargers, dispatch bay, supervisor desk, zones (toggle). Robots drawn with heading, battery ring and state colour; smooth interpolation using `motion.progress`; pan, zoom, fit-to-screen, click to select; selected robot panel (state, battery, position, task). Optional overlays: congestion heat, planned paths, labels.
- **Right:** alert drawer (severity, category, message, age, "locate" focusing the map, `requires_human` badge), an event feed, and a panel host.
- **Environment panel:** reads `meta.environment` and `/api/environment`: mode, demand source name, robot layer, active adapters, schema version, seed. This is the single disclosure surface.
- **Controls:** pause/resume/step/speed, rush button, overlay toggles, e-stop (confirmation required), block-cells tool (draw on map; confirmation), all calling the control channel with the token.
- Keyboard shortcuts, focus states, reduced-motion support, and a loading/empty/error state for everything. No "lorem", "sample" or placeholder text anywhere.
- **State:** a plain reducer/store that applies deltas, handles resync, and exposes selectors. Rendering must hold 60 fps with 50 robots and 300 live orders on a mid-range laptop.
- **Panels registry (CA-9):** panels (order board, alert drawer, event feed, Environment, and later decision log, KPI charts) are declared in a config file and rendered through a registry, so adding a panel is one component plus one config entry.
- Use a design/UI skill if one is installed. Record design decisions in `docs/UI.md`.

## E. Testing
- Backend: protocol tests (hello, snapshot, delta ordering, resync after gap, backpressure), adapter tests (rate statistics over long runs match the profile within tolerance; CSV errors; webhook auth, idempotency, rate limit), control-channel auth tests.
- Frontend: unit tests for the reducer and interpolation; Playwright end-to-end that starts the stack, waits for orders and robots, asserts DOM and canvas facts, and captures screenshots into `reports/screens/`.
- Soak: 30-minute run at 5x speed with one reconnecting client; memory and message-rate must stay flat.

## F. Documentation
`docs/API.md` (REST, WS protocol with examples), `docs/ADAPTERS.md`, `docs/UI.md`, updates to `ARCHITECTURE.md`, `CONFIG.md`, `EXTENDING.md`, `CONTRACTS.md` (version bump and changelog), `ASSUMPTIONS.md` (demand curve, basket and SLA parameters with sources), `phase2-report.md`.

# CHANGE DRILLS THIS PHASE MUST PASS
- **CD-3** add a new event type end to end (backend event, schema, TS type, feed rendering) in at most 3 files plus docs.
- **CD-4** switch the order source from `demand_engine` to `csv_replay` by config only.
- **CD-9** add a new panel and a new theme: at most 2 files plus config.
- **CD-2** change the layout and robot count via config only and see it rendered without frontend code changes.

# ACCEPTANCE CRITERIA
- **P2-A1** `make demo` works from a fresh clone following the README in under 10 minutes, on a clean machine or container.
- **P2-A2** WS protocol behaves as specified: sequence continuity, resync, backpressure, multi-client; all tests pass.
- **P2-A3** Control endpoints reject missing or wrong tokens; no state-changing endpoint is open.
- **P2-A4** Demand engine arrival counts per simulated hour match the configured profile within a stated statistical tolerance over a 24 simulated-hour run (test); overlays visibly change the rate.
- **P2-A5** CSV replay and webhook adapters work with validation errors that name the row or field; webhook is idempotent and rate-limited (tests).
- **P2-A6** The UI renders layout, robots, orders, alerts and KPIs from the stream with no console errors; Playwright suite passes.
- **P2-A7** 60 fps median with the `large` preset (50 robots) and 300 orders on a mid-range laptop; measured and reported with the method.
- **P2-A8** Reconnection: killing and restarting the backend leaves the UI recovering to a correct state with no manual refresh.
- **P2-A9** Environment panel is accurate and reachable in one click; no placeholder text exists in the UI (automated scan of source and rendered DOM).
- **P2-A10** Generated TS types are current; contract version bump and changelog are correct; `schema_compat` passes.
- **P2-A11** All Phase 1 acceptance checks still pass (determinism, safety, drills).
- **P2-A12** Change drills CD-2, CD-3, CD-4, CD-9 pass with files-touched recorded.
- **P2-A13** Accessibility basics: keyboard reachable controls, contrast checks pass on key text, reduced-motion respected.
- **P2-A14** Docs accurate; every documented command and endpoint works.

# FINAL REPORT
Write `docs/phase2-report.md`: criteria with evidence, measured numbers (fps, message rates, latency, soak memory), screenshots listed in `reports/screens/`, decisions and deviations, limitations, handoff notes for Phase 3. Stop. Do not start Phase 3.

=== END PHASE 2 BUILD PROMPT ===

---

=== BEGIN PHASE 2 REVIEW PROMPT ===

# ROLE
Independent, strict, read-only reviewer for Phase 2 of RoboFleet. Write only `reviews/phase-2-review.md`.

# READ FIRST
`docs/playbook/00-master-plan.md`, `docs/playbook/01-review-protocol.md` (apply fully), `docs/phase2-report.md` (claims to verify, not truth), and the previous review `reviews/phase-1-review.md` to confirm its change list was resolved.

# VERIFY
P2-A1 to P2-A14 by running things yourself. Re-measure fps, message rates and the soak yourself.

# PHASE-SPECIFIC CHECKS
- **P2-R1 Protocol abuse.** Write a script that: connects 50 clients, one very slow; sends malformed JSON, oversized messages, unknown message types, replayed or out-of-order control commands; floods the webhook with valid and invalid orders; sends duplicate order ids; tries SQL/JSON/HTML injection in string fields. The server must stay up, stay correct and return clear errors.
- **P2-R2 Auth.** Enumerate every route and message type; confirm each state-changing one requires auth and that tokens are not logged or exposed to the frontend bundle.
- **P2-R3 Stream correctness.** Compare the client-reconstructed state to the server's authoritative snapshot at 100 random ticks, including after forced disconnects. Any divergence is P1.
- **P2-R4 Demand realism.** Plot (or tabulate) arrivals per hour for a simulated day and overlay effects. Does the curve look like real quick-commerce demand (evening and lunch peaks, event spikes)? Check basket sizes and affinities for plausibility, and that no order references an unstocked or nonexistent SKU.
- **P2-R5 Visual review.** Take your own screenshots at 1366x768, 1920x1080 and 3840x2160, dark and light. Judge as a procurement lead evaluating an operations product: hierarchy, density, readability from 3 metres on a projector, colour semantics, empty and error states. List concrete visual defects.
- **P2-R6 Performance.** Profile the frontend for 5 minutes at 50 robots: frame times, long tasks, memory growth, GC pauses. Backend: CPU, memory, event-loop lag.
- **P2-R7 Disclosure surface.** Verify the Environment panel is the only disclosure surface, it is accurate for each adapter (changing the adapter changes the displayed source), and nothing in the UI overclaims (for example "live store", "real orders") when using the demand engine.
- **P2-R8 Adapter seam.** Confirm the three adapters share one port and that swapping works at runtime start by config only. Confirm the webhook adapter can be used with a real external client (curl or a small script).
- **P2-R9 Simplicity audit.** Dependencies added (frontend and backend): justify each against SR-2. Lines of UI code vs value. Dead components. Over-built state management.

# CHANGE DRILLS FOR THIS PHASE
CD-2, CD-3, CD-4, CD-9.

# PHASE 2 WORTH-IT QUESTIONS
1. Would a first-time viewer understand what is happening within 30 seconds, without narration?
2. Does the demo already feel like a product? What single change would improve that most?
3. Is the adapter story credible enough to answer "can it run on our data"?
4. Which UI or API choices will hurt Phases 3 to 6 (for example the delta format, the panel host, the control channel)?
5. What must change before Phase 3 starts?

# OUTPUT
Follow the review protocol's output template exactly, with the mechanical verdict, a scored table, the change list and a suggested GSD task list.

=== END PHASE 2 REVIEW PROMPT ===
