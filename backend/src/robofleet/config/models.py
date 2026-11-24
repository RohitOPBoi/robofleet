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


class OrdersConfig(BaseModel):
    """Order source adapter and lifecycle configuration."""

    model_config = ConfigDict(extra="forbid")
    adapter: Literal["demand_engine", "csv_replay", "webhook"] = Field(
        default="demand_engine", description="Active order source adapter"
    )
    demand_profile: str = Field(
        default="profiles/standard_evening.yaml", description="Path to demand profile YAML"
    )
    csv_file: str | None = Field(default=None, description="Path to CSV orders file if csv_replay")
    at_risk_threshold_ticks: int = Field(
        default=150, ge=10, description="Remaining ticks before deadline to flag order at_risk"
    )
    history_limit: int = Field(
        default=500, ge=50, description="Max finished orders kept in memory history"
    )
    rush_multiplier: float = Field(
        default=1.0, ge=1.0, le=10.0, description="Multiplier for demand burst"
    )
    urgent_share: float = Field(
        default=0.20, ge=0.0, le=1.0, description="Share of incoming orders tagged urgent"
    )
    nominal_service_time_ticks: int = Field(
        default=300, ge=50, description="Expected service time in ticks"
    )


class FulfilmentConfig(BaseModel):
    """Fulfilment, picking station, consolidation, and supervisor handoff parameters."""

    model_config = ConfigDict(extra="forbid")
    base_pick_time_ticks: int = Field(
        default=30, ge=5, description="Base picking time in ticks per item"
    )
    consolidation_time_ticks: int = Field(
        default=20, ge=0, description="Tote consolidation time in ticks"
    )
    supervisor_handoff_base_ticks: int = Field(
        default=40, ge=5, description="Base supervisor rider handoff time in ticks"
    )
    rider_arrival_rate_per_hr: float = Field(
        default=120.0, ge=10.0, description="Rider arrival rate per hour"
    )
    max_station_queue_capacity: int = Field(
        default=6, ge=1, description="Max robot queue size per picking station"
    )


class ServerConfig(BaseModel):
    """API server, WebSocket and authentication configuration."""

    model_config = ConfigDict(extra="forbid")
    host: str = Field(default="127.0.0.1", description="Bind host")
    port: int = Field(default=8000, ge=1024, le=65535, description="Bind port")
    delta_hz: float = Field(
        default=10.0, ge=1.0, le=50.0, description="WebSocket delta streaming frequency in Hz"
    )
    auth_token: str = Field(
        default="secret-robofleet-token", description="Bearer token for control channel"
    )
    cors_origins: list[str] = Field(
        default_factory=lambda: ["*"], description="Allowed CORS origins"
    )


class PickVerificationConfig(BaseModel):
    """Pick verification error model and retry parameters (Phase 6)."""

    model_config = ConfigDict(extra="forbid")
    enabled: bool = Field(default=True, description="Enable pick verification inspection")
    base_error_rate: float = Field(
        default=0.04, ge=0.0, le=0.5, description="Aggregate base failure probability"
    )
    retry_limit: int = Field(default=1, ge=0, le=3, description="Max retry attempts per pick")
    confidence_threshold: float = Field(
        default=0.85, ge=0.5, le=1.0, description="Minimum confidence for VERIFIED"
    )
    grasp_failure_rate: float = Field(
        default=0.015, ge=0.0, le=1.0, description="Estimated rate of failed grasp"
    )
    wrong_item_rate: float = Field(
        default=0.010, ge=0.0, le=1.0, description="Estimated rate of wrong SKU identification"
    )
    quantity_mismatch_rate: float = Field(
        default=0.010, ge=0.0, le=1.0, description="Estimated rate of quantity count discrepancy"
    )
    damaged_item_rate: float = Field(
        default=0.005, ge=0.0, le=1.0, description="Estimated rate of damaged merchandise"
    )


class ChaosConfig(BaseModel):
    """Chaos engineering and scheduled fault injection parameters (Phase 6)."""

    model_config = ConfigDict(extra="forbid")
    enabled: bool = Field(default=True, description="Enable chaos engine")
    scenario_file: str | None = Field(
        default=None, description="Path to chaos scenario YAML file if running scheduled chaos"
    )
    random_injection_rate: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Poisson arrival rate for random fault injection"
    )


class ReplenishmentConfig(BaseModel):
    """Minimal rule-driven replenishment tunables (Phase 6)."""

    model_config = ConfigDict(extra="forbid")
    enabled: bool = Field(default=True, description="Enable low-stock replenishment tasks")
    low_stock_threshold: int = Field(
        default=3, ge=1, description="Bin inventory threshold to trigger restock"
    )
    restock_quantity: int = Field(
        default=10, ge=1, description="Standard replenished unit batch size"
    )
    stocker_speed_ticks: int = Field(
        default=40, ge=5, description="Time in ticks for simulated stocker to replenish bin"
    )


class ReslottingConfig(BaseModel):
    """Re-slotting recommender parameters (Phase 6)."""

    model_config = ConfigDict(extra="forbid")
    enabled: bool = Field(default=True, description="Enable periodic re-slotting recommendations")
    evaluation_interval_ticks: int = Field(
        default=250, ge=50, description="Tick interval between re-slotting evaluations"
    )
    max_recommendations: int = Field(
        default=5, ge=1, le=20, description="Max recommendations produced per evaluation"
    )
    max_congestion_proxy_limit: float = Field(
        default=0.75, ge=0.1, le=1.0, description="Maximum allowable aisle congestion proxy"
    )


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
    orders: OrdersConfig = Field(default_factory=OrdersConfig)
    fulfilment: FulfilmentConfig = Field(default_factory=FulfilmentConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)

    verification: PickVerificationConfig = Field(default_factory=PickVerificationConfig)
    chaos: ChaosConfig = Field(default_factory=ChaosConfig)
    replenishment: ReplenishmentConfig = Field(default_factory=ReplenishmentConfig)
    reslotting: ReslottingConfig = Field(default_factory=ReslottingConfig)

    planner: StrategyConfig = Field(
        default_factory=lambda: StrategyConfig(type="astar_flow", params={})
    )
    dispatcher: StrategyConfig = Field(
        default_factory=lambda: StrategyConfig(type="wander", params={"dwell_ticks": 20})
    )
