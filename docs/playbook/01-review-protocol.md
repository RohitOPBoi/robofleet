# RoboFleet Playbook — 01 Review Protocol

Every phase review prompt tells the reviewer to apply this protocol. It is deliberately strict. Its job is to decide whether the phase is **worth keeping as built**, **needs specific changes**, or **must be redone**, and to produce a change list that can be turned straight into work.

---

## 1. Rules of engagement

1. **Independent and read-only.** Run in a *fresh* Claude Code session. Do not modify source, tests, configs or docs. The only file you may write is `reviews/phase-N-review.md`. Fixing is a separate step.
2. **Evidence only.** A criterion passes only if you personally ran a command, read the code, or inspected an artifact that proves it. Do not trust READMEs, the build report, commit messages or earlier claims. "Probably fine" is a FAIL.
3. **Unmeasured means failed.** If a number was not measured in this review (or in a committed artifact you re-verified), mark it UNVERIFIED, which counts as failing for gating.
4. **No benefit of the doubt, no cruelty.** Be exact and fair. Report strengths briefly; spend your effort on defects.
5. **Fresh facts.** Do Step 0 below before judging anything version- or market-dependent.
6. **Independence from the builder.** Re-run tests and benchmarks yourself. Write at least one *new* adversarial check the builder did not write, and run it.
7. **Quote locations.** Every finding cites `path:line` or a command and its output.

---

## 2. Step 0: Freshness check (do this first)

Use web search and the project's own tooling. Record results in the review under "Freshness".

