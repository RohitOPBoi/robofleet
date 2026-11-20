"""LLM Provider Port Interface (Phase 5 - CA-6).
Defines protocol for interchangeable AI decision engines (Heuristic, Anthropic, Replay).
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable
from pydantic import BaseModel, Field
from robofleet.contracts.brain import DecisionProposal, SituationBrief


class LLMProviderResult(BaseModel):
    proposals: list[DecisionProposal] = Field(default_factory=list)
    commands: list[dict[str, Any]] = Field(default_factory=list)
    rationale: str = ""
    token_usage: dict[str, int] = Field(default_factory=dict)
    cost_usd: float = 0.0
    latency_ms: float = 0.0
    provider_name: str = "heuristic"


@runtime_checkable
class LLMProvider(Protocol):
    """Protocol for AI decision engines."""

    name: str

    async def decide(
        self,
        brief: SituationBrief,
        specialists: list[Any],
    ) -> LLMProviderResult:
        ...
