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


class AICloudConfig(BaseModel):
    """Universal Cloud AI API configuration (AI Mode)."""

    model_config = ConfigDict(extra="forbid")
    provider_type: Literal["openai_compatible", "anthropic", "custom"] = Field(
        default="openai_compatible",
        description="API family / adapter type",
    )
    provider_label: str = Field(
        default="OpenAI",
        description="Human-readable provider name (OpenAI, OpenRouter, Groq, Anthropic, etc.)",
    )
    api_compatibility: Literal["openai_chat", "openai_responses", "anthropic_messages"] = Field(
        default="openai_chat",
        description="Wire protocol used to communicate with the endpoint",
    )
    base_url: str = Field(
        default="https://api.openai.com/v1",
        description="Base API endpoint URL",
    )
    model: str = Field(
        default="gpt-4o-mini",
        description="Target cloud model identifier",
    )
    organization_id: str | None = Field(
        default=None, description="Optional provider organization ID"
    )
    project_id: str | None = Field(
        default=None, description="Optional provider project ID"
    )
    timeout_s: float = Field(
        default=10.0, ge=0.5, le=120.0, description="Request timeout in seconds"
    )
    max_tokens: int = Field(
        default=800, ge=64, le=8192, description="Maximum output tokens per decision"
    )
    temperature: float = Field(
        default=0.15, ge=0.0, le=2.0, description="Sampling temperature"
    )
    retry_count: int = Field(
        default=1, ge=0, le=5, description="Bounded retries on transient errors or malformed JSON"
    )
    circuit_threshold: int = Field(
        default=3, ge=1, le=20, description="Consecutive failures before opening circuit breaker"
    )
    circuit_cooldown_s: float = Field(
        default=30.0, ge=1.0, le=600.0, description="Circuit breaker cooldown in seconds"
    )
    fallback_policy: Literal["heuristic", "safe_wait"] = Field(
        default="heuristic",
        description="Explicit fallback behavior when cloud AI is unavailable",
    )


class LocalLLMConfig(BaseModel):
    """Local LLM inference configuration via Ollama."""

    model_config = ConfigDict(extra="forbid")
    provider: Literal["ollama"] = Field(default="ollama", description="Local inference runtime")
    base_url: str = Field(
        default="http://localhost:11434",
        description="Local Ollama server base URL",
    )
    model: str = Field(
        default="qwen3.5:4b",
        description="Ollama local model identifier (recommended initial model: qwen3.5:4b)",
    )
    timeout_s: float = Field(
        default=15.0, ge=1.0, le=180.0, description="Local inference request timeout in seconds"
    )
    context_length: int = Field(
        default=4096, ge=512, le=32768, description="Context window size (num_ctx)"
    )
    temperature: float = Field(
        default=0.15, ge=0.0, le=2.0, description="Sampling temperature"
    )
    max_tokens: int = Field(
        default=512, ge=64, le=4096, description="Maximum generated tokens (num_predict)"
    )
    retry_count: int = Field(
        default=1, ge=0, le=5, description="Decision retry count on malformed JSON"
    )
    max_concurrency: int = Field(
        default=1, ge=1, le=4, description="Maximum concurrent local inference requests"
    )
    fallback_policy: Literal["heuristic", "safe_wait"] = Field(
        default="heuristic",
        description="Explicit fallback behavior when Ollama or model is unavailable",
    )
    health_check_interval_s: float = Field(
        default=15.0, ge=1.0, le=300.0, description="Health-check polling interval in seconds"
    )
    circuit_threshold: int = Field(
        default=3, ge=1, le=20, description="Consecutive failures before temporary cooldown"
    )
    circuit_cooldown_s: float = Field(
        default=20.0, ge=1.0, le=300.0, description="Cooldown duration after circuit opens"
    )


class BrainConfig(BaseModel):
    """AI Operations Brain orchestrator and provider configuration."""

    model_config = ConfigDict(extra="forbid")
    operating_mode: Literal["heuristic", "ai", "local_llm", "replay"] = Field(
        default="heuristic",
        description="Active fleet intelligence operating mode",
    )
    heartbeat_ticks: int = Field(
        default=50, ge=5, le=1000, description="Periodic decision heartbeat interval in ticks"
    )
    deadlock_no_progress_ticks: int = Field(
        default=12, ge=3, le=200, description="Ticks without progress before declaring deadlock"
    )
    outcome_eval_window_ticks: int = Field(
        default=20, ge=5, le=200, description="Ticks after execution to measure actual outcome"
    )
    max_decision_staleness_ticks: int = Field(
        default=30, ge=1, le=500, description="Maximum tick drift allowed for async LLM results"
    )
    dedup_cooldown_ticks: int = Field(
        default=12, ge=1, le=200, description="Cooldown between identical brief hashes"
    )
    congestion_alert_threshold: int = Field(
        default=3, ge=1, le=50, description="Blocked robots threshold triggering congestion event"
    )
    critical_battery_trigger_pct: float = Field(
        default=25.0, ge=5.0, le=50.0, description="Battery percentage triggering triage event"
    )
    cloud: AICloudConfig = Field(default_factory=AICloudConfig)
    local: LocalLLMConfig = Field(default_factory=LocalLLMConfig)


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
    brain: BrainConfig = Field(default_factory=BrainConfig)

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
