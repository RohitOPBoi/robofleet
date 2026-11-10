"""Schema migration registry and functions."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

# Registry of (from_version, to_version) -> migration_function
MIGRATION_REGISTRY: dict[tuple[str, str], Callable[[dict[str, Any]], dict[str, Any]]] = {}


def register_migration(
    from_version: str, to_version: str, fn: Callable[[dict[str, Any]], dict[str, Any]]
) -> None:
    MIGRATION_REGISTRY[(from_version, to_version)] = fn


def migrate(payload: dict[str, Any], from_version: str, to_version: str) -> dict[str, Any]:
    if from_version == to_version:
        return payload
    key = (from_version, to_version)
    if key in MIGRATION_REGISTRY:
        return MIGRATION_REGISTRY[key](payload)
    raise ValueError(
        f"No registered migration path from schema version {from_version} to {to_version}"
    )
