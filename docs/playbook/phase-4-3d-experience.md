# Phase 4 — 3D Experience

Run the build prompt first, then the review prompt in a **fresh** session. Phase 3 must be tagged `phase-3-complete` before starting.

---

=== BEGIN PHASE 4 BUILD PROMPT ===

# ROLE AND MISSION
You are the lead engineer for Phase 4 of 7 of RoboFleet. Build the **3D view** of the store: a polished, performant scene driven by the same state stream as the 2D map, with cinematic camera modes, alert beacons and synchronised selection. The 3D view is a renderer of the shared state; it never owns state.

# READ FIRST
1. `docs/playbook/00-master-plan.md` (SR-1 to SR-12, presentation stance).
2. `docs/playbook/01-review-protocol.md` (build to pass it).
3. `docs/phase3-report.md`, `docs/UI.md`, `docs/API.md`, `reviews/phase-3-review.md` (resolve all its open P0 to P2 items that touch the frontend).

# HOW TO WORK
GSD loop; SR-1 to SR-12. Simplicity first: reuse the existing store, selectors and panel registry. Add dependencies only with a recorded justification. No backend contract changes unless strictly required, and then additive only. Use the frontend design skill if installed.

# PHASE GOAL (exit demo)
At 1920x1080 a viewer can switch between 2D, 3D and split view; in 3D they see racks with bins, stations with queues, chargers, the dispatch bay and supervisor desk, and 20 to 50 robots carrying totes along their real paths. Clicking a robot or an alert in either view selects it in both. A "Cinematic" camera tours the store automatically, cutting to alerts when they appear. It holds 60 fps at 50 robots on a mid-range laptop and degrades gracefully on weak GPUs.

# NON-GOALS
No new simulation behaviour, no AI, no VR/AR, no external 3D asset downloads, no physics engine.

# SPECIFICATION

## A. Scene architecture (react-three-fiber with drei)
- **Procedural assets only.** All models are built in code from simple geometry (boxes, cylinders, rounded shapes) so there are no licence or loading issues. An **asset registry** (CA-9, CA-4) maps `robot.kind`, `cell type` and `zone type` to a builder function, so a new robot kind or station type adds one builder and one config entry.
- Scene is generated from `StaticWorld`: any valid layout renders without frontend code changes (test with the three presets and a hand-drawn ASCII layout).
- **Instancing:** racks, bins, floor tiles and lane markings use instanced meshes; robots use instancing with per-instance transforms, colour and state attributes. Target at most 200 draw calls at 50 robots.
- **Robots:** body, drive units, a status light, a lift or carrier plate, tote mesh when carrying (tote colour or label ties to the order). Heading and smooth interpolation from `motion.progress`; turn animation; subtle wheel rotation or motion cue.
- **Environment:** floor with lane arrows (toggle), racks with level boards, station booths with queue markers, chargers with glow when charging, dispatch bay with counter, supervisor desk with a simple seated figure and monitor glow, zone floor tints (toggle), walls. Lighting presets in config (clean daylight, warm evening, night ops), soft shadows with a quality tier switch.
- **State visualisation:** robot colour or light by state; battery bar sprite; congestion heat floor overlay (toggle); planned path ribbons for selected or all robots (toggle); order totes on the dispatch bay.
- **Alert beacons:** pulsing ring and vertical beam at the alert's cell, with a HUD label (severity colour, short text); clearing animates away. Beacons mirror the alert drawer exactly.
- **Labels:** screen-space labels with level-of-detail (only for selected, near, or alerting objects) to avoid clutter.

## B. Cameras
Modes, each declared in config (positions, FOV, easing), switchable by keys and a camera bar:
1. **Orbit** with sensible limits and a reset.
2. **Top isometric** (fixed pitch and yaw).
3. **Follow robot** (chase camera on the selected robot, smoothed).
4. **Station view** and **Dispatch view** preset cameras.
5. **Cinematic tour**: data-driven camera paths (waypoints, easing, dwell) that loop, and auto-cut to a new alert with a configurable cooldown and return afterwards. A manual input interrupts the tour and a short idle timer can resume it.
Transitions are eased; respect reduced-motion (cuts instead of sweeps).

