"""Generic typed registry implementation.
Provides registration, parameter model validation, and instantiation by name.
Enforces declared change axes seams (CA-1 to CA-9).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ValidationError

T = TypeVar("T")


class Registry(Generic[T]):
    """Generic registry for factories producing instances of type T."""

    def __init__(self, name: str) -> None:
        self.registry_name = name
        self._factories: dict[str, Callable[..., T]] = {}
        self._param_models: dict[str, type[BaseModel] | None] = {}

    def register(
        self,
        name: str,
        factory: Callable[..., T],
        param_model: type[BaseModel] | None = None,
    ) -> None:
        self._factories[name] = factory
        self._param_models[name] = param_model

    def create(self, spec: dict[str, Any]) -> T:
        """Create an instance from a spec dict: {type: str, params: dict}."""
        if "type" not in spec:
            raise ValueError(f"Specification for {self.registry_name} must contain a 'type' key.")

        type_name = spec["type"]
        if type_name not in self._factories:
            known = ", ".join(sorted(self._factories.keys())) or "none"
            raise ValueError(
                f"Unknown {self.registry_name} type '{type_name}'. Registered types: [{known}]"
            )

        factory = self._factories[type_name]
        param_model = self._param_models[type_name]
        raw_params = spec.get("params", {})

        if param_model is not None:
            try:
                validated_params = param_model.model_validate(raw_params)
                # Pass as kwargs or as validated model
                return factory(**validated_params.model_dump())
            except ValidationError as e:
                raise ValueError(
                    f"Parameter validation failed for {self.registry_name} '{type_name}': {e}"
                ) from e
        else:
            return factory(**raw_params)

    def list_registered(self) -> list[str]:
        return sorted(self._factories.keys())
