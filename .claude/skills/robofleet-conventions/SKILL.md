---
name: robofleet-conventions
description: Coding conventions, Standing Rules summary (SR-1 to SR-12), and how to run checks in RoboFleet.
---

# RoboFleet Conventions

## Standing Rules Summary
- **SR-1 Think before coding**: Explicit assumptions, document non-obvious choices in `docs/DECISIONS.md`.
- **SR-2 Simplicity first (ponytail ladder)**: Skip unnecessary features. Stdlib > existing deps > new deps.
- **SR-3 Surgical changes**: Every line traces to a requirement. No drive-by refactoring.
- **SR-4 Goal-driven execution**: Run checks/tests first, loop until passing.
- **SR-5 Dynamic by design**: Config over constants, rules as data, registries over conditionals. No magic numbers in `src/`.
- **SR-6 Evolvable contracts**: SemVer on contracts, versioned schemas, changelog tracking.
- **SR-7 Safety boundary**: SafetyGuard is the exclusive mover of robots.
- **SR-8 Evidence over claims**: Never assert completion without running commands or providing artifacts.
- **SR-9 Product feel**: Zero placeholder text (no lorem, test, dummy, foo) in visible surfaces; realistic INR and units.
- **SR-10 Agent Skills**: Document procedures in `.claude/skills/`.
- **SR-11 GSD discipline**: Atomic commits with conventional messages (`feat`, `fix`, `test`, `docs`, `refactor`).
- **SR-12 Sandbox & secrets**: No secrets in repo. Maintain `.env.example`. Check licenses (MIT/Apache-2.0 only).

## Verification Commands
```bash
make lint       # ruff check and magic number scan
make typecheck  # mypy --strict
make test       # pytest with coverage
make schemas    # export and check contract schemas
make drills     # run change drills CD-1 to CD-5
```
