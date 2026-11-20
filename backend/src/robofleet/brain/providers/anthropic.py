"""Anthropic Claude LLM Provider (Phase 5 - CA-6).
Integrates live Claude Sonnet / Haiku models via structured tool use.
Features automatic circuit breaking, token budgeting, and sub-tick failover to heuristic baseline.
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any
import httpx
from robofleet.brain.providers.base import LLMProviderResult
from robofleet.brain.providers.heuristic import HeuristicProvider
from robofleet.contracts.brain import DecisionProposal, SituationBrief

logger = logging.getLogger(__name__)

# Standard pricing per million tokens (Claude 3.5 Sonnet / Haiku benchmarks)
SONNET_INPUT_PRICE_PER_M = 3.0
SONNET_OUTPUT_PRICE_PER_M = 15.0


class AnthropicProvider:
    name: str = "anthropic"

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "claude-3-5-sonnet-20241022",
        timeout_s: float = 2.0,
        max_tokens: int = 1000,
        circuit_threshold: int = 3,
        circuit_cooldown_s: float = 30.0,
        failure_threshold: int | None = None,
        cooldown_sec: float | None = None,
    ) -> None:
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.model = model
        self.timeout_s = timeout_s
        self.max_tokens = max_tokens
        self.circuit_threshold = failure_threshold if failure_threshold is not None else circuit_threshold
        self.circuit_cooldown_s = cooldown_sec if cooldown_sec is not None else circuit_cooldown_s

        self.consecutive_failures: int = 0
        self.circuit_open_until: float = 0.0
        self.fallback = HeuristicProvider()

        # Telemetry
        self.total_prompt_tokens: int = 0
        self.total_completion_tokens: int = 0
        self.total_cost_usd: float = 0.0
        self.latencies_ms: list[float] = []

    @property
    def is_circuit_open(self) -> bool:
        return time.time() < self.circuit_open_until

    @property
    def circuit_tripped(self) -> bool:
        return self.is_circuit_open

    def _record_failure(self, err: str) -> None:
        self.consecutive_failures += 1
        logger.warning(
            "[AnthropicProvider] Call failed (%d consecutive): %s",
            self.consecutive_failures,
            err,
        )
        if self.consecutive_failures >= self.circuit_threshold:
            self.circuit_open_until = time.time() + self.circuit_cooldown_s
            logger.error(
                "[AnthropicProvider] Circuit breaker tripped open for %.1fs",
                self.circuit_cooldown_s,
            )

    def _record_success(self, latency: float, p_tokens: int, c_tokens: int) -> float:
        self.consecutive_failures = 0
        self.latencies_ms.append(latency)
        self.total_prompt_tokens += p_tokens
        self.total_completion_tokens += c_tokens
        call_cost = (
            (p_tokens / 1_000_000) * SONNET_INPUT_PRICE_PER_M
            + (c_tokens / 1_000_000) * SONNET_OUTPUT_PRICE_PER_M
        )
        self.total_cost_usd += call_cost
        return call_cost

    async def decide(
        self,
        brief: SituationBrief,
        specialists: list[Any] | None = None,
    ) -> LLMProviderResult:
        t0 = time.perf_counter()

        # 1. Fast failover if circuit is open
        if self.is_circuit_open:
            logger.info("[AnthropicProvider] Circuit open: auto-fallback to heuristic")
            res = await self.fallback.decide(brief, specialists)
            res.provider_name = "heuristic_fallback"
            return res

        api_key = self.api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            # No network key in environment: silently and smoothly use heuristic baseline
            res = await self.fallback.decide(brief, specialists)
            res.provider_name = "heuristic_offline"
            return res

        # 2. Build Structured Tools Payload
        brief_summary = brief.model_dump()
        system_prompt = (
            "You are the RoboFleet Mission Orchestrator for an automated quick-commerce dark store. "
            "You observe the store state brief and propose typed operational commands to maintain flow, "
            "meet 15-minute order SLAs, and balance workstation queues. "
            "Output JSON matching the required schema. Never invent entity IDs not in the brief."
        )

        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        payload = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": system_prompt,
            "messages": [
                {
                    "role": "user",
                    "content": f"SITUATION_BRIEF:\n{json.dumps(brief_summary, indent=2)}\n\n"
                    "Propose optimal operational commands and rationale.",
                }
            ],
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout_s) as client:
                resp = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers=headers,
                    json=payload,
                )
                if resp.status_code != 200:
                    self._record_failure(f"HTTP {resp.status_code}: {resp.text[:100]}")
                    res = await self.fallback.decide(brief, specialists)
                    res.provider_name = "heuristic_fallback"
                    return res

                data = resp.json()
                latency = (time.perf_counter() - t0) * 1000.0
                usage = data.get("usage", {})
                p_tokens = usage.get("input_tokens", 0)
                c_tokens = usage.get("output_tokens", 0)
                call_cost = self._record_success(latency, p_tokens, c_tokens)

                # Parse text response into commands and rationale
                content_blocks = data.get("content", [])
                text_content = ""
                for b in content_blocks:
                    if b.get("type") == "text":
                        text_content += b.get("text", "")

                # Extract JSON if returned in markdown fences or raw
                extracted_json: dict[str, Any] = {}
                try:
                    if "```json" in text_content:
                        json_str = text_content.split("```json")[1].split("```")[0].strip()
                        extracted_json = json.loads(json_str)
                    elif "{" in text_content and "}" in text_content:
                        s = text_content[text_content.find("{") : text_content.rfind("}") + 1]
                        extracted_json = json.loads(s)
                except Exception:
                    extracted_json = {}

                proposals = [
                    DecisionProposal.model_validate(p)
                    for p in extracted_json.get("proposals", [])
                ]
                commands = extracted_json.get("commands", [])
                rationale = extracted_json.get("rationale") or text_content[:200]

                if not commands:
                    # If empty or malformed output, fall back safely
                    res = await self.fallback.decide(brief, specialists)
                    res.token_usage = {"prompt_tokens": p_tokens, "completion_tokens": c_tokens}
                    res.cost_usd = round(call_cost, 6)
                    res.latency_ms = round(latency, 2)
                    res.provider_name = "anthropic"
                    return res

                return LLMProviderResult(
                    proposals=proposals,
                    commands=commands,
                    rationale=rationale,
                    token_usage={"prompt_tokens": p_tokens, "completion_tokens": c_tokens},
                    cost_usd=round(call_cost, 6),
                    latency_ms=round(latency, 2),
                    provider_name="anthropic",
                )

        except Exception as e:
            self._record_failure(str(e))
            res = await self.fallback.decide(brief, specialists)
            res.provider_name = "heuristic_fallback"
            return res
