"""Layered configuration loader and explainer.
Precedence: defaults.yaml < scenario.yaml < ROBOFLEET_* env < CLI --set key=value.
Tracks the exact origin of every effective configuration value.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from robofleet.config.models import ScenarioConfig


class ConfigOriginTracker:
    def __init__(self) -> None:
        self.origins: dict[str, str] = {}

    def record(self, key_path: str, origin: str) -> None:
        self.origins[key_path] = origin

    def get_origin(self, key_path: str) -> str:
        return self.origins.get(key_path, "default")


def _flatten_dict(d: dict[str, Any], parent_key: str = "", sep: str = ".") -> dict[str, Any]:
    items: list[tuple[str, Any]] = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(_flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def _set_deep(d: dict[str, Any], keys: list[str], val: Any) -> None:
    for k in keys[:-1]:
        d = d.setdefault(k, {})
    d[keys[-1]] = val


def _cast_primitive(val_str: str) -> Any:
    # Try bool, int, float, or string
    if val_str.lower() in ("true", "yes", "on"):
        return True
    if val_str.lower() in ("false", "no", "off"):
        return False
    try:
        return int(val_str)
    except ValueError:
        pass
    try:
        return float(val_str)
    except ValueError:
        pass
    return val_str


def load_config(
    scenario_name: str | None = None,
    scenario_file: Path | str | None = None,
    defaults_file: Path | str = "scenarios/defaults.yaml",
    cli_overrides: list[str] | None = None,
    env_prefix: str = "ROBOFLEET_",
) -> tuple[ScenarioConfig, ConfigOriginTracker]:
    tracker = ConfigOriginTracker()
    raw_data: dict[str, Any] = {}

    # 1. Defaults Layer
    d_path = Path(defaults_file)
    if d_path.exists():
        loaded_defaults = yaml.safe_load(d_path.read_text(encoding="utf-8")) or {}
        raw_data.update(loaded_defaults)
        for flat_k in _flatten_dict(loaded_defaults):
            tracker.record(flat_k, f"defaults ({d_path.name})")

    # 2. Scenario Layer
    s_path: Path | None = None
    if scenario_file:
        s_path = Path(scenario_file)
    elif scenario_name:
        s_candidate = Path(f"scenarios/{scenario_name}.yaml")
        if s_candidate.exists():
            s_path = s_candidate

    if s_path and s_path.exists():
        loaded_scenario = yaml.safe_load(s_path.read_text(encoding="utf-8")) or {}
        # Deep merge scenario into raw_data
        for flat_k, v in _flatten_dict(loaded_scenario).items():
            _set_deep(raw_data, flat_k.split("."), v)
            tracker.record(flat_k, f"scenario ({s_path.name})")

    # 3. Environment Variables Layer
    for env_k, env_v in os.environ.items():
        if env_k.startswith(env_prefix):
            # Example ROBOFLEET_ROBOT_COUNT -> robot_count
            # ROBOFLEET_TIMING__TICK_HZ -> timing.tick_hz
            tail = env_k[len(env_prefix) :].lower()
            key_path = tail.replace("__", ".")
            val = _cast_primitive(env_v)
            _set_deep(raw_data, key_path.split("."), val)
            tracker.record(key_path, f"env ({env_k})")

    # 4. CLI Overrides Layer (--set key.path=val)
    if cli_overrides:
        for override in cli_overrides:
            if "=" in override:
                k_path, v_str = override.split("=", 1)
                k_path = k_path.strip()
                val = _cast_primitive(v_str.strip())
                _set_deep(raw_data, k_path.split("."), val)
                tracker.record(k_path, "cli (--set)")

    try:
        config_obj = ScenarioConfig.model_validate(raw_data)
    except ValidationError as e:
        # Formulate clear, path-specific error messages
        errors_summary = []
        for err in e.errors():
            loc = ".".join(str(part) for part in err["loc"])
            msg = err["msg"]
            errors_summary.append(f"Field '{loc}': {msg}")
        raise ValueError("Config validation failed:\n" + "\n".join(errors_summary)) from e

    return config_obj, tracker


def explain_config(config: ScenarioConfig, tracker: ConfigOriginTracker) -> str:
    flat = _flatten_dict(config.model_dump())
    lines = [f"{'KEY':<40} {'VALUE':<25} {'ORIGIN'}"]
    lines.append("-" * 80)
    for k in sorted(flat.keys()):
        val_str = str(flat[k])
        if len(val_str) > 22:
            val_str = val_str[:19] + "..."
        origin = tracker.get_origin(k)
        lines.append(f"{k:<40} {val_str:<25} {origin}")
    return "\n".join(lines)
