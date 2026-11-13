# Phase 7 — Evidence, Pitch and Flagship Hardening

Run the build prompt first, then the review prompt in a **fresh** session. Phase 6 must be tagged `phase-6-complete` before starting.

---

=== BEGIN PHASE 7 BUILD PROMPT ===

# ROLE AND MISSION
You are the lead engineer for Phase 7 of 7 of RoboFleet. Turn a working system into a **flagship you can put in front of a company**: reproducible evidence, a hardened and packaged demo that cannot easily fail on stage, a pitch kit grounded in measured results, an integration story for a prospect's real order feed, and a clean, documented, licence-compliant repository. Add no big new features; cut what does not earn its place.

# READ FIRST
1. `docs/playbook/00-master-plan.md` (SR-1 to SR-12, presentation stance and claims policy in section 2, repo reuse map in section 9).
2. `docs/playbook/01-review-protocol.md` (build to pass it).
3. All `docs/phase*-report.md` files and `reviews/phase-*-review.md` files. Every open P0 to P2 item from every earlier review must be resolved or explicitly accepted in `DECISIONS.md` with the owner's name.

# HOW TO WORK
GSD loop; SR-1 to SR-12. SR-3 (surgical changes) matters most now: harden, do not rebuild. Where something is weak and not worth fixing, cut it and say so. Every number you publish must come from an artifact you can regenerate.

# PHASE GOAL (exit demo)
From a fresh clone on a clean machine, one command (`make demo`) starts the full stack in under 10 minutes of setup, runs the scripted 3-minute pitch demo (and a 10-minute extended one) with the AI live, in fallback, or in replay mode, and survives a network cut, a browser refresh and a laptop swap. `make evidence` regenerates every figure in the pitch kit. `make verify` runs the full strict self-check.

# NON-GOALS
No new product features, no new agents, no new fault types, no rewrites. Bugs and polish only, plus the items below.

# SPECIFICATION

## A. Evidence harness
- `python -m robofleet.cli evidence` runs the full matrix: strategies (`fcfs_nearest`, `edf_deadline`, `batch_greedy`, `heuristic`, `ai` or `replay`) by scenarios (normal evening, rush, match-night spike, plus the chaos library) by at least 10 seeds (default 20), paired seeds, writes `reports/evidence-<date>/` containing: per-run metrics, summary tables with means, standard deviations, 95 percent confidence intervals and effect sizes, plots (PNG and data CSV), a manifest (git commit, config hashes, seeds, versions, machine info, wall time), and an `evidence.md` summary.
- Held-out seeds are fixed in config and never used for tuning (record this).
- Results are labelled with the provider mode for any AI run. If AI is run live, its recorded I/O is stored so the run can be replayed exactly.
- `docs/CLAIMS.md` is rebuilt from the evidence: every claim has an ID, the exact wording permitted, the artifact path, the scenario and seeds, the confidence interval, and the stated assumptions. Claims without evidence are removed.

## B. Replay, recording and timeline
- Record any run (events plus periodic snapshots) and replay it in the UI with a timeline scrubber, speed control and bookmarks at alerts and decisions. Replay uses the same renderers and panels.
- A "demo recording" mode that plays a pre-recorded high-quality run entirely offline, used as the stage safety net. The Environment panel labels the mode accurately ("Recorded run").

## C. Performance and soak
- Targets, measured and reported with hardware and method: backend 50 robots under a 3x rush for 2 simulated hours without memory growth beyond a stated bound and without event-loop lag above a stated threshold; frontend 60 fps median at 50 robots in 2D, 3D and split views over a 60-minute soak; start-to-first-render time; reconnect time.
- Profile and fix the top three hotspots only if they miss target; otherwise leave them alone.

## D. Hardening
- **Security:** authentication and authorisation reviewed end to end (roles from Phase 6); rate limiting on every public endpoint; input validation and size limits; secure headers and CORS from config; dependency audit (backend and frontend) with no known high or critical advisories unresolved; SBOM generated (`make sbom`); secrets scan of the working tree and git history clean; `.env.example` complete; no default credentials.
- **Reliability:** graceful shutdown, crash recovery (restart resumes from the latest snapshot and event log tail, or starts clean with a clear message), health checks, bounded queues, timeouts everywhere.
- **Observability:** structured logs with request and run IDs, a metrics endpoint (Prometheus text format) for key operational gauges, and a diagnostics page (versions, config hash, adapter states, AI mode and cost, frame budget).
- **Compatibility:** supported Python and Node versions documented and tested; browsers (current Chrome, Edge, Firefox, Safari where WebGL permits) smoke-tested.

