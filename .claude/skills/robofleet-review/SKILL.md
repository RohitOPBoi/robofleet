---
name: robofleet-review
description: Runs the independent review protocol for a given phase, producing an evidence-only review report.
---

# RoboFleet Phase Review Runner

Runs `docs/playbook/01-review-protocol.md` against the phase completion claims.

## Rules of Engagement
- Read-only on source, tests, configs, and docs.
- The ONLY file written is `reviews/phase-N-review.md`.
- Evidence only: run tests and commands personally; unmeasured means FAIL.
- Run freshness checks (Step 0) first.
- Execute Universal Checks U1 to U12.
- Execute applicable Change Drills (CD-1 to CD-9) on a scratch branch.
- Calculate mechanical score (out of 100) and assign verdict: GO / GO-WITH-CHANGES / NO-GO.
- Produce ordered change list with locations, evidence, required fix, and acceptance tests.
