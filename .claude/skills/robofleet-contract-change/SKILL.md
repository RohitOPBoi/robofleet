---
name: robofleet-contract-change
description: Procedure for additive vs breaking schema changes in RoboFleet (version bump, migration, changelog, review).
---

# RoboFleet Contract Change Protocol

All contracts live in `backend/src/robofleet/contracts/` and must adhere to SemVer (MAJOR.MINOR.PATCH).

## Classification Rules
1. **Patch (1.0.0 -> 1.0.1)**: Non-structural metadata update, documentation, internal comments.
2. **Minor / Additive (1.0.0 -> 1.1.0)**: New optional fields, new event types in union, backwards-compatible extensions.
3. **Major / Breaking (1.0.0 -> 2.0.0)**: Removing fields, renaming fields, altering types, tightening validations.

## Procedure
1. Run `python -m robofleet.tools.schema_compat` before editing to inspect baseline.
2. Update the Pydantic model in `backend/src/robofleet/contracts/`.
3. If breaking, implement a migration function in `robofleet.contracts.migrations`.
4. Update `contracts/CHANGELOG.md` with version bump, date, description, and migration notes.
5. Export updated schemas:
   ```bash
   make schemas
   ```
6. Verify schema compatibility test passes:
   ```bash
   pytest backend/tests/test_contracts.py
   ```