- Latest stable versions and known deprecations or security advisories for each direct dependency actually used (backend and frontend). Flag anything more than one major version behind or with a known advisory.
- Anthropic model identifiers, pricing and limits used by the project (Phase 5 onward): confirm they still exist and are not deprecated.
- Installed tooling: GSD (`/gsd:help`, `/gsd:whats-new`), Karpathy skills, ponytail. Note version drift that changes how prompts should be run.
- Licences of every third-party snippet listed in `docs/THIRD_PARTY.md`; confirm the source repo's licence has not changed.
- Any reference-project fact the phase depended on (for example a repo's current licence or maintenance status).

---

## 3. Universal checks (U1 to U12). Apply every one, every phase

For each check record: **Result** (PASS / PARTIAL / FAIL / N/A / UNVERIFIED), **Evidence**, **Severity if not PASS**.

**U1 Build health.** Fresh clone, follow the README exactly. Lint, format check, type check and tests all pass. Record the exact commands and outputs. A README that does not work is a P1.

**U2 Test integrity.** Run `git diff phase-(N-1)-complete..HEAD -- '**/tests/**'` (or the equivalent for phase 1). Look for deleted or weakened assertions, widened tolerances, skipped or xfailed tests, and tests that cannot fail. Mutation spot-check: deliberately break three important behaviours in a scratch copy (do not commit) and confirm tests fail. Tests that survive mutation are a P1.

**U3 Scope fidelity.** Compare delivered work to the phase's build prompt. List missing items, partial items and unrequested extras. Unrequested features are a finding (SR-3).

**U4 Karpathy compliance.**
- *Think before coding:* `docs/DECISIONS.md` records assumptions and non-obvious choices; ambiguities were surfaced, not silently decided.
- *Simplicity first / ponytail:* look for speculative abstractions, one-implementation interfaces outside the declared change axes, unused code, reimplemented stdlib or existing helpers, needless dependencies. Run `/ponytail-audit` if installed; otherwise do it manually. Report approximate lines that could be deleted.
- *Surgical changes:* sample 5 commits; every changed line must trace to a requirement. Drive-by refactors are findings.
- *Goal-driven:* each acceptance criterion has a runnable check.

**U5 Dynamism audit (SR-5).**
- Run `tools/magic_numbers.py`; review the allowlist for abuse.
- Grep for hard-coded tunables, thresholds, ids, URLs, model names, colours and timings in logic.
- Check that every behaviour choice goes through a registry and config key.
- **Change drills** (section 4): perform them for real in a scratch branch and report files touched and time taken. A drill that needs more code changes than its limit is a FAIL.

**U6 Contract integrity (SR-6).** Run the schema compatibility check. Confirm `contracts/CHANGELOG.md` matches actual changes, version bumps are correct, migrations exist for breaking changes, and examples validate. Test that an old client payload still loads.

**U7 Determinism and replay.** Same scenario, seed and commands must produce identical state hashes in two separate runs. Different seeds must differ. Replay of a recorded event log must reproduce the final hash.

**U8 Safety boundary (SR-7).** Independently verify, with a checker you write, that no two robots share or swap cells and no robot leaves walkable cells or violates flow rules, across a long run and a randomised command fuzz. Confirm nothing outside the SafetyGuard mutates robot positions (grep and read). Confirm emergency stop works.

**U9 Security, secrets and licences.** Search the repo and history for secrets. Check input validation on every external entry point, authentication on control endpoints (once they exist), dependency audit output, and licence compliance of reused code. Anything copied without a permissive licence is a P0.

**U10 Docs accuracy.** Every documented command must work as written. Every documented config key must exist. Every documented file must exist. Docs describing behaviour the code does not have are a P1. Check `ASSUMPTIONS.md` entries have sources and dates.

**U11 Claims audit.** Every number or capability asserted in docs, UI, reports or the build report must trace to a reproducible artifact. List claims that cannot be traced. Overclaiming is a P1; claiming real deployments, customers or production results is a P0.

**U12 Product feel (SR-9).** Search source and runtime UI for placeholder text (lorem, sample, dummy, test, TODO, foo). Check units, currency, time formats and naming consistency. Check the Environment panel exists (Phase 2 onward) and is accurate. From Phase 2, take screenshots and judge them against a professional operations tool.

---

## 4. Change drills

A change drill measures how easy the system is to change. Do each applicable drill on a scratch branch, using only what documentation and the code allow. Record **files touched**, **lines changed**, **time**, and whether tests still pass. Revert afterwards.

| Drill | Task | Limit |
|---|---|---|
| CD-1 | Add a new placement or alert rule using YAML only | 0 code files |
| CD-2 | Add a new zone and change robot count and grid size through config | 0 code files |
| CD-3 | Add a new event type | at most 3 files plus docs |
| CD-4 | Swap the order data source (for example demand engine to CSV replay) through config | 0 code files |
| CD-5 | Add a new strategy (dispatcher, planner or baseline) through the registry | at most 2 files plus config |
| CD-6 | Add a new specialist agent or tool (Phase 5+) | at most 2 files plus config and prompt |
| CD-7 | Add a new KPI (Phase 3+) | at most 2 files plus config |
| CD-8 | Add a new fault type and a scenario using it (Phase 6+) | at most 2 files plus YAML |
| CD-9 | Add a new UI panel or theme (Phase 2+) | at most 2 files plus config |

Each phase review lists which drills apply.

---

## 5. Severity definitions

| Level | Meaning | Gate effect |
|---|---|---|
| **P0 Blocker** | Safety violation, data corruption, licence breach, false claim of real deployment, secrets in repo, crash on the main path | Verdict is NO-GO until fixed |
| **P1 Major** | Acceptance criterion failed or unverified, broken docs or README, test integrity problem, determinism break, dynamism drill failed, untraceable claim | Must be fixed before tagging |
| **P2 Moderate** | Quality, maintainability or polish problem that will hurt later phases | Fix before the next phase starts, or record an accepted-risk decision |
| **P3 Minor** | Nit, naming, small cleanup | Optional |

---

## 6. Verdict rules (mechanical, not subjective)

- **NO-GO:** any P0, or more than 3 failed acceptance criteria, or the phase's exit demo does not run.
- **GO-WITH-CHANGES:** no P0, at most 3 failed criteria, every failure has a concrete fix.
- **GO:** no P0, no P1, all acceptance criteria PASS with evidence, all applicable change drills PASS.

Also give a **score** out of 100 using: acceptance criteria 40, universal checks 30, change drills 15, product feel and docs 15. State the arithmetic.

---

## 7. Worth-it assessment (required section)

Answer each with evidence-based reasoning, in a short paragraph:
1. **Value delivered:** what can a viewer or user do now that they could not before, and is it impressive and credible?
2. **Cost and risk:** complexity added, debt created, risks for later phases.
3. **Keep, change or cut:** for each major component, say KEEP / CHANGE / CUT and why. Be willing to recommend cutting.
4. **Does it serve the pitch?** One paragraph on whether this phase moves the flagship goal forward.
5. **Next-phase readiness:** what must be true before the next phase starts.

---

## 8. Output template (write to `reviews/phase-N-review.md` and print)

```
# Phase N Review
Date / commit / reviewer session
## 1. Verdict
GO | GO-WITH-CHANGES | NO-GO   Score: xx/100 (arithmetic)
## 2. Freshness (Step 0 results)
## 3. Acceptance criteria table (ID | result | evidence)
## 4. Universal checks U1-U12 table (ID | result | evidence | severity)
## 5. Phase-specific checks table
## 6. Change drills table (drill | files | lines | time | result)
## 7. New adversarial checks I wrote and their results
## 8. Worth-it assessment (section 7)
## 9. Change list
| ID | Sev | Title | Location | Evidence | Required fix | Effort (S/M/L) | Acceptance test |
## 10. Accepted risks (only if the owner approved them)
## 11. Hand-off
Suggested GSD task list (one task per change-list item, ordered), and the exact re-review scope.
```

The change list is the most important output: every item needs a location, evidence, a specific fix and a test that will prove it fixed.

---

## 9. Re-review (after fixes)
Re-run only: all changed items, every P0 and P1 item, the full test suite, determinism and safety checks, and the change drills that failed. Produce `reviews/phase-N-review-r2.md` using the same template, with a "Regression" section.