## C. Synchronisation and layout
- Single source of truth: the existing store. Selection, focus and hover are shared state; selecting in 2D highlights in 3D and vice versa. Alert "locate" works in both.
- View switcher: 2D, 3D, split (side by side) with a draggable divider; the choice persists across reloads. A picture-in-picture mini-map (2D) over 3D is optional and toggleable.
- Panels (order board, KPI, alerts, fleet, Environment) behave identically in all views.

## D. Performance and quality tiers
- Target: 60 fps median and no frame over 33 ms in the 95th percentile at 50 robots, 300 orders, shadows on, 1080p, mid-range laptop integrated GPU. Report the exact hardware and method.
- **Auto quality:** measure frame time and step through tiers (shadows, resolution scale, instancing detail, post effects off, labels off) with hysteresis; show the current tier in a diagnostics overlay (toggle). Manual override in settings.
- **Budgets** recorded in `docs/UI3D.md` and enforced by a perf test in CI-able form: draw calls, triangles, texture memory, JS heap growth over 10 minutes (flat).
- WebGL capability detection: if WebGL2 is unavailable show a clear message and fall back to the 2D view (never a blank screen). Handle context loss and restoration.
- Memory hygiene: dispose geometries, materials and textures on unmount; no per-frame allocations in hot paths.

## E. Polish
- Subtle post effects only if budget allows (ambient occlusion or bloom on status lights, off in low tiers). No heavy effects that fail the performance target.
- Consistent colour semantics across 2D, 3D and alert severity (documented in `docs/UI.md`).
- A tasteful intro transition on first load and a loading state; no flash of empty scene.
- Accessibility: keyboard camera controls, visible focus, reduced-motion mode, colour-blind-safe state palette option.
- No placeholder text; all labels and units realistic.

## F. Testing
- Unit tests for geometry builders, transform interpolation, camera path evaluation, quality-tier controller.
- Playwright end-to-end: load 3D, wait for robots, assert scene stats exposed by a diagnostics hook (draw calls, robot instances, FPS sample), capture screenshots in each camera mode and lighting preset into `reports/screens/`.
- **Visual regression**: screenshot comparison with a tolerance for the main views.
- Soak: 30 minutes at 50 robots with shadows on; heap stays flat; no console errors.
- Context-loss test.

## G. Documentation
`docs/UI3D.md` (architecture, asset registry, camera config, quality tiers, budgets, how to add a robot kind, station type or camera path), updates to `UI.md`, `EXTENDING.md`, `ASSUMPTIONS.md` (visual scale choices), `phase4-report.md`.

# CHANGE DRILLS THIS PHASE MUST PASS
- **CD-4a** add a new robot kind visual: one builder and one config entry (at most 2 files plus config).
- **CD-9** add a new camera path and a new lighting preset through config only.
- **CD-2** change layout, robot count and zone through config only and see it correctly in 3D with no frontend code changes.

# ACCEPTANCE CRITERIA
- **P4-A1** 3D, 2D and split views work from the same stream; selection and alert location sync both ways (Playwright tests).
- **P4-A2** Any valid layout (three presets plus a hand-drawn ASCII one) renders correctly in 3D with no code changes.
- **P4-A3** 60 fps median and p95 frame under 33 ms at 50 robots and 300 orders at 1080p on the stated hardware, measured with the stated method; quality tiers engage and recover under an induced slowdown (test).
- **P4-A4** Draw calls at most 200 and JS heap growth flat over a 30-minute soak.
- **P4-A5** Robot positions in 3D match simulation state within one cell at all times and within a visually smooth interpolation (test comparing scene transforms with state at 100 random ticks).
- **P4-A6** Alert beacons match the alert drawer exactly (add, update, clear) over a run with many alerts (test).
- **P4-A7** All camera modes work; the cinematic tour cuts to alerts, respects cooldown and returns; manual input interrupts it.
- **P4-A8** WebGL fallback and context loss are handled without a blank screen (tests).
- **P4-A9** Accessibility options work: reduced motion, keyboard camera controls, colour-blind-safe palette.
- **P4-A10** No console errors or warnings in any Playwright run; no placeholder text in the UI.
- **P4-A11** Phase 1 to 3 acceptance checks still pass (backend unchanged or additively changed).
- **P4-A12** Change drills CD-2, CD-4a, CD-9 pass with files-touched recorded.
- **P4-A13** Screenshots of each camera mode and lighting preset exist in `reports/screens/`; docs accurate.