## E. Packaging and one-command operation
- `docker compose up` (backend, frontend, optional reverse proxy) and `make demo` for local use. Pinned dependency lockfiles. A `make verify` target runs: lint, types, unit and property tests, determinism check, safety fuzz, schema compatibility, magic-number scan, docs link check, secrets scan, licence check, a short evidence run, Playwright suite, and prints a pass/fail table.
- CI workflow file (GitHub Actions or equivalent) running `make verify` without network or API keys (using `heuristic` and `replay`).
- **Offline and stage safety:** demo works with no internet using `replay` AI mode; a preflight command (`make preflight`) checks ports, GPU/WebGL, screen resolution advice, API key presence, adapter and mode status, and prints a go/no-go.

## F. Integration story (CA-2)
- `docs/INTEGRATION.md`: how a prospect connects their data. Three paths: CSV replay of historical orders to calibrate and test; webhook ingest for live order feeds (payload, auth, idempotency, rate limits, error handling); and a calibration guide to fit demand profile, basket size distribution and SKU catalogue from their exports (a `calibrate` command that reads their CSVs and produces a profile and catalogue with a fit-quality report).
- A worked end-to-end example with a synthetic "customer export" that is clearly an example file, run through `calibrate` and `csv_replay`, producing a before-and-after KPI comparison in the digital twin.
- State plainly in the document what is and is not integrated: the digital twin consumes real order data; robot control is simulated; no partner API is claimed.

## G. Pitch kit (all content derived from `CLAIMS.md` and evidence)
Create in `pitch/`:
1. `demo-script-3min.md` and `demo-script-10min.md`: second-by-second scripts (what is on screen, what is said, which control is clicked, which fallback to use if something fails).
2. `deck-outline.md`: slide-by-slide outline (problem, product, live demo, how it works, evidence with the actual charts, resilience, integration path, roadmap, ask), including exactly one slide that states the environment truthfully ("RoboFleet digital twin: simulated fleet and store, real data adapters") and the standard footnote for every number ("Measured in the RoboFleet digital twin under the stated assumptions").
3. `one-pager.md`: a concise leave-behind.
4. `roi-model.md` (plus a spreadsheet generated from config): a what-if model where the prospect enters their order volume, labour cost and SLA; assumptions listed; outputs labelled as estimates from the twin, not guarantees.
5. `faq-diligence.md`: honest answers to the hardest questions a technical or operations buyer will ask (is it real, what is simulated, how were the baselines chosen, how does it scale, what happens when the AI is wrong, what safety layer exists, what hardware is assumed, what would a pilot look like, what are the limits).
6. `pilot-proposal.md`: a scoped pilot outline (calibration on their data, digital-twin what-if study, success metrics, timeline, what they provide, what we deliver) with no claims beyond the evidence.
7. `risks-and-limits.md`: known limitations stated plainly, for internal use and for sharing when asked.

## H. Repository polish
- `README.md` (what it is, a screenshot gallery, five-minute quickstart, architecture overview, links), `docs/ARCHITECTURE.md` brought fully up to date with diagrams (Mermaid), `docs/EXTENDING.md` verified by performing every drill, `docs/THIRD_PARTY.md` complete with licences and attributions, `LICENSE` chosen deliberately (record the choice and reasons), `CONTRIBUTING.md`, `SECURITY.md`, a changelog, and a docs link check passing.
- **Licence audit:** every reused snippet has a header and a `THIRD_PARTY.md` row; confirm sources' current licences; remove anything from a repo without a visible permissive licence.
- **Simplicity pass:** run `/ponytail-audit` (if installed) and the review protocol's simplicity checks; delete dead code, unused configs, unused dependencies and stale docs. Record lines deleted.
- **Visual polish pass:** fix every visual defect listed in earlier reviews; produce final screenshots and a 60-second screen recording script (do not fabricate recordings).

