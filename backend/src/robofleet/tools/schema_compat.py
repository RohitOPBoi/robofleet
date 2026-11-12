"""Schema compatibility checker.
Compares committed JSON Schemas in contracts/jsonschema/ with current Pydantic models.
Classifies changes as: NONE, PATCH, MINOR, BREAKING.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from robofleet.contracts.alert import Alert
from robofleet.contracts.catalogue import Bin, Sku
from robofleet.contracts.events import Event
from robofleet.contracts.layout import Layout
from robofleet.contracts.order import Order, Task
from robofleet.contracts.robot import Robot
from robofleet.contracts.state import DynamicState, StaticWorld, WorldSnapshot

MODELS: dict[str, type[BaseModel]] = {
    "StaticWorld": StaticWorld,
    "DynamicState": DynamicState,
    "WorldSnapshot": WorldSnapshot,
    "Layout": Layout,
    "Robot": Robot,
    "Order": Order,
    "Task": Task,
    "Alert": Alert,
    "Event": Event,
    "Sku": Sku,
    "Bin": Bin,
}


def compare_schemas(old_schema: dict[str, Any], new_schema: dict[str, Any]) -> str:
    """Classify schema change between old committed schema and new generated schema."""
    if old_schema == new_schema:
        return "NONE"

    old_props = old_schema.get("properties", {})
    new_props = new_schema.get("properties", {})
    old_req = set(old_schema.get("required", []))
    new_req = set(new_schema.get("required", []))

    # Check for removed properties -> BREAKING
    for prop in old_props:
        if prop not in new_props:
            return "BREAKING"

    # Check for newly added required properties -> BREAKING
    newly_required = new_req - old_req
    if newly_required:
        return "BREAKING"

    # Check for changed types on existing properties
    for prop, old_def in old_props.items():
        new_def = new_props[prop]
        if old_def.get("type") != new_def.get("type"):
            return "BREAKING"

    # If new optional properties were added -> MINOR
    newly_added_props = set(new_props.keys()) - set(old_props.keys())
    if newly_added_props:
        return "MINOR"

    # Otherwise description/title change -> PATCH
    return "PATCH"


def check_compatibility(schema_dir: Path | None = None) -> tuple[bool, dict[str, str]]:
    target_dir = schema_dir or Path("contracts/jsonschema")
    if not target_dir.exists():
        return False, {"all": "Schema directory does not exist"}

    results: dict[str, str] = {}
    has_breaking = False

    for name, model_cls in MODELS.items():
        schema_file = target_dir / f"{name}.json"
        if not schema_file.exists():
            results[name] = "MISSING_COMMITTED_SCHEMA"
            has_breaking = True
            continue

        try:
            committed_schema = json.loads(schema_file.read_text(encoding="utf-8"))
        except Exception as e:
            results[name] = f"MALFORMED_JSON: {e}"
            has_breaking = True
            continue

        current_schema = model_cls.model_json_schema()
        classification = compare_schemas(committed_schema, current_schema)
        results[name] = classification
        if classification == "BREAKING":
            has_breaking = True

    return not has_breaking, results


def main() -> int:
    ok, results = check_compatibility()
    print("Contract Schema Compatibility Report:")
    for model_name, status in results.items():
        print(f"  {model_name}: {status}")

    if not ok:
        print(
            "\nERROR: Breaking schema changes detected without required version bump!",
            file=sys.stderr,
        )
        return 1
    print("\nAll schema compatibility checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