# FINAL REPORT
`docs/phase4-report.md`: evidence per criterion, performance data with hardware and method, screenshots listed, decisions, limitations, handoff notes for Phase 5 (what hooks exist for the decision log and AI overlays). Stop. Do not start Phase 5.

=== END PHASE 4 BUILD PROMPT ===

---

=== BEGIN PHASE 4 REVIEW PROMPT ===

# ROLE
Independent, strict, read-only reviewer for Phase 4 of RoboFleet. Write only `reviews/phase-4-review.md`.

# READ FIRST
`docs/playbook/00-master-plan.md`, `docs/playbook/01-review-protocol.md` (apply fully), `docs/phase4-report.md` (claims to verify), `reviews/phase-3-review.md` (confirm frontend items resolved).

# VERIFY
P4-A1 to P4-A13 yourself. Re-measure FPS and draw calls with your own method on the best and worst hardware you can access, and at 4K.

# PHASE-SPECIFIC CHECKS
- **P4-R1 Truthfulness of the scene.** At 50 random moments compare the 3D scene (via diagnostics or DOM hooks) to the authoritative snapshot: robots, carried totes, charging states, station queues, alerts. Any mismatch is P1. Any robot visibly passing through a rack or another robot is P1.
- **P4-R2 Performance stress.** Run 100 robots (above the target) to find the cliff; run with shadows and the highest tier; run a 60-minute soak; record frame-time histograms, heap, GPU memory if measurable. Try a low-end profile (CPU throttling 4x) and confirm graceful degradation.
- **P4-R3 Robustness.** Resize and rotate the window repeatedly; switch views rapidly 50 times; disconnect and reconnect the backend while in 3D; background the tab for 5 minutes; lose and restore the WebGL context. Look for leaks, blank screens, stuck cameras.
- **P4-R4 Visual review.** Capture your own screenshots in every camera mode and lighting preset at 1080p and 4K. Judge as a buyer's executive: does it look like a credible, professional product? List concrete defects (z-fighting, shimmering shadows, clutter, unreadable labels, harsh colours, ugly intersections, empty-looking store).
- **P4-R5 Projector test.** Check legibility at low contrast and from a distance: label sizes, alert beacon visibility, colour semantics under a colour-blind simulation.
- **P4-R6 Extensibility.** Do CD-4a, CD-9, CD-2 yourself. Also add a new station type visual with only config and one builder. Report files and time.
- **P4-R7 Simplicity audit.** Dependencies added and their bundle cost; dead shaders or components; effects that cost more than they add; code duplicated between 2D and 3D that should be shared selectors.
- **P4-R8 Cinematic quality.** Watch the tour for 10 minutes; note awkward cuts, motion sickness risks, repeating loops, bad framing during alerts.
- **P4-R9 Contract hygiene.** Confirm no backend contract changed non-additively and generated types are current.

# CHANGE DRILLS FOR THIS PHASE
CD-2, CD-4a, CD-9.

# PHASE 4 WORTH-IT QUESTIONS
1. Does the 3D view add real value for a pitch (comprehension, wow) beyond the 2D map, or is it decoration? Which parts carry the value?
2. Is the performance margin large enough to survive a weaker demo machine and a projector?
3. Which visual flaws would cost credibility in the first 10 seconds?
4. Is the state-to-visual pipeline clean enough for Phase 5 overlays (decision markers, AI annotations)?
5. What must change before Phase 5 starts?

# OUTPUT
Follow the review protocol's output template exactly: mechanical verdict, score arithmetic, change list with acceptance tests, suggested GSD task list.

=== END PHASE 4 REVIEW PROMPT ===
