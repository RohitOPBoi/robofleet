"""Decision contracts for AI / brain module (Phase 5 seam defined early)."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from robofleet.contracts.common import RoboFleetBaseModel


class DecisionProposal(RoboFleetBaseModel):
    specialist: str
    action: str
    target_id: str | None = None
    confidence: float = 1.0
    rationale: str = ""


class Decision(RoboFleetBaseModel):
    decision_id: str
    tick: int = Field(ge=0)
    trigger: str
    brief_hash: str
    proposals: list[DecisionProposal] = Field(default_factory=list)
    final_commands: list[dict[str, Any]] = Field(default_factory=list)
    governance_outcome: str = "approved"  # approved, denied, require_human
    execution_result: str = "success"
    observed_outcome: str = "unknown"  # improved, neutral, worsened, unknown
    latency_ms: float = 0.0
    token_usage: dict[str, int] = Field(default_factory=dict)
    cost_usd: float = 0.0
    provider_mode: str = "heuristic"  # anthropic, heuristic, replay
    rationale: str = ""
