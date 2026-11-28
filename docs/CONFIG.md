# RoboFleet Configuration Guide — Phase 1 & 2

## 1. Configuration Layering Order

Configuration is loaded through a 4-tier precedence hierarchy:
1. **Base Defaults**: `scenarios/defaults.yaml`
2. **Scenario Preset**: `scenarios/<name>.yaml` (`small`, `standard`, `large`)
3. **Environment Variables**: Prefixed with `ROBOFLEET_`
4. **CLI Overrides**: Supplied via `--set key=value`

---

## 2. Schema Specification

### 2.1 Order Source Configuration (`orders`)
```yaml
orders:
  adapter: demand_engine                # demand_engine | csv_replay | webhook
  demand_profile: profiles/standard_evening.yaml # Diurnal profile YAML
  csv_file: scenarios/sample_orders.csv # Replay orders CSV
  at_risk_threshold_ticks: 150         # Ticks before deadline to flag at_risk (15s at 10Hz)
  history_limit: 500                   # Retained finished orders
  rush_multiplier: 1.0                 # Demand burst factor
  urgent_share: 0.20                   # Share of incoming orders tagged urgent
  nominal_service_time_ticks: 300      # Nominal fulfillment window
```

### 2.2 Fulfilment & Station Operations Configuration (`fulfilment`)
```yaml
fulfilment:
  base_pick_time_ticks: 30             # Base pick duration (3.0s at 10Hz)
  consolidation_time_ticks: 20         # Multi-line tote consolidation time (2.0s)
  supervisor_handoff_base_ticks: 40    # Dispatch bay courier handoff duration (4.0s)
  rider_arrival_rate_per_hr: 120.0     # Mean Poisson courier arrivals per hour
  max_queue_capacity: 6                # Station queue physical buffer slots
```

### 2.3 Dispatcher & Planner Configuration (`dispatcher`, `planner`)
```yaml
dispatcher:
  type: batch_greedy                   # batch_greedy | fcfs_nearest | edf_deadline | random
  params:
    dwell_ticks: 20
    batch_window_ticks: 250
    low_battery_threshold: 22.0

planner:
  type: reservation_astar              # reservation_astar | astar_flow
  params:
    horizon_ticks: 25
    replan_wait_ticks: 8
    yield_wait_ticks: 20
    deadlock_threshold_ticks: 40
```

### 2.4 Server Configuration (`server`)
```yaml
server:
  host: 127.0.0.1                      # Bind host
  port: 8000                           # Bind port
  delta_hz: 10.0                       # WebSocket delta frequency in Hz
  auth_token: secret-robofleet-token   # Bearer token for control channel
  cors_origins:                        # Permitted CORS origins
    - "http://localhost:5173"
    - "http://localhost:8000"
    - "http://127.0.0.1:5173"
    - "http://127.0.0.1:8000"
```

### 2.5 AI Operations Brain Configuration (`brain`)
```yaml
brain:
  operating_mode: "heuristic"          # heuristic | ai | local_llm | replay
  heartbeat_ticks: 50                  # Periodic decision heartbeat interval
  deadlock_no_progress_ticks: 12       # Ticks stalled before deadlock triage
  outcome_eval_window_ticks: 20        # Post-execution outcome evaluation window
  max_decision_staleness_ticks: 30     # Async LLM staleness cutoff
  cloud:
    provider_type: "openai"            # openai | openrouter | groq | together | fireworks | deepseek | anthropic | custom
    api_compatibility: "openai_chat"   # openai_chat | openai_responses | anthropic_messages
    base_url: "https://api.openai.com/v1"
    model: "gpt-4o-mini"
    timeout_s: 12.0
    max_tokens: 900
    temperature: 0.15
    fallback_policy: "heuristic"       # heuristic | safe_wait
  local:
    provider: "ollama"
    base_url: "http://localhost:11434"
    model: "qwen3.5:4b"                # Recommended local initial model
    timeout_s: 15.0
    context_length: 4096
    temperature: 0.15
    max_tokens: 512
    max_concurrency: 1
    fallback_policy: "heuristic"       # heuristic | safe_wait
```

API keys for **AI Mode** are intentionally excluded from `ScenarioConfig` YAML dumps and `/api/config/effective`. Supply credentials at runtime through the UI **AI Settings** modal or environment variables (`ROBOFLEET_AI_API_KEY`, `OPENAI_API_KEY`, `OPENROUTER_API_KEY`, `GROQ_API_KEY`, `ANTHROPIC_API_KEY`).

---

## 3. Explaining Effective Config

Inspect resolved values and source origin layers:
```bash
python -m robofleet.cli config explain --scenario standard --set orders.adapter=csv_replay
```