## I. Flagship checklist (must be filled with evidence in the final report)
1. One clear claim, supported by evidence against a strong baseline.
2. Reproducible: `make evidence` regenerates the numbers; replay reproduces runs exactly.
3. Stable: 2-hour soak with no crash, leak or console error; stage-safety modes tested.
4. Honest: Environment panel accurate; claims register complete; no untraceable number.
5. Dynamic: all change drills pass; `EXTENDING.md` verified.
6. Safe: SafetyGuard exclusivity proven; AI behind governance; audit complete.
7. Documented and licensed: docs accurate; `THIRD_PARTY.md` complete.
8. Pitch-ready: scripts, deck outline, one-pager, ROI model, FAQ and pilot proposal exist and match the evidence.
9. Maintainable: `make verify` green in CI; dependency audit clean.

# CHANGE DRILLS THIS PHASE MUST PASS
Re-run **all** applicable drills (CD-1 to CD-9) as part of `make verify` and report files touched.

# ACCEPTANCE CRITERIA
- **P7-A1** `make evidence` regenerates the evidence directory with paired-seed tables, confidence intervals, effect sizes, plots and a manifest; held-out seeds recorded.
- **P7-A2** `CLAIMS.md` is complete: every claim traces to an artifact path, scenario, seeds and interval; no claim lacks evidence; wording matches what the evidence supports.
- **P7-A3** Replay reproduces any recorded run's final hash exactly; the timeline UI works; the offline recorded-demo mode runs with no network.
- **P7-A4** Soak and performance targets are met or the misses are documented with profiles: backend 2 simulated hours at 50 robots under 3x rush; frontend 60 fps median over 60 minutes in each view.
- **P7-A5** Security checklist passes: auth on every state-changing path, rate limits, input limits, no unresolved high or critical advisories, SBOM generated, clean secrets scan including history.
- **P7-A6** Crash and restart behaviour is tested and documented; graceful shutdown flushes logs; health checks work.
- **P7-A7** `docker compose up` and `make demo` work on a clean machine from the README in under 10 minutes (timed, with the machine described).
- **P7-A8** `make verify` is green locally and in CI without network or API keys.
- **P7-A9** Integration: `calibrate`, `csv_replay` and webhook paths work end to end on the worked example; `INTEGRATION.md` is accurate and states limits plainly.
- **P7-A10** Pitch kit complete and consistent with `CLAIMS.md`; the deck outline contains the single honest environment slide and the standard footnote; the FAQ's answers are true.
- **P7-A11** Licence audit: every reused snippet attributed and permissively licensed; none from no-licence repos.
- **P7-A12** All change drills pass; `EXTENDING.md` verified by performing each one.
- **P7-A13** All earlier phases' acceptance checks and every earlier review's P0 and P1 items are verified closed.
- **P7-A14** Preflight command gives a correct go/no-go in at least five induced failure situations (port in use, no API key, no WebGL, adapter down, stale build).
- **P7-A15** Final screenshots exist; visual defects from earlier reviews resolved.

# FINAL REPORT
`docs/phase7-report.md`: the flagship checklist with evidence, the evidence summary, performance and soak numbers, remaining known issues, accepted risks (owner-approved), and a clear statement of what the product is and is not. Tag `phase-7-candidate` (not complete) and stop; the tag `phase-7-complete` is applied only after the review verdict.

=== END PHASE 7 BUILD PROMPT ===

---

=== BEGIN PHASE 7 REVIEW PROMPT ===

# ROLE
Independent, strict, read-only final reviewer for RoboFleet. You act as a skeptical technical due-diligence reviewer for a company evaluating the product. Write only `reviews/phase-7-review.md`.

# READ FIRST
`docs/playbook/00-master-plan.md`, `docs/playbook/01-review-protocol.md` (apply fully), `docs/phase7-report.md` (claims to verify), all earlier `reviews/phase-*-review.md` (confirm every P0 and P1 is closed; list any that are not).

# VERIFY
P7-A1 to P7-A15 yourself. This review must be run on a **clean machine or container** that you set up from the README alone, timing every step. Record every point where the README is wrong, incomplete or slow.

