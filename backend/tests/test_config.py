"""Tests for layered configuration system, validation, and explainability."""

from __future__ import annotations

import pytest
from robofleet.config.loader import explain_config, load_config


def test_config_layering_order(monkeypatch: pytest.MonkeyPatch) -> None:
    # 1. Base from defaults: robot_count is 20
    cfg1, t1 = load_config()
    assert cfg1.robot_count == 20
    assert "defaults" in t1.get_origin("robot_count")

    # 2. Scenario layer overrides defaults: small has robot_count = 10
    cfg2, t2 = load_config(scenario_name="small")
    assert cfg2.robot_count == 10
    assert "scenario" in t2.get_origin("robot_count")

    # 3. Environment variable layer overrides scenario
    monkeypatch.setenv("ROBOFLEET_ROBOT_COUNT", "35")
    cfg3, t3 = load_config(scenario_name="small")
    assert cfg3.robot_count == 35
    assert "env" in t3.get_origin("robot_count")

    # 4. CLI overrides layer overrides environment variable
    cfg4, t4 = load_config(scenario_name="small", cli_overrides=["robot_count=40"])
    assert cfg4.robot_count == 40
    assert "cli" in t4.get_origin("robot_count")


def test_config_validation_error_paths() -> None:
    # Invalid robot count (must be >= 1)
    with pytest.raises(ValueError, match="Field 'robot_count'"):
        load_config(cli_overrides=["robot_count=0"])

    # Invalid tick rate (must be >= 1)
    with pytest.raises(ValueError, match="Field 'timing.tick_hz'"):
        load_config(cli_overrides=["timing.tick_hz=-5"])


def test_config_explain_output() -> None:
    cfg, tracker = load_config(scenario_name="standard", cli_overrides=["timing.tick_hz=25"])
    explanation = explain_config(cfg, tracker)
    assert "timing.tick_hz" in explanation
    assert "cli" in explanation
    assert "robot_count" in explanation
