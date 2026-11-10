"""Configuration models for RoboFleet.
All tunables are strictly defined here with documentation, defaults, and validation.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class TimingConfig(BaseModel):
    """Simulation clock and timing tunables."""

    model_config = ConfigDict(extra="forbid")
    tick_hz: int = Field(default=10, ge=1, le=100, description="Simulation tick frequency in Hertz")
    max_duration_s: int = Field(
        default=3600, ge=1, description="Default simulation duration in seconds"
    )


class PhysicsConfig(BaseModel):
    """Robot physics, cell dimension, and motion costs."""

    model_config = ConfigDict(extra="forbid")
    cell_size_m: float = Field(
        default=0.8, ge=0.1, le=5.0, description="Square cell dimension in metres"
    )
    robot_speed_mps: float = Field(
        default=1.2, ge=0.1, le=5.0, description="Robot travel speed in metres/second"
    )
    turn_cost_ticks: int = Field(
        default=5, ge=0, description="Time in ticks to execute a 90-degree turn"
    )


class BatteryConfig(BaseModel):
    """Battery drain, thresholds, and charging rates."""

    model_config = ConfigDict(extra="forbid")
    drain_moving_per_tick: float = Field(
        default=0.01, ge=0.0, description="Percent battery drain per moving tick"
    )
    drain_idle_per_tick: float = Field(
        default=0.001, ge=0.0, description="Percent battery drain per idle tick"
    )
    charge_rate_per_tick: float = Field(
        default=0.05, ge=0.0, description="Percent battery gained per charging tick"
    )
    low_battery_threshold: float = Field(
        default=20.0, ge=5.0, le=50.0, description="Threshold to seek charger"
    )
    critical_battery_threshold: float = Field(
        default=10.0, ge=1.0, le=20.0, description="Threshold for critical alert"
    )
    recharge_target_pct: float = Field(
        default=95.0, ge=50.0, le=100.0, description="Battery target before resuming work"
    )


class LayoutPresetConfig(BaseModel):
    """Layout generation parameters."""

    model_config = ConfigDict(extra="forbid")
    preset: Literal["small", "standard", "large", "custom"] = Field(default="standard")
    ascii_file: str | None = Field(
        default=None, description="Path to hand-drawn ASCII layout file if custom"
    )
    width: int = Field(default=24, ge=8, description="Grid width in cells")
    height: int = Field(default=16, ge=8, description="Grid height in cells")
    cell_size_m: float = Field(
        default=0.8, ge=0.1, le=5.0, description="Square cell dimension in metres"
    )
    rack_rows: int = Field(default=4, ge=1, description="Number of rack double-rows")
    rack_length: int = Field(default=12, ge=4, description="Length of rack row in cells")
    rack_levels: int = Field(default=4, ge=1, le=8, description="Shelf vertical levels per cell")
    aisle_width: int = Field(default=2, ge=1, le=4, description="Width of picking aisles in cells")
    cross_aisle_width: int = Field(
        default=2, ge=1, le=4, description="Width of cross aisles in cells"
    )
    station_count: int = Field(default=3, ge=1, description="Number of pick/pack stations")
    charger_count: int = Field(default=4, ge=1, description="Number of charging stations")
    parking_count: int = Field(default=25, ge=1, description="Number of parking bays")
    right_hand_traffic: bool = Field(
        default=True, description="Enforce one-way flow lanes in aisles"
    )


class StrategyConfig(BaseModel):
    """Polymorphic strategy specification (type + params)."""

    model_config = ConfigDict(extra="allow")
    type: str = Field(description="Registered strategy name")
    params: dict[str, Any] = Field(default_factory=dict, description="Strategy parameters")


class CatalogueConfig(BaseModel):
    """Catalogue and slotting configuration."""

    model_config = ConfigDict(extra="forbid")
    source_type: Literal["generated", "csv"] = Field(default="generated")
    csv_file: str | None = Field(default=None, description="Path to CSV catalogue if source is csv")
    sku_count: int = Field(default=1500, ge=50, le=10000, description="Total active SKUs")
    empty_bin_pct: float = Field(
        default=5.0, ge=0.0, le=30.0, description="Percentage of bins initially unstocked"
    )
    top_k_popular_replicas: int = Field(
        default=50, ge=0, description="Number of top SKUs given replica bins"
    )


class RulesConfig(BaseModel):
    """Rule engine configuration."""

    model_config = ConfigDict(extra="forbid")
    rules_dir: str = Field(
        default="rules", description="Directory containing declarative YAML rules"
    )
    hot_reload: bool = Field(default=True, description="Hot reload rules on file modification")


class ScenarioConfig(BaseModel):
    """Top-level scenario configuration container."""

    model_config = ConfigDict(extra="forbid")
    scenario_name: str = Field(default="standard")
    seed: int = Field(default=42, description="Root random seed for deterministic simulation")
    robot_count: int = Field(default=20, ge=1, le=100, description="Number of active AMRs")

    timing: TimingConfig = Field(default_factory=TimingConfig)
    physics: PhysicsConfig = Field(default_factory=PhysicsConfig)
    battery: BatteryConfig = Field(default_factory=BatteryConfig)
    layout: LayoutPresetConfig = Field(default_factory=LayoutPresetConfig)
    catalogue: CatalogueConfig = Field(default_factory=CatalogueConfig)
    rules: RulesConfig = Field(default_factory=RulesConfig)

    planner: StrategyConfig = Field(
        default_factory=lambda: StrategyConfig(type="astar_flow", params={})
    )
    dispatcher: StrategyConfig = Field(
        default_factory=lambda: StrategyConfig(type="wander", params={"dwell_ticks": 20})
    )
