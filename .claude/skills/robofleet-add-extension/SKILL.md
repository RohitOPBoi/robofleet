---
name: robofleet-add-extension
description: Step-by-step procedure for adding an extension seam implementation along declared change axes CA-1 to CA-9.
---

# Adding an Extension Seam in RoboFleet

Seams exist ONLY along declared change axes (CA-1 to CA-9). A seam consists of:
1. A **Protocol** defined in `backend/src/robofleet/interfaces/` or respective subsystem.
2. A **typed Registry** in `backend/src/robofleet/registry/`.
3. A **config key / param model** in `backend/src/robofleet/config/`.
4. Exactly one **example or standard implementation**.
5. A **unit test** asserting registration, creation, and execution.

## Steps
1. Identify the Change Axis (CA-1 to CA-9).
2. Define the typed factory and param schema:
   ```python
   class MyStrategyParams(BaseModel):
       param1: float = 1.0
   ```
3. Register the implementation in the subsystem registry:
   ```python
   registry.register("my_strategy", factory, param_model=MyStrategyParams)
   ```
4. Expose the strategy selection via config YAML:
   ```yaml
   strategy:
     type: "my_strategy"
     params:
       param1: 2.0
   ```
5. Run `make test` to verify instantiation and behavior.
