"""Tests for CLI subcommands: render, validate-layout, config explain, rules, drills."""

from __future__ import annotations

from pathlib import Path

from robofleet.cli.main import main


def test_cli_validate_layout_and_render() -> None:
    # validate-layout
    ret = main(["validate-layout", "--scenario", "standard"])
    assert ret == 0

    # render
    ret = main(["render", "--scenario", "small"])
    assert ret == 0


def test_cli_config_explain() -> None:
    ret = main(["config", "explain", "--scenario", "standard", "--set", "timing.tick_hz=20"])
    assert ret == 0


def test_cli_rules_subcommands() -> None:
    assert main(["rules", "list"]) == 0
    assert main(["rules", "lint"]) == 0
    assert main(["rules", "test"]) == 0


def test_cli_export_schemas() -> None:
    assert main(["export-schemas"]) == 0


def test_cli_run_short_simulation(tmp_path: Path) -> None:
    out_dir = tmp_path / "cli_run"
    ret = main(["run", "--scenario", "small", "--duration", "2", "--out", str(out_dir)])
    assert ret == 0
    assert (out_dir / "metrics.json").exists()
    assert (out_dir / "final_snapshot.json").exists()


def test_cli_drills() -> None:
    assert main(["drills"]) == 0