# PHASE-SPECIFIC CHECKS
- **P7-R1 Evidence re-derivation.** Run `make evidence` on a clean checkout. Compare every number in `CLAIMS.md`, `pitch/` and the UI with your regenerated numbers. Any number that does not reproduce within its stated interval is P1 (P0 if it appears in the pitch as a headline claim).
- **P7-R2 Statistical audit.** Check pairing, seed independence, held-out discipline, multiple-comparison handling, effect sizes, and that no result was cherry-picked (compare the evidence set with the full run list). Look for baselines changed after seeing results (check git history around baseline files).
- **P7-R3 Claims audit (strict).** Read every sentence in `pitch/`, the README, the UI text and the Environment panel. Classify each factual statement as: PROVEN (artifact), ASSUMED (stated assumption), or UNSUPPORTED. List every UNSUPPORTED or overclaiming statement. Forbidden: any implication of real customers, real stores, deployed robots, or production results; "fully autonomous store" or "no human" language beyond what is evidenced.
- **P7-R4 Honesty of presentation.** Confirm the single environment disclosure is accurate and discoverable, the deck outline's environment slide is truthful, and the footnote is applied consistently. Judge whether a sceptical buyer would feel misled at any point; if so, say exactly where.
- **P7-R5 Stage-safety drill.** Run the 3-minute script five times, each with a different induced failure (network off, API key invalid, browser refresh, backend restart, projector at a different resolution). Record outcomes and recovery time. Any unrecoverable stage failure is P1.
- **P7-R6 Security review.** Perform a focused penetration-style pass: auth bypass attempts, token leakage, injection through webhook and CSV paths, resource exhaustion, SSRF-like behaviour if any URL inputs exist, unsafe deserialisation, CORS misconfiguration, dependency advisories. Review the SBOM and dependency audit output. Search git history for secrets.
- **P7-R7 Licence and attribution audit.** Verify `THIRD_PARTY.md` against the actual code: for every reused snippet, confirm source, licence at the time of copying and attribution. Confirm no copied code from no-licence or incompatible repos. Check the project's own `LICENSE` choice is consistent with dependencies.
- **P7-R8 Integration honesty.** Execute the worked integration example. Then try a deliberately messy customer CSV (missing columns, odd encodings, duplicate ids, impossible times). The tool must fail clearly or repair with a report, never silently produce garbage. Check that `INTEGRATION.md` does not imply partner API integration.
- **P7-R9 Dynamism final exam.** Perform all change drills CD-1 to CD-9 plus three new unplanned changes chosen by you (for example add a new robot kind with different speed and capacity, add a second dispatch bay, add a policy that changes behaviour by time of day). Report files touched and what required code. Compare with the Phase 1 promise of "no locked constraints".
- **P7-R10 Maintainability.** Run the simplicity audit across the codebase: size, duplication, dead code, dependency count and weight, test quality (mutation spot-checks), documentation drift. Estimate how long a new engineer would take to make the first meaningful change using only the docs.
- **P7-R11 Scale and limits.** Push beyond targets: 100 robots, 5x rush, 6-hour soak (or the longest you can). Report the break point and the failure behaviour; check the FAQ's statements about scale are true.
- **P7-R12 Pitch fit.** Read the pitch kit as the target buyer would. Is the story clear, credible and differentiated? Which three slides or claims are weakest? Is the pilot proposal realistic and modest enough to be credible?

# CHANGE DRILLS FOR THIS PHASE
CD-1 to CD-9 (all applicable), plus the three unplanned changes in P7-R9.

# FLAGSHIP CHECKLIST (score each item PASS or FAIL with evidence)
1. One clear, evidenced claim against a strong baseline.
2. Reproducible evidence and replay.
3. Stable under soak and stage-failure drills.
4. Honest presentation and claims register.
5. Dynamic: change drills pass.
6. Safe: SafetyGuard exclusive, AI governed, audit complete.
7. Documented and licensed correctly.
8. Pitch kit complete and truthful.
9. Maintainable and CI-verified.
**Flagship-ready requires 9 of 9 PASS and no open P0 or P1.**

# PHASE 7 WORTH-IT QUESTIONS
1. Is this a flagship, or a polished side project? Answer with the checklist and your judgement, and name the two weakest elements.
2. If you were the buyer's technical lead, what would you still distrust, and what evidence would change your mind?
3. What is the strongest honest sentence the owner can say about this product? What is the one sentence they must never say?
4. What three things, if done next, would most increase real-world credibility (for example a pilot on real order data, an external safety review, a hardware-in-the-loop demo)?
5. What must change before the final tag `phase-7-complete`?

# OUTPUT
Follow the review protocol's output template exactly. Add a final section "Flagship Decision": READY / READY WITH CONDITIONS / NOT READY, the conditions, and the ordered GSD task list to reach READY.

=== END PHASE 7 REVIEW PROMPT ===
